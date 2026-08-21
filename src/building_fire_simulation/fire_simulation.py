"""Fire, heat, degradation, suppression, and simulation-loop behavior."""

import random
import copy
from typing import Dict, Tuple, List, Optional, Iterable

Coord = Tuple[int, int, int]

from building_fire_simulation.domain import (
    BuildingComponent, Cube, Wall, FloorSurface, CeilingSurface, CeilingRoof,
    BuildingAccessory,
    Item, FireSafetyItem, CoverMaterialItem
)

from building_fire_simulation.agents import (
    FireDepartment, ensure_movement_hook_in_sim
)

SUPPORTED_HISTORY_PARAMETERS = (
    "fire_status",
    "air_temp",
    "components",
    "agents",
    "fire_department",
)

VERBOSE_START_FIRE = False
VERBOSE_SURFACE_HEAT_RELEASE_FORMULA = False
VERBOSE_TOTAL_CUBE_SURFACES_HEAT_RELEASE_FORMULA = False
VERBOSE_UPDATE_ITEMS_IGNITION = False
VERBOSE_UPDATE_SURFACE_IGNITION = False
VERBOSE_HEAT_INCREMENT_FORMULA = False
VERBOSE_HEAT_INCREASE_FORMULA = False
VERBOSE_UPDATE_AIR_TEMP_FROM_FIRE = False
VERBOSE_DEGRADATION_OF_SURFACE_FORMULA = False
VERBOSE_IS_DEGRADED = False
VERBOSE_TICK = False

class FireState:
    def __init__(self):
        self.is_on_fire: bool = False
        self.heat: float = 0.0
        self.burn_time: int = 0

    def __repr__(self):
        return f"<FireState fire={self.is_on_fire}, heat={self.heat:.1f}, burn_time={self.burn_time}>"

class FireSimulation:
    def __init__(self,
                 global_model: Dict[Coord, Cube],
                 spread_func=None,
                 save_full_history: bool = False,
                 agents: Optional[List["Agent"]] = None,
                 probabilistic: bool = False):
        self.global_model = global_model
        self.fire_status: Dict[Coord, FireState] = {coord: FireState() for coord in global_model}
        self.time = 0
        self.spread_func = spread_func
        self.save_full_history = save_full_history
        self.history = {}
        self.agents = agents if agents is not None else []
        self.probabilistic = probabilistic

        # minimal, dict-based config (no dataclass needed)
        self.snapshot_parameters = {
            "snapshot_interval": 1,
            "fields_to_save": ("fire_status",),
        }

def start_fire(self, coord: Coord, verbose=VERBOSE_START_FIRE):
    """
    Force-ignite all combustible surfaces and items in a cube.
    - Uses absolute sim time (self.time) so HRR curves start correctly.
    - Does NOT sample heat immediately at t=now; next tick will produce energy.
    - Optionally seeds the cube's heat store with energy to raise air to the
      highest ignition temperature (if air mass & cp are available).
    """
    if coord not in self.fire_status:
        return

    cube = self.global_model[coord]
    state = self.fire_status[coord]
    now = self.time

    ignition_temps = []

    # Helper: ignite FB at 'now' without consuming energy this instant
    def _force_ignite_fb(fb):
        if not fb:
            return
        if hasattr(fb, "force_ignite"):
            fb.force_ignite(now)
        else:
            # Fallback for older FireBehavior
            fb.is_ignited = True
            fb.time_above_ignition_temp = getattr(fb.material, "t_ignition", 0.0) or 0.0
            fb._ignition_time = now
            fb._curve_ready = False
            fb._last_eval_time = now
            fb._last_ignition_check_time = now

    # Ignite all surface covers
    for surface in cube.get_all_surfaces():
        cover_item = getattr(surface, "cover_material", None)
        if isinstance(cover_item, CoverMaterialItem):
            fb = getattr(cover_item, "fire_behavior", None)
            if fb:
                _force_ignite_fb(fb)
                # Mirror flags/timers to the surface for UI/telemetry
                surface.is_ignited = True
                if hasattr(surface, "time_above_ignition_temp"):
                    surface.time_above_ignition_temp = fb.time_above_ignition_temp
                ignition_temps.append(getattr(fb.material, "ignition_temp", 20.0))
                if verbose:
                    print(f" [cover: {getattr(cover_item, 'name', '?')}] forced ignition @ t={now:.2f}s "
                          f"(q_max={fb.material.q_max}, beta={getattr(fb.material, 'lambda_decay', 1.0)})")
        elif cover_item:
            raise TypeError(f"Surface cover_material is not a CoverMaterialItem: got {type(cover_item)}")

    # Ignite all free-standing items in the cube
    for item in getattr(cube, "items", []):
        fb = getattr(item, "fire_behavior", None)
        if fb:
            _force_ignite_fb(fb)
            if hasattr(item, "is_ignited"):
                item.is_ignited = True
            ignition_temps.append(getattr(fb.material, "ignition_temp", 20.0))
            if verbose:
                print(f" [item: {getattr(item, 'name', '?')}] forced ignition @ t={now:.2f}s "
                      f"(q_max={fb.material.q_max}, beta={getattr(fb.material, 'lambda_decay', 1.0)})")

    # Mark cube fire state
    state.is_on_fire = True
    state.burn_time = 0

    # Optional: physically seed air energy to reach the highest ignition temp
    max_ign_temp = max(ignition_temps, default=getattr(cube, "air_temp", 20.0))
    have_air_physics = hasattr(cube, "air_mass_kg") and hasattr(self, "CP_AIR_KJ_PER_KGK")

    if have_air_physics:
        delta_T = max(0.0, max_ign_temp - float(getattr(cube, "air_temp", 20.0)))
        eff = getattr(self, "HEATING_EFFICIENCY", 1.0) or 1.0
        seed_kJ = (cube.air_mass_kg * self.CP_AIR_KJ_PER_KGK * delta_T) / eff
        state.heat = float(getattr(state, "heat", 0.0)) + seed_kJ
        if verbose:
            print(f" Seeding air: m={cube.air_mass_kg:.3f} kg, cp={self.CP_AIR_KJ_PER_KGK:.3f} kJ/kgK, "
                  f"ΔT={delta_T:.2f} K → seed={seed_kJ:.2f} kJ")
    else:
        # Legacy fallback (units mix). Safe to remove once physical seeding is used everywhere.
        state.heat = max(float(getattr(state, "heat", 0.0)), float(max_ign_temp))
        if verbose:
            print(" Legacy kick used: state.heat set to max ignition temp (units mix).")

    # Update air temperature from the (possibly) seeded heat
    self.update_air_temp_from_fire(coord, verbose=verbose)



def start_random_fire(self, seed: int = None) -> Coord:
    """Randomly select a cube and ignite it. Returns the coord ignited."""
    if seed is not None:
        random.seed(seed)

    unburned_coords = [coord for coord, state in self.fire_status.items() if not state.is_on_fire]
    if not unburned_coords:
        raise ValueError("No unburned cubes available to ignite.")

    selected = random.choice(unburned_coords)
    self.start_fire(selected)
    return selected

def custom_spread_func(self, origin_coord: Coord, target_coord: Coord, surface: BuildingComponent) -> float:
    """
    Fire spreads if:
      - The connecting surface is marked as 'hollow'
      - OR the surface is fully degraded
    """
    if surface is None:
        return 0.0

    is_hollow = getattr(surface, "hollow", False)
    is_degraded = getattr(surface, "degradation", 1.0) <= 0

    if is_hollow or is_degraded:
        return 1.0  # Always spread if surface is hollow or destroyed

    return 0.0  # Otherwise, blocked


def get_mirrored_surface(self, coord1, coord2, surface1):
    """
    Given two adjacent coordinates and one surface, find the surface on the neighbor cube
    that corresponds to the opposite side.
    """
    dx, dy, dz = tuple(c2 - c1 for c1, c2 in zip(coord1, coord2))
    neighbor = self.global_model.get(coord2)
    if not neighbor:
        return None

    if isinstance(surface1, Wall):
        direction_map = {
            ("-1", "0", "0"): "right",
            ("1", "0", "0"): "left",
            ("0", "1", "0"): "back",   # 👈 adjusted
            ("0", "-1", "0"): "front", # 👈 adjusted
        }
        key = (str(dx), str(dy), str(dz))
        mirrored = direction_map.get(key)
        return getattr(neighbor, f"{mirrored}_wall", None) if mirrored else None

    elif isinstance(surface1, FloorSurface):
        return neighbor.ceiling
    elif isinstance(surface1, CeilingSurface):
        return neighbor.floor

    return None

def update_surface_ignition(self, cube, surface, verbose=VERBOSE_UPDATE_SURFACE_IGNITION):
    """
    Ignites a surface's cover if (and only if) its FireBehavior decides so:
      air_temp >= ignition_temp continuously for t_ignition seconds.
    Delegates timing to cover.fire_behavior.update_ignition(air_temp, now=self.time).
    Returns (just_ignited: bool, cover_or_None).
    """
    if verbose:
        print(f"[update_surface_ignition] cube={cube}, type={type(cube)} \n"
              f"surface={surface}, type={type(surface)}")

    cover = getattr(surface, "cover_material", None)
    if not isinstance(cover, CoverMaterialItem):
        if verbose:
            print("Surface has no valid CoverMaterialItem.")
        return False, None

    fb = getattr(cover, "fire_behavior", None)
    if not fb:
        if verbose:
            print("CoverMaterialItem is missing fire_behavior.")
        return False, None

    # If already ignited, keep state in sync and exit early.
    if getattr(surface, "is_ignited", False) or fb.is_ignited:
        # Optional: mirror timer to the surface for debugging/telemetry
        if hasattr(surface, "time_above_ignition_temp"):
            surface.time_above_ignition_temp = getattr(fb, "time_above_ignition_temp", 0.0)
        return False, None

    # Let FireBehavior handle continuous exposure accounting.
    just_ignited = fb.update_ignition(air_temp=cube.air_temp, now=self.time)

    # Keep external surface flag in sync with the internal FB state.
    if just_ignited or fb.is_ignited:
        setattr(surface, "is_ignited", True)
        # Optional: mirror timer for compatibility with any existing UI/logs
        if hasattr(surface, "time_above_ignition_temp"):
            surface.time_above_ignition_temp = getattr(fb, "time_above_ignition_temp", 0.0)

        if verbose:
            coord = getattr(cube, "coordinate", None)
            coord_str = coord.as_tuple() if hasattr(coord, "as_tuple") else "?"
            print(f"🔥 Surface ignited: {surface.__class__.__name__} in {coord_str}")

        return True, cover

    # Not ignited this tick; optionally mirror timer
    if hasattr(surface, "time_above_ignition_temp"):
        surface.time_above_ignition_temp = getattr(fb, "time_above_ignition_temp", 0.0)

    return False, None


def update_items_ignition(self, cube: Cube, verbose: bool = VERBOSE_UPDATE_ITEMS_IGNITION):
    """
    Iterate items and delegate ignition timing to each item's FireBehavior.
    Uses absolute sim time self.time; requires you to call this once per tick.
    """
    if verbose:
        print("\n[update_items_ignition]")
        coord = getattr(cube, "coordinate", None)
        coord_str = coord.as_tuple() if hasattr(coord, "as_tuple") else "?"
        print(f"🚨 update_items_ignition called for cube {coord_str}")
        print(f"📦 Cube has {len(getattr(cube, 'items', []))} items")
        print(f"🌡️ Air temp = {cube.air_temp:.1f}")

    for item in getattr(cube, "items", []):
        fb = getattr(item, "fire_behavior", None)
        if not fb:
            if verbose:
                print("No fire behavior attribute for item.")
            continue

        # Before/after for logging
        if verbose:
            print(f"🔍 Item '{getattr(item, 'name', '?')}' → "
                  f"Ignited={fb.is_ignited}, "
                  f"TimeAbove={getattr(fb, 'time_above_ignition_temp', 0.0):.2f}, "
                  f"T_ign={fb.material.t_ignition}, "
                  f"T_ign_temp={fb.material.ignition_temp}")

        just_ignited = fb.update_ignition(air_temp=cube.air_temp, now=self.time)

        # Optional: if the item has its own external flag, keep it in sync
        if hasattr(item, "is_ignited") and (just_ignited or fb.is_ignited):
            item.is_ignited = True

        if verbose and just_ignited:
            print(f"🔥 Item ignited: {getattr(item, 'name', '?')}")

    # No return to keep existing call sites unchanged

def surface_heat_release_formula(self, surface, burn_time: float,
                                 verbose=VERBOSE_SURFACE_HEAT_RELEASE_FORMULA) -> float:
    """
    Returns energy (kJ) released by a surface's cover material during this tick.
    Delegates to FireBehavior's HRR integrator using ABSOLUTE sim time (self.time).
    Applies when either the surface OR its fire_behavior reports ignited.
    """
    if verbose:
        print("[surface_heat_release_formula]")
        coord = getattr(getattr(surface, "cube", None), "coordinate", None)
        print(f"Surface at Cube: {coord}")

    cover = getattr(surface, "cover_material", None)
    if not isinstance(cover, CoverMaterialItem):
        if verbose:
            print("Surface has no valid CoverMaterialItem.")
        return 0.0

    fb = getattr(cover, "fire_behavior", None)
    is_surface_on = bool(getattr(surface, "is_ignited", False))
    is_fb_on = bool(fb and getattr(fb, "is_ignited", False))
    if not (fb and (is_surface_on or is_fb_on)):
        if verbose:
            print("CoverMaterialItem's fire_behavior is missing or not ignited.")
        return 0.0

    # Delegate with absolute sim time to advance HRR and flip FB off at burnout.
    heat_kJ = float(fb.heat_release(burn_time=self.time, verbose=verbose))
    if verbose:
        print(f"Heat (kJ this tick): {heat_kJ:.3f}")

    return heat_kJ


def total_cube_surfaces_heat_release_formula(self, cube: Cube, burn_time: float,
                                             verbose=VERBOSE_TOTAL_CUBE_SURFACES_HEAT_RELEASE_FORMULA) -> float:
    """
    Sum of surface cover heat outputs (kJ) for a cube this tick.
    Delegates each surface to surface_heat_release_formula, which now uses self.time.
    The 'burn_time' param is ignored (kept only for API compatibility).
    """
    if verbose:
        print("\n[total_cube_surfaces_heat_release_formula]")
        print(f"Cube: {getattr(cube, 'coordinate', None)}")
        if not cube:
            print("Cube doesn't exist")
            return 0.0

    total = 0.0
    for surface in cube.get_all_surfaces():
        q = self.surface_heat_release_formula(surface, burn_time=self.time, verbose=False)
        total += q

        if verbose and q > 0.0:
            print(f"🔥 Heat from {surface.__class__.__name__} (id={id(surface)}): {q:.3f} kJ")

    return total

#VERBOSE_HEAT_INCREMENT_FORMULA = False
#VERBOSE_HEAT_INCREASE_FORMULA = False
EXPONENTIAL_BASE = 1.05 # Exponential base for calculating increment in: heat_increment_formula.
# MAX_HEAT = 1000.0 # Max limit for heat in cube used in: heat_increase_formula.

def heat_increment_formula(self, burn_time: int, cube: Cube,
                           base: float = EXPONENTIAL_BASE,
                           verbose=VERBOSE_HEAT_INCREMENT_FORMULA) -> float:
    """
    Returns total energy (kJ) added to this cube during the current tick.
    Notes:
      - Uses absolute simulation time (self.time) for all heat_release() calls.
      - The 'burn_time' parameter is ignored (kept for API compatibility).
      - Surface heat is computed via total_cube_surfaces_heat_release_formula(), which also uses self.time.
    """
    # Surfaces (covers)
    surface_heat = self.total_cube_surfaces_heat_release_formula(
        cube, burn_time=self.time, verbose=False
    )

    # Items (free-standing and surface-mounted)
    item_heat = 0.0

    # Free-standing items inside the cube
    for item in getattr(cube, "items", []):
        if isinstance(item, Item):
            heat = float(item.heat_release(self.time))
            if verbose:
                print(f"Calling {getattr(item, 'name', '?')}.heat_release @ t={self.time:.2f}s → {heat:.3f} kJ")
            item_heat += heat

    # Items attached to surfaces (if any)
    for comp in cube.get_all_surfaces():
        for item in getattr(comp, "items", []):
            if isinstance(item, Item):
                heat = float(item.heat_release(self.time))
                if verbose:
                    print(f"Calling surface item {getattr(item, 'name', '?')}.heat_release @ t={self.time:.2f}s → {heat:.3f} kJ")
                item_heat += heat

    total_increment = surface_heat + item_heat

    if verbose:
        print(f"surface_heat: {surface_heat:.3f} kJ")
        print(f"item_heat: {item_heat:.3f} kJ")
        print(f"total_increment: {total_increment:.3f} kJ")

    return total_increment


def heat_increase_formula(self,
                          current_heat: float,
                          burn_time: int,
                          cube: Cube,
                          # max_heat: float = MAX_HEAT,
                          verbose=VERBOSE_HEAT_INCREASE_FORMULA) -> float:
    """
    Increases cube heat ENERGY (kJ) from surfaces and items for this tick.
    Notes:
      - Uses absolute simulation time (self.time) via heat_increment_formula.
      - The 'burn_time' parameter is retained for API compatibility but ignored downstream.
    """
    if verbose:
        print("\n[heat_increase_formula]")

    # Uses absolute time internally; 'burn_time' here is ignored by the callee.
    increment_kJ = self.heat_increment_formula(burn_time=self.time, cube=cube, verbose=False)
    heat_kJ = current_heat + increment_kJ

    if verbose:
        print(f"ΔE (this tick): {increment_kJ:.3f} kJ")
        print(f"Heat energy total: {heat_kJ:.3f} kJ")

    return heat_kJ

MAX_AIR_TEMP = 1000.0 # Max air temp for a cube.
TRANSFER_HEAT_BETWEEN_CUBES_FACTOR = 0.2 # Factor regulating heat transfer between cubes.
TRANSFER_EFFICIENCY = 0.4 # Factor regulating how much heat transfers to air temp.

def update_air_temp_from_fire(self, coord: Coord, verbose=False):
    """
    Convert accumulated fire energy (kJ) into air temperature rise for this cube.
    Harder to heat at higher temps via:
      - cp_air(T): mild increase with T
      - transfer_efficiency(T): decreases as ΔT to ambient grows
    """
    cube = self.global_model[coord]
    fire = self.fire_status[coord]

    # Parameters (overridable if you set these on the sim/cube)
    air_mass = getattr(cube, "air_mass_kg", 6.0)                # kg of air in the cell
    base_cp  = getattr(self, "CP_AIR_KJ_PER_KGK", 1.0)          # kJ/kg·°C at ~20°C
    base_eff = TRANSFER_EFFICIENCY                               # your existing constant
    ambient  = getattr(self, "AMBIENT_TEMP", 20.0)               # °C

    # Current conditions
    T = float(cube.air_temp)
    dT_to_amb = max(0.0, T - ambient)

    # Mild cp increase with temperature (~+2.5% per 100°C by default).
    # Clamp to keep numerics sane if things run very hot.
    cp = base_cp * (1.0 + 0.00025 * dT_to_amb)
    cp = max(0.8, min(1.5, cp))

    # Make transfer efficiency fall with temperature difference (saturating).
    # T_half: ΔT where efficiency is halved; exponent tunes the steepness.
    T_half = getattr(self, "HEAT_TRANSFER_T_HALF", 200.0)        # °C
    expo   = getattr(self, "HEAT_TRANSFER_EXPONENT", 1.5)
    eff_scale = 1.0 / (1.0 + (dT_to_amb / max(1e-6, T_half))**expo)
    eff = base_eff * eff_scale

    # Convert kJ -> Δ°C
    delta_temp = (fire.heat * eff) / (air_mass * cp)
    cube.air_temp = min(cube.air_temp + delta_temp, MAX_AIR_TEMP)

    if verbose:
        print(f"[update_air_temp_from_fire] E={fire.heat:.2f} kJ, eff={eff:.3f}, cp={cp:.3f}, "
              f"ΔT={delta_temp:.3f}°C, T_new={cube.air_temp:.2f}°C")

    # Consume the stored energy
    fire.heat = 0.0


def transfer_heat_between_cubes(self, source_coord: Coord, target_coord: Coord,
                                factor: float = TRANSFER_HEAT_BETWEEN_CUBES_FACTOR):
    source_cube = self.global_model[source_coord]
    target_cube = self.global_model[target_coord]

    # Only transfer if source is hotter
    delta = source_cube.air_temp - target_cube.air_temp
    if delta <= 0.0:
        return

    # Move a fraction of the temperature difference. Clamp the RESULT, not the increment.
    transfer = delta * factor
    target_cube.air_temp = min(target_cube.air_temp + transfer, MAX_AIR_TEMP)


def apply_cooling(self, cube, ambient_temp: float = 20.0,
                  cooling_rate: float = 0.05, radiative_coeff: float = 0.0003):
    """
    Cool the cube toward ambient. Uses:
      - Linear Newtonian cooling (proportional to ΔT)
      - Mild radiative-like term that grows with temperature (ΔT^2 scaling, small coefficient)
    """
    delta = cube.air_temp - ambient_temp
    if delta > 0.0:
        # Effective rate grows with temperature; clamp to avoid overshoot.
        effective_rate = cooling_rate + radiative_coeff * (delta / 100.0)**2
        effective_rate = min(effective_rate, 0.95)
        cube.air_temp -= effective_rate * delta

# Default values for degradation of surfaces functions.
TEMP_TO_DEGRADATION_CONSTANT = 0.05 # Regulates how much heat translates into degradation.
HEAT_TO_CAUSE_DEGRADATION = 300 # Only heat \geq will cause degradation.

def degradation_of_surface_formula(self,
                                   surface,
                                   air_temp: float,
                                   c: float = TEMP_TO_DEGRADATION_CONSTANT,
                                   verbose: bool = VERBOSE_DEGRADATION_OF_SURFACE_FORMULA) -> float:
    """
    Degrade a surface based on environmental temperature and material resistance.
    """
    if verbose:
        print("\n[degradation_of_surface_formula]")
        if not surface:
            print("No surface")
            return
        elif not surface.structure_material:
            print("No surface str. matr. exists")
            return

    burn_resistance = surface.structure_material.burn_resistance
    degradation = surface.degradation

    vulnerability = 1.0 - burn_resistance
    degradation_damage = c * air_temp * vulnerability

    if air_temp >= HEAT_TO_CAUSE_DEGRADATION:
        degradation = max(degradation - degradation_damage, 0.0)
    surface.degradation = degradation

    if verbose:
        print(f"  ↳ burn_resistance={burn_resistance:.2f}, air_temp={air_temp:.2f}, c={c}")
        print(f"  ↳ damage={degradation_damage:.2f}, new degradation={degradation:.2f}")

    return degradation



def is_degraded(self, surface, verbose: bool = VERBOSE_IS_DEGRADED) -> bool:
    """
    Check whether a surface is fully degraded (degradation ≤ 0).
    """
    result = surface.degradation <= 0.0
    if verbose:
        print(f"[is_degraded] \n{surface.__class__.__name__} (node {surface.node_id}) → {result}")
    return result

def _iter_all_surfaces(self, cube):
    """Yield this cube's surfaces (works even if .get_all_surfaces() isn't present)."""
    if hasattr(cube, "get_all_surfaces"):
        return cube.get_all_surfaces() or []
    labels = ("left_wall","right_wall","front_wall","back_wall","floor","ceiling","roof")
    res = []
    for lbl in labels:
        s = getattr(cube, lbl, None)
        if s is not None:
            res.append(s)
    return res

# replace your existing _discover_exits_from_accessories with this
def _discover_exits_from_accessories(self):
    """
    Return a de-duplicated list of coords that have at least one accessory marked as an exit.
    Looks for `is_exit` (preferred) or `exit_path` (legacy).
    """
    exits = set()
    for coord, cube in self.global_model.items():
        for surf in self._iter_all_surfaces(cube):
            for it in (getattr(surf, "items", []) or []):
                if bool(getattr(it, "is_exit", getattr(it, "exit_path", False))):
                    exits.add(coord)
                    break  # one is enough for this cube
    return sorted(exits)


def refresh_exits_from_building(self):
    """Re-scan the building and push exits to the FireDepartment."""
    exits = self._discover_exits_from_accessories()
    if hasattr(self, "fire_department") and hasattr(self.fire_department, "update_exits"):
        self.fire_department.update_exits(exits)
    return exits

def make_get_fire_state(sim):
    # Fast map: id(cube) -> coord
    id2coord = {id(c): coord for coord, c in sim.global_model.items()}
    fire_status = sim.fire_status  # bind dict to avoid capturing 'sim' itself

    def _get_fire_state(cube):
        coord = id2coord.get(id(cube))
        if coord is None:
            # slow fallback (should be rare)
            for k, c in sim.global_model.items():
                if c is cube:
                    coord = k
                    id2coord[id(cube)] = k
                    break
        return fire_status.get(coord)
    return _get_fire_state



def _set_air_temp(cube, T: float):
    cube.air_temp = float(T)

def _pathfind(start, goal):
    x, y, z = start; gx, gy, gz = goal
    path = []
    sx = 1 if gx >= x else -1
    sy = 1 if gy >= y else -1
    sz = 1 if gz >= z else -1
    while x != gx: x += sx; path.append((x, y, z))
    while y != gy: y += sy; path.append((x, y, z))
    while z != gz: z += sz; path.append((x, y, z))
    return path

def _collect_triggered_alarm_coords(self) -> list[Coord]:
    coords = set()
    for coord, cube in self.global_model.items():
        for surf in self._iter_all_surfaces(cube):   # <-- reuse shared helper
            for it in (getattr(surf, "items", []) or []):
                if hasattr(it, "triggered") and getattr(it, "triggered") and (
                    getattr(it, "is_alarm", False)
                    or "smoke_alarm" in str(getattr(it, "name", "")).lower()
                    or "alarm" in it.__class__.__name__.lower()
                ):
                    coords.add(coord); break
    return sorted(coords)

def _process_fire_department(self, verbose: bool = False, dt_s: float = 1.0) -> None:
    """Collect triggered alarms, notify the FD, then advance FD one step."""
    fd = getattr(self, "fire_department", None)
    if fd is None:
        return
    alarm_coords = self._collect_triggered_alarm_coords()
    if alarm_coords:
        fd.receive_alarm(alarm_coords, now_s=self.time)
    fd.step(dt_s=dt_s, now_s=self.time, verbose=verbose)

def _prepare_tick(self, verbose: bool):
    if verbose:
        print(f"\n--- Tick {self.time} ---")

    # BEFORE: self.save_state_snapshot(fields_to_save=fields)
    # fields = getattr(self, "snapshot_fields", ("fire_status",))
    self.save_state_snapshot()  # <— uses self.snapshot_parameters

    return set()

def _update_ignition_status(self):
    for coord, cube in self.global_model.items():
        self.update_items_ignition(cube)
        for surface in cube.get_all_surfaces():
            self.update_surface_ignition(cube, surface)

def _try_ignite_new_cubes(self, verbose: bool):
    for coord, state in self.fire_status.items():
        cube = self.global_model[coord]
        if state.is_on_fire:
            continue

        # Use the Cube’s derived fire state (items + covers, with epsilon on tails)
        has_active = cube.has_active_fire() if hasattr(cube, "has_active_fire") else any(
            getattr(s, "is_ignited", False) for s in cube.get_all_components()
        )

        if has_active:
            state.is_on_fire = True
            state.burn_time = 0

            # Seed using ignition temps of *actually active* components
            cover_temps = []
            for s in cube.get_all_surfaces():
                cover = getattr(s, "cover_material", None)
                fb = getattr(cover, "fire_behavior", None) if cover else None
                if fb and fb.is_active():  # uses new FB helper
                    cover_temps.append(fb.material.ignition_temp)

            item_temps = []
            for item in getattr(cube, "items", []):
                fb = getattr(item, "fire_behavior", None)
                if fb and fb.is_active():
                    item_temps.append(fb.material.ignition_temp)

            min_ign_temp = min(cover_temps + item_temps) if (cover_temps or item_temps) else 0.0

            state.heat = max(
                self.heat_increase_formula(
                    current_heat=0.0,
                    burn_time=0,
                    cube=cube,
                    verbose=verbose
                ),
                min_ign_temp
            )

            if verbose:
                print(f"🔥 Cube ignition triggered at {coord}, heat set to ≥ {min_ign_temp}")

        elif cube.air_temp >= 300:
            # Hot-air ignition fallback
            state.is_on_fire = True
            state.burn_time = 0
            state.heat = self.heat_increase_formula(
                current_heat=0.0,
                burn_time=0,
                cube=cube,
                verbose=verbose
            )
            if verbose:
                print(f"🔥 Cube at {coord} ignited by hot air (T={cube.air_temp:.1f})")

def _process_fire_suppression(self, cube, state):
    for surface in cube.get_all_surfaces():
        for item in getattr(surface, "items", []):
            if isinstance(item, FireSafetyItem):
                item.respond_to_fire(state, cube)

def _update_heat_and_degradation(self, cube, state, degraded_this_tick):
    for surface in cube.get_all_surfaces():
        sid = id(surface)
        if sid not in degraded_this_tick and hasattr(surface, "degradation") and surface.degradation > 0:
            self.degradation_of_surface_formula(surface, cube.air_temp)
            degraded_this_tick.add(sid)

def _spread_fire_to_neighbors(self, coord, cube, state, degraded_this_tick, verbose):
    for neighbor_coord, component1 in self.get_adjacent_components(coord):
        component2 = self.get_mirrored_surface(coord, neighbor_coord, component1)
        if not component2:
            continue

        for comp in (component1, component2):
            sid = id(comp)
            if sid not in degraded_this_tick and getattr(comp, "degradation", 100) > 0:
                self.degradation_of_surface_formula(comp, state.heat, verbose=False)
                degraded_this_tick.add(sid)

        h1, h2 = getattr(component1, "hollow", False), getattr(component2, "hollow", False)
        d1, d2 = self.is_degraded(component1), self.is_degraded(component2)

        passage_open = any(
            isinstance(item, BuildingAccessory) and item.allows_passage()
            for item in getattr(component1, "items", []) + getattr(component2, "items", [])
        )

        if verbose:
            print(f"[SPREAD] {coord} → {neighbor_coord}")
            print(f"  Surface1 hollow={h1}, degraded={d1}")
            print(f"  Surface2 hollow={h2}, degraded={d2}")
            print(f"  Cube heat: {state.heat:.1f}, air_temp: {cube.air_temp:.1f}")

        if (d1 or h1 or passage_open) and (d2 or h2 or passage_open):
            self.transfer_heat_between_cubes(coord, neighbor_coord)
            if verbose:
                print(f"  🔥 Heat transferred to {neighbor_coord} (air_temp={self.global_model[neighbor_coord].air_temp:.1f})")

def _process_burning_cubes(self, degraded_this_tick: set, verbose: bool):
    for coord, state in self.fire_status.items():
        if not state.is_on_fire:
            continue

        cube = self.global_model[coord]
        if verbose:
            print(f"[tick] Processing burning cube at {coord}")

        # 1) Apply last tick’s stored energy to air
        state.burn_time += 1
        self.update_air_temp_from_fire(coord)
        cube.air_temp = min(cube.air_temp, 1000.0)

        # 2) Suppression reacts
        self._process_fire_suppression(cube, state)

        # 3) Compute NEW heat for this tick
        state.heat = self.heat_increase_formula(
            current_heat=state.heat,
            burn_time=state.burn_time,  # downstream uses self.time
            cube=cube
        )

        # 4) Degrade + spread
        self._update_heat_and_degradation(cube, state, degraded_this_tick)
        self._spread_fire_to_neighbors(coord, cube, state, degraded_this_tick, verbose)

        # 5) Sync surface flags with their FB activity
        for s in cube.get_all_surfaces():
            if hasattr(s, "extinguish_cover_material"):
                s.extinguish_cover_material()

        # 6) Determine if anything is still *active* (ignited OR emitted heat this tick)
        def _fb_active(fb, eps=1e-3) -> bool:
            if not fb:
                return False
            if hasattr(fb, "is_active"):
                return fb.is_active(eps)
            return bool(getattr(fb, "is_ignited", False) or
                        (getattr(fb, "latest_heat_output", 0.0) > eps))

        if hasattr(cube, "has_active_fire"):
            still_burning = cube.has_active_fire()
        else:
            still_burning = False
            # covers
            for s in cube.get_all_surfaces():
                cov = getattr(s, "cover_material", None)
                if _fb_active(getattr(cov, "fire_behavior", None) if cov else None):
                    still_burning = True
                    break
            # items (free + surface-mounted)
            if not still_burning:
                for it in getattr(cube, "items", []):
                    if _fb_active(getattr(it, "fire_behavior", None)):
                        still_burning = True
                        break
                if not still_burning:
                    for s in cube.get_all_surfaces():
                        for it in getattr(s, "items", []) or []:
                            if _fb_active(getattr(it, "fire_behavior", None)):
                                still_burning = True
                                break
                        if still_burning:
                            break

        # 7) Keep cube flag in sync (optional helper on Cube)
        if hasattr(cube, "refresh_fire_flag"):
            cube.refresh_fire_flag()

        # 8) Extinguish cube when no new heat AND no active burners remain
        if state.heat <= 0.0 and not still_burning:
            state.is_on_fire = False
            if verbose:
                print(f"[extinguish] Cube at {coord} fire extinguished after {state.burn_time} ticks.")

def _edge_surfaces(self, cur, nxt):
    """Return the two surfaces between cur -> nxt using surface_neighbor."""
    x1, y1, z1 = cur; x2, y2, z2 = nxt
    dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
    cube = self.global_model.get(cur)
    if cube is None: return None, None

    if   dx ==  1 and dy == 0 and dz == 0: s1 = cube.right_wall
    elif dx == -1 and dy == 0 and dz == 0: s1 = cube.left_wall
    elif dx ==  0 and dy == 1 and dz == 0: s1 = cube.front_wall
    elif dx ==  0 and dy ==-1 and dz == 0: s1 = cube.back_wall
    elif dx ==  0 and dy == 0 and dz == 1: s1 = cube.ceiling
    elif dx ==  0 and dy == 0 and dz ==-1: s1 = cube.floor
    else:
        return None, None  # not an adjacent step

    s2 = getattr(s1, "surface_neighbor", None)
    return s1, s2

def _process_agent_movement(self, verbose: bool):
    for agent in getattr(self, "agents", []):
        if not agent.alive:
            continue

        # init tick throttle
        if not hasattr(agent, "_ticks_waited"):
            agent._ticks_waited = 0

        # Normalize path head: drop duplicates of current location
        while agent.path and agent.path[0] == agent.location:
            agent.path.pop(0)

        if not agent.path:
            continue

        next_wp = agent.path[0]

        # Let the Agent decide if the step is legal. This will:
        # - accept adjacent steps OR explicit bridges via leads_to
        # - auto-unlock (via access_panel) and open doors when allowed
        # - honor hazard gates (avoid_fire / max_air_temp)
        ok, reason = agent.can_pass_between(
            self.global_model,
            agent.location,
            next_wp,
            policy={
                "avoid_fire": True,
                "max_air_temp": 150.0,       # match your previous danger threshold
                "auto_open_doors": True,
                "auto_unlock_doors": True,
            },
        )

        if not ok:
            # Greedy skip of bad waypoint; optional: plug replanner here instead.
            if verbose:
                print(f"🧱 Agent {agent.name}: cannot step {agent.location} → {next_wp} ({reason}).")
            agent.path.pop(0)
            continue

        # Throttle by agent.speed (ticks per cell)
        agent._ticks_waited += 1
        if agent._ticks_waited >= max(1, int(agent.speed)):
            agent.location = next_wp
            agent.path.pop(0)
            agent._ticks_waited = 0
            if verbose:
                print(f"🚶 Agent {agent.name} moved to {agent.location}")

def _apply_cooling_all_cubes(self):
    for cube in self.global_model.values():
        self.apply_cooling(cube)

def tick(self, verbose: bool = VERBOSE_TICK):
    degraded_this_tick = self._prepare_tick(verbose)
    self._update_ignition_status()
    self._try_ignite_new_cubes(verbose)
    self._process_burning_cubes(degraded_this_tick, verbose)
    self._process_agent_movement(verbose)
    self._apply_cooling_all_cubes()
    self._process_fire_department(verbose=verbose, dt_s=1.0)  # pass verbose
    self.time += 1

def configure_snapshots(self, *,
                        snapshot_interval: Optional[int] = None,
                        fields_to_save: Optional[Tuple[str, ...]] = None) -> None:
    params = self.snapshot_parameters
    if isinstance(params, dict):
        if snapshot_interval is not None:
            params["snapshot_interval"] = snapshot_interval
        if fields_to_save is not None:
            params["fields_to_save"] = tuple(fields_to_save)
    else:
        if snapshot_interval is not None:
            params.snapshot_interval = snapshot_interval
        if fields_to_save is not None:
            params.fields_to_save = tuple(fields_to_save)

@staticmethod
def _coord_key(c):
    if isinstance(c, tuple):
        return c
    if hasattr(c, "as_tuple"):
        return c.as_tuple()
    try:
        return tuple(c)
    except Exception:
        return c

# ------------------- component analysis ----------------------------
def _serialize_component(self, obj, category: str, label: Optional[str] = None) -> dict:
    fb = getattr(obj, "fire_behavior", None)
    has_fb = fb is not None
    total = float(getattr(fb, "total_energy", 0.0)) if has_fb else None
    released = float(getattr(fb, "released_energy", 0.0)) if has_fb else None
    latest = float(getattr(fb, "latest_heat_output", 0.0)) if has_fb else None
    is_ignited = bool(getattr(fb, "is_ignited", False)) if has_fb else None
    pct_left = None
    if has_fb and total and total > 0:
        pct_left = max(0.0, min(100.0, 100.0 * (1.0 - (released / total))))
    return {
        "name": getattr(obj, "name", obj.__class__.__name__ if obj is not None else "Unknown"),
        "class": obj.__class__.__name__ if obj is not None else "Unknown",
        "category": category,   # "item" | "surface" | "cover"
        "label": label,
        "has_fire_behavior": has_fb,
        "is_ignited": is_ignited,
        "total_energy": total,
        "released_energy": released,
        "latest_heat_output": latest,
        "energy_left_pct": pct_left,
    }

def _iter_surface_covers(self, surface):
    """Yield cover items from a surface: supports .cover_material or plural aliases/methods."""
    cm_single = getattr(surface, "cover_material", None)
    if cm_single is not None:
        yield cm_single
        return
    for attr in ("cover_materials","cover_items","cover_material_items","covers","coverings","materials","layers","fire_layers"):
        cm = getattr(surface, attr, None)
        if cm:
            if isinstance(cm, dict):
                for obj in cm.values():
                    if obj is not None: yield obj
            elif isinstance(cm, (list, tuple, set)):
                for obj in cm:
                    if obj is not None: yield obj
            else:
                yield cm
            return
    for m in ("get_cover_materials","get_cover_items","iter_covers","iter_cover_items"):
        if hasattr(surface, m):
            try:
                res = getattr(surface, m)()
                if not res: return
                if isinstance(res, dict):
                    for obj in res.values():
                        if obj is not None: yield obj
                elif isinstance(res, (list, tuple, set)):
                    for obj in res:
                        if obj is not None: yield obj
                else:
                    yield res
                return
            except Exception:
                return

def _serialize_surface(self, surface, label: Optional[str] = None) -> dict:
    base = self._serialize_component(surface, category="surface", label=label)
    covers = [self._serialize_component(cov, category="cover", label=label) for cov in self._iter_surface_covers(surface)]
    base["covers"] = covers
    if covers:
        base["latest_heat_output"] = sum((c.get("latest_heat_output") or 0.0) for c in covers)
        base["released_energy"]    = sum((c.get("released_energy")    or 0.0) for c in covers)
        base["total_energy"]       = sum((c.get("total_energy")       or 0.0) for c in covers)
        tot = base.get("total_energy") or 0.0
        rel = base.get("released_energy") or 0.0
        base["energy_left_pct"]    = (100.0 * (1.0 - rel / tot)) if tot > 0 else None
    return base

def _collect_surfaces(self, cube) -> dict:
    """Return {label: surface} with deduplication and stable labeling priority."""
    candidates = []
    for lbl in ("left_wall","right_wall","front_wall","back_wall","floor","ceiling","roof","ceiling_roof"):
        if hasattr(cube, lbl):
            s = getattr(cube, lbl)
            if s is not None: candidates.append((3, lbl, s))
    smap = getattr(cube, "surfaces", None)
    if isinstance(smap, dict):
        for lbl, s in smap.items():
            if s is not None: candidates.append((2, str(lbl), s))
    if hasattr(cube, "iter_surfaces"):
        try:
            for lbl, s in cube.iter_surfaces():
                if s is not None: candidates.append((1, str(lbl), s))
        except Exception:
            pass
    if hasattr(cube, "get_all_surfaces"):
        try:
            for i, s in enumerate(cube.get_all_surfaces()):
                if s is not None:
                    lbl = getattr(s, "name", None) or getattr(s, "label", None) or f"surface_{i}"
                    candidates.append((0, str(lbl), s))
        except Exception:
            pass

    best_for_id = {}
    for prio, lbl, s in candidates:
        sid = id(s)
        cur = best_for_id.get(sid)
        if cur is None or prio > cur[0]:
            best_for_id[sid] = (prio, lbl, s)

    result, used = {}, set()
    for prio, lbl, s in sorted(best_for_id.values(), key=lambda x: (-x[0], x[1])):
        base = lbl
        if base in used:
            i = 1
            lbl2 = f"{base}_{i}"
            while lbl2 in used:
                i += 1; lbl2 = f"{base}_{i}"
            lbl = lbl2
        result[lbl] = s
        used.add(lbl)
    return result

# ---------------- agent analysis -------------------
def _serialize_agent(self, agent) -> dict:
    """Return a JSON-friendly dict of the agent's current state."""
    def _coord(v):
        return None if v is None else self._coord_key(v)

    def _coord_list(lst):
        return [] if not lst else [self._coord_key(c) for c in lst]

    return {
        "name": getattr(agent, "name", None),
        "role": getattr(agent, "role", None),
        "alive": bool(getattr(agent, "alive", True)),
        "health": float(getattr(agent, "health", 0.0)) if hasattr(agent, "health") else None,
        "speed": float(getattr(agent, "speed", 0.0)) if hasattr(agent, "speed") else None,

        "location": _coord(getattr(agent, "location", None)),
        "target":   _coord(getattr(agent, "target", None)),
        "path":     _coord_list(getattr(agent, "path", [])),

        # behavior/state flags
        "is_evacuating": bool(getattr(agent, "is_evacuating", False)),
        "is_assisting":  bool(getattr(agent, "is_assisting", False)),

        # cognition
        "awareness_level":  float(getattr(agent, "awareness_level", 0.0)) if hasattr(agent, "awareness_level") else None,
        "competence_level": float(getattr(agent, "competence_level", 0.0)) if hasattr(agent, "competence_level") else None,
        "panic_level":      float(getattr(agent, "panic_level", 0.0)) if hasattr(agent, "panic_level") else None,

        # exposures
        "heat_exposure":  float(getattr(agent, "heat_exposure", 0.0)) if hasattr(agent, "heat_exposure") else None,
        "smoke_exposure": float(getattr(agent, "smoke_exposure", 0.0)) if hasattr(agent, "smoke_exposure") else None,

        # policy (copy to avoid later mutation)
        "movement_policy": dict(getattr(agent, "movement_policy", {})),

        # items (re-use your component serializer)
        "items": [self._serialize_component(it, category="agent_item") for it in (getattr(agent, "items", []) or [])],
    }

def _snapshot_fire_status(self):
    import copy
    return copy.deepcopy(self.fire_status)

def _snapshot_air_temp(self):
    return { self._coord_key(coord): getattr(cube, "air_temp", None)
             for coord, cube in self.global_model.items() }

def _snapshot_components(self):
    comps = {}
    for coord, cube in self.global_model.items():
        key = self._coord_key(coord)
        items_list = [self._serialize_component(it, "item") for it in (getattr(cube, "items", []) or [])]
        surfaces_dict = { lbl: self._serialize_surface(surf, label=lbl)
                          for lbl, surf in self._collect_surfaces(cube).items() }
        comps[key] = {"items": items_list, "surfaces": surfaces_dict}
    return comps

def _snapshot_agents(self):
    """List of agents with their current attributes."""
    agents = getattr(self, "agents", []) or []
    return [self._serialize_agent(a) for a in agents]

def _snapshot_fire_department(self):
    fd = getattr(self, "fire_department", None)
    if not fd:
        return None
    # fallbacks if telemetry not yet set this tick
    telem = getattr(fd, "_last_telemetry", None)
    if telem is None:
        unit_states = [{
            "name": u.name,
            "location": tuple(u.location) if u.location is not None else None,
            "enroute": bool(u.enroute),
            "arrived": bool(u.arrived),
            "eta": getattr(fd, "_eta", {}).get(u.name, None),
            "targets_remaining": len(u.targets or [])
        } for u in getattr(fd, "units", [])]
        telem = {
            "time": self.time,
            "opened_egress": 0,
            "cooled_cubes": 0,
            "agents_helped": 0,
            "force_entries": 0,
            "unit_states": unit_states,
            "command_mode": getattr(fd, "command_mode", None),
            "active_incident": bool(getattr(fd, "active_incident", False)),
        }
    return telem


def _ensure_snapshot_builders(self):
    if not hasattr(self, "_snapshot_builders"):
        self._snapshot_builders: Dict[str, callable] = {
            "fire_status":     self._snapshot_fire_status,
            "air_temp":        self._snapshot_air_temp,
            "components":      self._snapshot_components,
            "agents":          self._snapshot_agents,
            "fire_department": self._snapshot_fire_department
        }

def _resolve_snapshot_params(self,
                             snapshot_interval: Optional[int],
                             fields_to_save: Optional[Tuple[str, ...]]) -> Tuple[int, Tuple[str, ...]]:
    params = self.snapshot_parameters if isinstance(self.snapshot_parameters, dict) else self.snapshot_parameters
    if isinstance(params, dict):
        snap_int = int(snapshot_interval if snapshot_interval is not None else params.get("snapshot_interval", 1))
        fields   = tuple(fields_to_save if fields_to_save is not None else params.get("fields_to_save", ("fire_status",)))
    else:
        snap_int = int(snapshot_interval if snapshot_interval is not None else getattr(params, "snapshot_interval", 1))
        fields   = tuple(fields_to_save if fields_to_save is not None else getattr(params, "fields_to_save", ("fire_status",)))
    return snap_int, fields

def _should_take_snapshot(self, snap_int: int) -> bool:
    return bool(getattr(self, "save_full_history", False)) and (self.time % max(1, snap_int) == 0)

def save_state_snapshot(
    self,
    snapshot_interval: Optional[int] = None,
    fields_to_save: Optional[Tuple[str, ...]] = None,
) -> None:
    """
    Save selected parts of the state every `snapshot_interval` ticks.

    Supported fields:
      - "fire_status"
      - "air_temp"
      - "components"       (loose items, surfaces, and each surface's cover items)
      - "agents"           (all agent attributes at the snapshot)
      - "fire_department"  (fire department status/action telemetry)
    """
    self._ensure_snapshot_builders()
    snap_int, fields = self._resolve_snapshot_params(snapshot_interval, fields_to_save)
    if not self._should_take_snapshot(snap_int):
        return

    snapshot: dict = {}
    for field in fields:
        builder = self._snapshot_builders.get(field)
        if builder is None:
            # silently skip unknown fields, or log a warning if you prefer
            continue
        snapshot[field] = builder()

    if not isinstance(self.history, dict):
        self.history = {}
    self.history[self.time] = snapshot

def get_adjacent_components(self, coord: Coord, verbose: bool = False) -> List[Tuple[Coord, BuildingComponent]]:
    """
    For a given cube coordinate, return a list of tuples:
    (adjacent cube coordinate, connecting surface component on the origin cube).
    """
    adjacent = []
    x, y, z = coord
    cube = self.global_model.get(coord)
    if not cube:
        return adjacent

    neighbor_offsets = {
        'left':  (-1, 0, 0),
        'right': (1, 0, 0),
        'front': (0, 1, 0),
        'back':  (0, -1, 0),
        'below': (0, 0, -1),
        'above': (0, 0, 1),
    }

    for direction, (dx, dy, dz) in neighbor_offsets.items():
        neighbor_coord = (x + dx, y + dy, z + dz)
        if neighbor_coord not in self.global_model:
            continue

        # ✅ Proper surface attribute for each direction
        if direction in {"left", "right", "front", "back"}:
            surface = getattr(cube, f"{direction}_wall", None)
        elif direction == "below":
            surface = cube.floor
        elif direction == "above":
            surface = cube.ceiling
        else:
            continue

        if surface:
            adjacent.append((neighbor_coord, surface))
            if verbose:
                print(f"[get_adjacent_components] {coord} → {neighbor_coord} via {surface.__class__.__name__} ({direction})")

    return adjacent


def get_adjacency_type(self, component: BuildingComponent) -> str:
    """Surface type for base probability lookup."""
    if isinstance(component, Wall):
        return "wall"
    elif isinstance(component, FloorSurface):
        return "floor"
    elif isinstance(component, CeilingSurface):
        return "ceiling"
    elif isinstance(component, CeilingRoof):
        return "ceiling"
    else:
        return "unknown"


def get_opposite_direction(self, direction: str) -> str:
    return {
        "left": "right", "right": "left",
        "front": "back", "back": "front",
        "above": "below", "below": "above"
    }.get(direction, "unknown")


def get_heat_map_at_timestep(self, t: int) -> Dict[Coord, float]:
    """
    Return a heat map (coord → heat) for the simulation at timestep t.
    """
    if not isinstance(self.history, dict) or t not in self.history:
        raise IndexError(f"Timestep {t} is out of bounds for recorded history.")

    snap = self.history[t]
    fire = snap.get("fire_status", {})
    # fire is a dict: coord -> FireState
    return {coord: fs.heat for coord, fs in fire.items() if fs.is_on_fire}


def get_burning_cubes(self, epsilon_kJ: float = 1e-3) -> List[Tuple[int, int, int]]:
    """
    Return coords of cubes that are actually burning now:
    - cube flag set AND (state.heat > 0 OR any FB is active this tick).
    Opportunistically clear stale flags.
    """
    burning = []
    for coord, state in self.fire_status.items():
        cube = self.global_model[coord]

        if hasattr(cube, "has_active_fire"):
            active = cube.has_active_fire(epsilon_kJ)
        else:
            def _fb_active(fb) -> bool:
                if not fb:
                    return False
                if hasattr(fb, "is_active"):
                    return fb.is_active(epsilon_kJ)
                return bool(getattr(fb, "is_ignited", False) or
                            (getattr(fb, "latest_heat_output", 0.0) > epsilon_kJ))

            active = False
            for s in cube.get_all_surfaces():
                cov = getattr(s, "cover_material", None)
                if _fb_active(getattr(cov, "fire_behavior", None) if cov else None):
                    active = True; break
            if not active:
                for it in getattr(cube, "items", []):
                    if _fb_active(getattr(it, "fire_behavior", None)):
                        active = True; break
                if not active:
                    for s in cube.get_all_surfaces():
                        for it in getattr(s, "items", []) or []:
                            if _fb_active(getattr(it, "fire_behavior", None)):
                                active = True; break
                        if active: break

        if state.is_on_fire and (state.heat > 0.0 or active):
            burning.append(coord)
        elif state.is_on_fire and not active and state.heat <= 0.0:
            state.is_on_fire = False  # clear stale flag

    return burning

def _iter_all_items(self, cube) -> Iterable[object]:
    """Yield all items 'inside' a cube and attached to its surfaces."""
    # Free-standing items
    for it in getattr(cube, "items", []) or []:
        yield it
    # Surface-mounted items
    for s in self._iter_all_surfaces(cube):
        for it in getattr(s, "items", []) or []:
            yield it

def enable_probabilistic_devices(sim, *, rng=None, verbose=False):
    """
    Find devices that support probabilistic behavior and enable + (optionally) draw.
    """
    import numpy as np
    rng = rng or np.random.default_rng()

    count = 0
    for cube in sim.global_model.values():
        for surface in cube.get_all_surfaces():
            for item in getattr(surface, "items", []) or []:
                # Only flip devices that opt-in or have a 'probabilistic' attribute in their class
                if hasattr(item, "enable_probabilistic"):
                    item.enable_probabilistic(rng=rng)
                    count += 1
                    if verbose:
                        nm = getattr(item, "name", item.__class__.__name__)
                        print(f"[prob✓] ENABLED -> {nm} @ {cube.coordinate.as_tuple()}")

    if verbose and count == 0:
        print("[prob] No devices supporting probabilistic behavior were found.")


def reset_probabilistic_params(sim, verbose=False):
    """Redraw per-incident samples (e.g., trigger temp, max burn time) for all devices."""
    count = 0
    for cube in sim.global_model.values():
        for surface in cube.get_all_surfaces():
            for item in getattr(surface, "items", []) or []:
                if hasattr(item, "reset_probabilistic_params") and getattr(item, "probabilistic", False):
                    item.reset_probabilistic_params()
                    count += 1
                    if verbose:
                        nm = getattr(item, "name", item.__class__.__name__)
                        print(f"[prob↻] RESET -> {nm} @ {cube.coordinate.as_tuple()}")
    if verbose and count == 0:
        print("[prob] No probabilistic devices to reset.")

def run_simulation(global_model,
                   nr_ticks_to_simulate: int,
                   save_full_history: bool,
                   snapshot_interval: int,
                   save_history_parameters: tuple,
                   agents: list,
                   probabilistic: bool,
                   fire_dept_arrival_coords: Tuple[int, int, int],
                   fire_dept_response_time: float = 240,
                   start_fire_at_coord: Tuple[int, int, int] = (0, 0, 0),
                   random_seed: Optional[int] = None,
                  ):

    global_model = global_model

    # Initialize sim.
    sim = FireSimulation(
        global_model,                        # Imported model.
        save_full_history=save_full_history, # Save simulation info.
        agents=agents,                       # Include agents in sim.
        probabilistic=probabilistic          # Set probabilistic simulation setting.
        )
    sim.random_seed = random_seed
    ensure_movement_hook_in_sim(sim)

    rng = None
    if random_seed is not None:
        import numpy as np

        random.seed(random_seed)
        rng = np.random.default_rng(random_seed)

    # Define building exits.
    exits = sim._discover_exits_from_accessories() if hasattr(sim, "_discover_exits_from_accessories") else []

    # Initialize the fire department.
    sim.fire_department = FireDepartment(
        model=sim.global_model,
        get_fire_state=make_get_fire_state(sim),
        set_air_temp=_set_air_temp,
        pathfind=_pathfind,
        exits=exits,
        dispatch_origin=fire_dept_arrival_coords if fire_dept_arrival_coords else exits[0],
        default_response_time_s=fire_dept_response_time,
        probabilistic = True if probabilistic else False
    )
    sim.fire_department.agents = sim.agents

    # Enable probabilistic variables.
    if probabilistic:
        sim.enable_probabilistic_devices(rng=rng)  # Activate probabilistic devices.
        sim.reset_probabilistic_params()     # Draw new random values.

    # Set snapshot parameters.
    sim.snapshot_parameters = {
        "snapshot_interval": snapshot_interval,
        "fields_to_save": save_history_parameters,
    }

    # Start fire.
    sim.start_fire(start_fire_at_coord)

    # Capture the seed state at t=0
    sim.save_state_snapshot()

    # Run steps in simulation.
    for _ in range(nr_ticks_to_simulate):
        sim.tick()

    return sim

# Starting fires.
FireSimulation.start_fire = start_fire
FireSimulation.start_random_fire = start_random_fire

# Spreading.
FireSimulation.custom_spread_func = custom_spread_func   # Obsolete??
FireSimulation.get_mirrored_surface = get_mirrored_surface
FireSimulation.update_surface_ignition = update_surface_ignition
FireSimulation.update_items_ignition = update_items_ignition

# Controlling heat.
FireSimulation.surface_heat_release_formula = surface_heat_release_formula
FireSimulation.total_cube_surfaces_heat_release_formula = total_cube_surfaces_heat_release_formula
FireSimulation.heat_increment_formula = heat_increment_formula
FireSimulation.heat_increase_formula = heat_increase_formula
FireSimulation.update_air_temp_from_fire = update_air_temp_from_fire
FireSimulation.transfer_heat_between_cubes = transfer_heat_between_cubes
FireSimulation.apply_cooling = apply_cooling


# Degradation of surfaces.
FireSimulation.degradation_of_surface_formula = degradation_of_surface_formula
FireSimulation.is_degraded = is_degraded

# Timestep methods.
FireSimulation._prepare_tick = _prepare_tick
FireSimulation._update_ignition_status = _update_ignition_status
FireSimulation._try_ignite_new_cubes = _try_ignite_new_cubes
FireSimulation._process_fire_suppression = _process_fire_suppression
FireSimulation._update_heat_and_degradation = _update_heat_and_degradation
FireSimulation._spread_fire_to_neighbors = _spread_fire_to_neighbors
FireSimulation._process_burning_cubes = _process_burning_cubes
FireSimulation._edge_surfaces = _edge_surfaces
FireSimulation._process_agent_movement = _process_agent_movement
FireSimulation._iter_all_surfaces = _iter_all_surfaces
FireSimulation._discover_exits_from_accessories = _discover_exits_from_accessories
FireSimulation.refresh_exits_from_building = refresh_exits_from_building
FireSimulation.make_get_fire_state = make_get_fire_state
FireSimulation._set_air_temp = _set_air_temp
FireSimulation._pathfind = _pathfind
FireSimulation._collect_triggered_alarm_coords = _collect_triggered_alarm_coords
FireSimulation._process_fire_department = _process_fire_department
FireSimulation._apply_cooling_all_cubes = _apply_cooling_all_cubes
FireSimulation.tick = tick

# History.
FireSimulation.configure_snapshots = configure_snapshots
FireSimulation._coord_key = _coord_key
FireSimulation._serialize_component = _serialize_component
FireSimulation._iter_surface_covers = _iter_surface_covers
FireSimulation._serialize_surface = _serialize_surface
FireSimulation._collect_surfaces = _collect_surfaces
FireSimulation._serialize_agent = _serialize_agent
FireSimulation._snapshot_fire_status = _snapshot_fire_status
FireSimulation._snapshot_air_temp = _snapshot_air_temp
FireSimulation._snapshot_components = _snapshot_components
FireSimulation._snapshot_agents = _snapshot_agents
FireSimulation._snapshot_fire_department = _snapshot_fire_department
FireSimulation._ensure_snapshot_builders = _ensure_snapshot_builders
FireSimulation._resolve_snapshot_params = _resolve_snapshot_params
FireSimulation._should_take_snapshot = _should_take_snapshot
FireSimulation.save_state_snapshot = save_state_snapshot

# Get info.
FireSimulation.get_adjacent_components = get_adjacent_components
FireSimulation.get_adjacency_type = get_adjacency_type # Obsolete??
FireSimulation.get_burning_cubes = get_burning_cubes # Obsolete??
FireSimulation.get_heat_map_at_timestep = get_heat_map_at_timestep
FireSimulation.get_opposite_direction = get_opposite_direction # Obsolete??

# Probabilistic switch.
FireSimulation._iter_all_items = _iter_all_items
FireSimulation.enable_probabilistic_devices = enable_probabilistic_devices
FireSimulation.reset_probabilistic_params = reset_probabilistic_params

FireSimulation.run_simulation = run_simulation
