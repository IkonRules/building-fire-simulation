"""Occupant movement and fire-department response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Iterable
from collections import deque
from copy import deepcopy
import math

from building_fire_simulation.domain import (
    ACCESS_CARDS
)

from building_fire_simulation.probability_distributions import (
    lognormal_sampler
)

Coord = Tuple[int, int, int]

class Agent:
    def __init__(self,
                 name: str,
                 location: Tuple[int, int, int],
                 awareness_level: float,
                 competence_level: float,
                 role: str,
                 health: float = 100.0,
                 speed: float = 5.0,
                 items: Optional[List[object]] = None):
        self.name = name
        self.location = location
        self.role = role
        self.health = health
        self.alive = True
        self.speed = speed
        self.items = items if items is not None else []
        self.heat_exposure = 0.0
        self.smoke_exposure = 0.0
        self.is_evacuating = False
        self.is_assisting = False
        self.awareness_level = awareness_level
        self.competence_level = competence_level
        self.panic_level = 0.0
        self.target: Optional[Tuple[int, int, int]] = None
        self.path: list[Tuple[int, int, int]] = []

    # ---- movement config ----
    movement_policy: Dict[str, object] = {
        "avoid_fire": True,
        "max_air_temp": 80.0,
        "auto_open_doors": True,       # try opening when permitted
        "auto_unlock_doors": True,     # NEW: try unlocking when permitted
    }

    # ---- helpers ----
    @staticmethod
    def _surface_attr_for_delta(dx: int, dy: int, dz: int) -> Optional[str]:
        if abs(dx) + abs(dy) + abs(dz) != 1:
            return None
        if dx ==  1: return "right_wall"
        if dx == -1: return "left_wall"
        if dy ==  1: return "front_wall"
        if dy == -1: return "back_wall"
        if dz ==  1: return "ceiling"
        if dz == -1: return "floor"

    @staticmethod
    def _iter_accessories(surface, kinds: set):
        for it in (getattr(surface, "items", []) or []):
            if getattr(it, "access_type", None) in kinds:
                yield it

    def _has_access(self, panel) -> bool:
        """True if any of this agent's cards satisfies panel.determine_access(card)."""
        if panel is None:
            return False  # panel-less doors shouldn't be 'unlockable' by credentials
        for it in self.items:
            if hasattr(it, "access_level") and panel.determine_access(it):
                return True
        return False

    def _attempt_unlock_and_open(self, door) -> bool:
        """
        Unlock if we have credentials (when a panel exists). If door is unlocked,
        anyone may open it. Return True iff the door ends up allowing passage.
        """
        # Blocked doors are never passable
        if getattr(door, "is_blocked", False):
            return False

        # Already passable?
        if hasattr(door, "allows_passage") and door.allows_passage():
            return True

        panel = getattr(door, "access_panel", None)

        # If locked: only unlock if there is a panel AND we have access
        if getattr(door, "is_locked", False):
            if panel is not None:
                if self._has_access(panel):
                    door.is_locked = False  # unlock via credentials
                else:
                    return False            # locked and no access → stop
            else:
                # Locked and no panel → cannot unlock (adjust here if you want a "mechanical unlock" rule)
                return False

        # At this point the door is unlocked (either was already unlocked or we just unlocked it).
        # Anyone may open it.
        if getattr(door, "open", None):
            door.open()
            return door.allows_passage() if hasattr(door, "allows_passage") else False

        return False


    # ---- single-step gate ----
    def can_pass_between(self,
                         model: Dict[Coord, "Cube"],
                         a: Coord, b: Coord,
                         policy: Optional[Dict[str, object]] = None) -> tuple[bool, str]:
        policy = {**self.movement_policy, **(policy or {})}
        ca = model.get(a)
        if not ca:
            return False, "from_out_of_bounds"

        dx, dy, dz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
        src_attr = self._surface_attr_for_delta(dx, dy, dz)

        # Non-adjacent: allow only explicit bridges (stairs/door.leads_to)
        if src_attr is None:
            for s in ca.get_all_surfaces():
                for it in (getattr(s, "items", []) or []):
                    if getattr(it, "leads_to", None) == b and not getattr(it, "is_blocked", False):
                        kind = getattr(it, "access_type", None)
                        if kind == "stairs":
                            return True, "via_stairs_bridge"
                        if kind == "door":
                            if it.allows_passage():
                                return True, "via_door_bridge_open"
                            if policy.get("auto_open_doors", True) and self._attempt_unlock_and_open(it):
                                return True, "via_door_bridge_unlocked_opened"
            return False, "non_adjacent_step"

        # Adjacent: use neighbor surfaces
        sA = getattr(ca, src_attr, None)
        if sA is None:
            return False, f"missing_surface:{src_attr}"
        sB = getattr(sA, "surface_neighbor", None)
        if sB is None:
            return False, "no_surface_neighbor"

        cb = getattr(sB, "cube", None) or model.get(b)
        if cb is None:
            return False, "neighbor_cube_missing"

        # Hazards
        if policy.get("avoid_fire", True) and getattr(cb, "is_on_fire", False):
            return False, "target_on_fire"
        tmax = policy.get("max_air_temp", None)
        if (tmax is not None) and getattr(cb, "air_temp", 20.0) > float(tmax):
            return False, "too_hot"

        # Vertical moves require stairs
        if src_attr in ("floor", "ceiling"):
            stairs = [it for s in (sA, sB) for it in self._iter_accessories(s, {"stairs"})]
            if not stairs:
                return False, "no_stairs"
            if any(getattr(st, "is_blocked", False) for st in stairs):
                return False, "stairs_blocked"
            return True, "stairs_ok"

        # Horizontal: built opening?
        if getattr(sA, "hollow", False) or getattr(sB, "hollow", False):
            return True, "hollow_opening"

        # Otherwise, need a door
        doors = [it for s in (sA, sB) for it in self._iter_accessories(s, {"door"})]
        if not doors:
            return False, "solid_wall"

        # If any door already passable → ok
        if any(d.allows_passage() for d in doors):
            return True, "door_open"

        # Try to open/unlock with credentials
        if policy.get("auto_open_doors", True) or policy.get("auto_unlock_doors", True):
            for d in doors:
                if self._attempt_unlock_and_open(d):
                    return True, "door_unlocked_opened"

        return False, "door_closed_or_locked"

    # ---- whole-path validator ----
    def validate_path(self,
                      model: Dict[Coord, "Cube"],
                      path: Optional[List[Coord]] = None,
                      policy: Optional[Dict[str, object]] = None) -> tuple[bool, Optional[dict]]:
        p = path if path is not None else self.path
        if not p or len(p) < 2:
            return True, None
        for i in range(len(p) - 1):
            ok, reason = self.can_pass_between(model, p[i], p[i+1], policy)
            if not ok:
                return False, {"index": i, "from": p[i], "to": p[i+1], "reason": reason}
        return True, None

    # ---- one-step mover ----
    def try_step(self,
                 model: Dict[Coord, "Cube"],
                 policy: Optional[Dict[str, object]] = None) -> bool:
        if not self.path or len(self.path) < 2:
            return False
        here, nxt = self.path[0], self.path[1]
        ok, _ = self.can_pass_between(model, here, nxt, policy)
        if not ok:
            return False
        self.location = nxt
        self.path.pop(0)
        return True

    def __repr__(self):
        return (f"<Human {self.name} ({self.role}) @ {self.location} | "
                f"health={self.health:.1f}, evacuating={self.is_evacuating}, aware={self.awareness_level:.2f} | "
                f"items={self.items}>")

class OfficeStaff(Agent):
    def __init__(self,
                 name: str,
                 location: Tuple[int, int, int],
                 health: float = 100.0,
                 speed: float = 1.0,
                 items: Optional[List[object]] = None,
                 path: Optional[List[Tuple[int, int, int]]] = None):
        super().__init__(
            name=name,
            location=location,
            role="office_staff",
            awareness_level=0.3,
            competence_level=0.2,
            health=health,
            speed=speed,
            items=items
        )
        self.path = path if path is not None else []

        # As of now set specifically for global_model.
        self.room_target_weights = {
            self.role: {
                "downstairs_large_office": 3,
                "downstairs_storage": 1,
                "downstairs_meeting_room": 5,
                "downstairs_entry_hall":  2,
                "upstairs_large_office":  3,
                "upstairs_small_office_1":  4,
                "upstairs_small_office_2":  4,
                "upstairs_small_office_3":  4,
                "upstairs_small_office_4":  4,
                "upstairs_small_office_5":  4,
                "upstairs_open_area":  3
                }}

class Janitor(Agent):
    def __init__(self,
                 name: str,
                 location: Tuple[int, int, int],
                 health: float = 100.0,
                 speed: float = 1.0,
                 items: Optional[List[object]] = None,
                 path: Optional[List[Tuple[int, int, int]]] = None):
        super().__init__(
            name=name,
            location=location,
            role="Janitor",
            awareness_level=0.4,
            competence_level=0.3,
            health=health,
            speed=speed,
            items=items
        )
        self.path = path if path is not None else []

        # As of now set specifically for global_model.
        self.room_target_weights = {
            self.role: {
                "downstairs_large_office": 2,
                "downstairs_storage":  7,
                "downstairs_meeting_room":  3,
                "downstairs_entry_hall":  5,
                "upstairs_large_office":  2,
                "upstairs_small_office_1":  3,
                "upstairs_small_office_2":  3,
                "upstairs_small_office_3":  3,
                "upstairs_small_office_4":  3,
                "upstairs_small_office_5":  3,
                "upstairs_open_area": 5
                }}

AGENT_TEMPLATES = {
    "office_staff": OfficeStaff(name="Elin", location=(0, 0, 0)),
    "janitor": Janitor(
        name="John",
        location=(0, 0, 0),
        items=[ACCESS_CARDS["access_card_level_3"]],
        path=[(0, 0, 0), (0, 1, 0), (0, 2, 0)],
    )
}

def create_agent(kind: str, **overrides):
    """Return a NEW agent cloned from the template, with optional attribute overrides."""
    agent = deepcopy(AGENT_TEMPLATES[kind])   # deep copy so lists/items aren’t shared
    for k, v in overrides.items():
        setattr(agent, k, v)
    return agent

Coordinate3D = Tuple[int, int, int]

@dataclass
class FireUnit:
    """A responding crew with water and tools."""
    name: str
    location: Optional[Coordinate3D] = None
    enroute: bool = False
    arrived: bool = False
    water_flow_lps: float = 8.0          # litres per second (tunable)
    stream_radius: float = 2.5           # cubes within this Euclidean radius get cooled
    vent_radius: float = 2.0
    crew_size: int = 4
    has_fans: bool = True
    has_forcible_entry: bool = True
    targets: List[Coordinate3D] = field(default_factory=list)

class FireDepartment:
    """
    High-level incident response controller.

    Expects the simulation to provide:
      - model: Dict[(x,y,z) -> Cube]
      - get_fire_state(cube) -> FireState   (must expose .heat and .burn_time, like the Sprinkler expects)
      - set_air_temp(cube, new_temp: float)
      - pathfind(start, goal) -> List[Coordinate3D]
      - exits: Iterable[Coordinate3D]       (where rescued agents are led)
    """
    def __init__(self,
                 model: Dict[Coordinate3D, "Cube"],
                 get_fire_state: Callable[["Cube"], "FireState"],
                 set_air_temp: Callable[["Cube", float], None],
                 pathfind: Callable[[Coordinate3D, Coordinate3D], List[Coordinate3D]],
                 exits: Iterable[Coordinate3D],
                 dispatch_origin: Coordinate3D = (-1, -1, 0),
                 default_response_time_s: float = 240.0,
                 probabilistic: bool = False):
        self.model = model
        self.get_fire_state = get_fire_state
        self.set_air_temp = set_air_temp
        self.pathfind = pathfind
        self.exits = list(exits)
        self.dispatch_origin = dispatch_origin
        self.default_response_time_s = default_response_time_s

        self.units: List[FireUnit] = []
        self._eta: Dict[str, float] = {}   # unit_name -> seconds until arrival
        self.active_incident: bool = False
        self.command_mode: str = "investigative"  # "offensive" | "defensive" | "investigative"

        self.demob_cooldown_s = 60.0  # seconds to wait with no active fire
        self._no_fire_accum = 0.0

        # History functionality.
        self.action_log: list[dict] = []
        self._last_telemetry: dict | None = None
        self._last_forced_entries: int = 0

        # Probabilistic attributes.
        self.probabilistic = bool(probabilistic)
        if self.probabilistic:
            # default lognormal: mean = default_response_time_s, std = 60s (tweak as you like)
            self._eta_sampler = lognormal_sampler(
                mean=self.default_response_time_s,
                std=60.0)
        else:
            self._eta_sampler = None

def receive_alarm(
    self,
    alarm_coords: List[Coordinate3D],
    now_s: float,
    create_units: Optional[Callable[[], List[FireUnit]]] = None
) -> None:
    """
    Called when smoke alarms trip or a manual call is made.
    Plan initial dispatch and set ETAs (probabilistic if enabled).
    """
    if self.active_incident:
        return
    self.active_incident = True
    self.command_mode = "offensive"
    self.units = create_units() if create_units else [FireUnit(name="Engine 1")]
    for u in self.units:
        u.location = self.dispatch_origin
        u.enroute = True
        u.arrived = False

        # Either constant or probabilistic.
        self._eta[u.name] = self._draw_eta_seconds()

        # crude initial target: nearest alarm
        if alarm_coords:
            u.targets = [self._nearest(u.location, alarm_coords)]


def cancel_incident(self):
    self.active_incident = False
    self.command_mode = "investigative"
    self.units.clear()
    self._eta.clear()

def step(self, dt_s: float, now_s: float, verbose: bool = False) -> None:
    """
    Advance unit ETAs, move units if they have paths, then apply tactics:
    suppression, open egress points, search & rescue.

    Adds:
      - opportunistic retargeting to other active-fire coordinates for idle units
      - auto-demobilization after 'demob_cooldown_s' with zero active fire
      - telemetry logging in self.action_log (per-tick)
    """
    if not self.active_incident:
        return

    # init demob accumulator & telemetry (once)
    if not hasattr(self, "_no_fire_accum"):
        self._no_fire_accum = 0.0
    if not hasattr(self, "action_log"):
        self.action_log = []
    if not hasattr(self, "_last_forced_entries"):
        self._last_forced_entries = 0

    # --- arrival accounting ---
    for u in self.units:
        if u.enroute and not u.arrived:
            self._eta[u.name] = max(0.0, self._eta[u.name] - dt_s)
            if self._eta[u.name] == 0.0:
                u.enroute = False
                u.arrived = True
                # Once arrived, try to path to first target immediately
                if u.targets:
                    self._ensure_path(u, u.targets[0], verbose)

    # --- move arrived units along their paths ---
    for u in self.units:
        if u.arrived and u.targets:
            self._advance_unit(u, dt_s)

    # --- opportunistic retargeting: idle units → nearest burning coord ---
    burning_coords = [coord for coord, cube in self.model.items()
                      if getattr(cube, "is_on_fire", False)]
    if burning_coords:
        for u in self.units:
            if u.arrived and not u.targets and u.location is not None:
                # pick nearest burning coordinate
                cx, cy, cz = u.location
                def _dist2(p):
                    dx, dy, dz = p[0]-cx, p[1]-cy, p[2]-cz
                    return dx*dx + dy*dy + dz*dz
                goal = min(burning_coords, key=_dist2)
                if goal != u.location:
                    self._ensure_path(u, goal, verbose)

    # --- tactics at current locations (with telemetry counts) ---
    opened_total = 0
    cooled_total = 0
    helped_total = 0
    for u in self.units:
        if u.arrived:
            # pass dt_s so suppression can scale by timestep
            cooled_total += (self._apply_suppression(u, dt_s=dt_s) or 0)
            opened_total += (self._open_nearby_egress_points(u) or 0)
            helped_total += (self._do_search_and_rescue(u) or 0)

    forced = int(getattr(self, "_last_forced_entries", 0))

    # Snapshot unit states for telemetry BEFORE any potential demobilization
    unit_states = [{
        "name": u.name,
        "location": tuple(u.location) if u.location is not None else None,
        "enroute": bool(u.enroute),
        "arrived": bool(u.arrived),
        "eta": self._eta.get(u.name, None),
        "targets_remaining": len(u.targets or []),
    } for u in self.units]

    telemetry = {
        "time": now_s,
        "opened_egress": int(opened_total),
        "cooled_cubes": int(cooled_total),
        "agents_helped": int(helped_total),
        "force_entries": forced,
        "unit_states": unit_states,
        "command_mode": getattr(self, "command_mode", None),
        "active_incident": bool(self.active_incident),
    }
    self._last_telemetry = telemetry
    self.action_log.append(telemetry)
    self._last_forced_entries = 0  # reset counter after logging

    if verbose:
        try:
            print(f"[FD t={now_s}] cooled={cooled_total} opened={opened_total} "
                  f"helped={helped_total} forced={forced} units={len(self.units)}")
        except Exception:
            pass

    # --- command mode + auto-demobilize when fire is out ---
    total_active = sum(1 for c in self.model.values() if getattr(c, "is_on_fire", False))
    if total_active == 0:
        self.command_mode = "investigative"
        self._no_fire_accum += dt_s
        cooldown = float(getattr(self, "demob_cooldown_s", 60.0))  # seconds
        if self._no_fire_accum >= cooldown:
            self.cancel_incident()  # clears units/ETAs and sets active_incident=False
    else:
        self._no_fire_accum = 0.0

def _apply_suppression(self, unit: "FireUnit", dt_s: float = 1.0) -> int:
    """
    Apply water stream to burning components that are REACHABLE via hollow/degraded
    interfaces within `stream_radius` adjacency steps. Reduces per-object heat
    output (kJ) and quenches when cooled below a threshold.
    Returns number of components affected (for telemetry).
    """
    if unit.location is None:
        return 0

    # Tunables
    steps = max(0, int(math.ceil(float(getattr(unit, "stream_radius", 2.0)))))  # BFS steps
    flow_lps = float(getattr(unit, "water_flow_lps", 6.0))                      # L/s
    kj_per_liter = float(getattr(self, "suppression_kj_per_liter", 200.0))      # kJ/L
    q_eps = float(getattr(self, "quench_output_threshold", 1.0))                # kJ/tick to consider out

    water_kj_available = kj_per_liter * flow_lps * dt_s
    if water_kj_available <= 0.0:
        return 0

    # Determine which cubes are reachable through passable boundaries
    if hasattr(self, "_reachable_cubes_within"):
        coords = self._reachable_cubes_within(unit.location, max_steps=steps)
    else:
        # Fallback: Euclidean radius if BFS helper isn't bound
        def _euclid(a, b):
            return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5
        r = float(getattr(unit, "stream_radius", 2.0))
        coords = {coord for coord in self.model if _euclid(coord, unit.location) <= r}

    # Collect burning components in those cubes
    targets = []
    for coord in coords:
        cube = self.model.get(coord)
        if not cube:
            continue
        for obj, fb in self._iter_combustibles(cube):
            latest = float(getattr(fb, "latest_heat_output", 0.0) or 0.0)
            ignited = bool(getattr(fb, "is_ignited", False))
            if ignited or latest > 0.0:
                targets.append((cube, fb, latest))

    if not targets:
        return 0

    # Evenly distribute available water energy
    share = water_kj_available / len(targets)
    affected = 0

    for cube, fb, latest in targets:
        quench = getattr(fb, "quench_by_energy", None)
        if callable(quench):
            try:
                quench(share)
            except Exception:
                pass
            latest = float(getattr(fb, "latest_heat_output", 0.0) or 0.0)
        else:
            new_latest = max(0.0, latest - share)
            try:
                setattr(fb, "latest_heat_output", new_latest)
            except Exception:
                pass
            latest = new_latest

        if latest <= q_eps and hasattr(fb, "is_ignited"):
            try:
                fb.is_ignited = False
            except Exception:
                pass

        if hasattr(cube, "extinguish_inactive_surfaces"):
            cube.extinguish_inactive_surfaces()
        if hasattr(cube, "refresh_fire_flag"):
            cube.refresh_fire_flag()

        affected += 1

    return affected

def _open_nearby_egress_points(self, unit: FireUnit) -> int:
    """
    Assist egress: open nearby doors/windows that are UNLOCKED and not blocked.
    This does not model any airflow/heat/smoke effects—just makes exits usable.
    Radius can be tuned per-unit via `unit.vent_radius` (fallback 1.5).
    """
    if unit.location is None:
        return 0
    r = float(getattr(unit, "vent_radius", 1.5))
    opened_count = 0
    for cube in self._adjacent_cubes(unit.location, r=r):
        surfaces = cube.get_all_surfaces() if hasattr(cube, "get_all_surfaces") else []
        for surface in surfaces:
            for item in (getattr(surface, "items", []) or []):
                if getattr(item, "access_type", None) not in {"window", "door"}:
                    continue
                if getattr(item, "is_open", False):
                    continue
                if getattr(item, "is_locked", False) or getattr(item, "is_blocked", False):
                    continue
                op = getattr(item, "open", None)
                try:
                    op() if callable(op) else setattr(item, "is_open", True)
                except Exception:
                    setattr(item, "is_open", True)
                opened_count += 1
    self._last_egress_opened = opened_count
    return opened_count


def _do_search_and_rescue(self, unit: FireUnit) -> int:
    """
    Nudge nearby Agents toward exits; if an agent has no path, plan one.
    """
    agents: Iterable["Agent"] = getattr(self, "agents", [])
    if unit.location is None or not agents:
        return 0
    helped = 0
    for a in agents:
        if not a.alive:
            continue
        if self._euclidean(a.location, unit.location) <= 2.0:
            a.is_evacuating = True
            if not a.path:
                exit_goal = self._nearest(a.location, self.exits) if self.exits else a.location
                a.path = self.pathfind(a.location, exit_goal)
            helped += 1
    return helped

def force_entry(self, coord: Coordinate3D) -> int:
    """
    Break locks/blocked state on doors/windows at a coordinate (if present).
    """
    cube = self.model.get(coord)
    if not cube:
        return 0
    n = 0
    for surface in cube.get_all_surfaces():
        for item in getattr(surface, "items", []) or []:
            if getattr(item, "access_type", None) in {"door", "window"}:
                if getattr(item, "is_locked", False) or getattr(item, "is_blocked", False):
                    item.is_locked = False
                    item.is_blocked = False
                    item.open()
                    n += 1
    self._last_forced_entries = getattr(self, "_last_forced_entries", 0) + n
    return n


def _ensure_path(self, unit: FireUnit, goal: Coordinate3D, verbose=False):
    if unit.location is None:
        return
    unit.targets = self.pathfind(unit.location, goal)

def _advance_unit(self, unit: FireUnit, dt_s: float) -> None:
    """
    Walk the unit along its planned path at 1 cell/sec (tunable later).
    """
    if not unit.targets:
        return
    # simple step: pop next waypoint per second
    travel_budget = dt_s
    while travel_budget > 0.0 and unit.targets:
        next_wp = unit.targets[0]
        if next_wp == unit.location:
            unit.targets.pop(0)
            continue
        unit.location = next_wp
        travel_budget -= 1.0  # 1 cell per second

def _iter_combustibles(self, cube):
    """
    Yield (obj, fb) pairs for any object on/in this cube that has a fire_behavior.
    Includes loose items, surface-mounted items, and single cover_material if present.
    """
    # 1) items placed in the cube
    for it in (getattr(cube, "items", []) or []):
        fb = getattr(it, "fire_behavior", None)
        if fb is not None:
            yield it, fb

    # 2) surfaces and their mounted items / single cover_material
    surfaces = cube.get_all_surfaces() if hasattr(cube, "get_all_surfaces") else []
    for s in surfaces:
        # mounted items (e.g., furniture on wall, doors/windows if they had FB)
        for it in (getattr(s, "items", []) or []):
            fb = getattr(it, "fire_behavior", None)
            if fb is not None:
                yield it, fb
        # single-cover case (common in your model)
        cm = getattr(s, "cover_material", None)
        if cm is not None:
            fb = getattr(cm, "fire_behavior", None)
            if fb is not None:
                yield cm, fb

def _adjacent_cubes(self, origin: Coordinate3D, r: float) -> List["Cube"]:
    return [cube for coord, cube in self.model.items()
            if self._euclidean(coord, origin) <= r]

def _cube_to_coord(self, cube):
    coord = getattr(cube, "coordinate", None)
    if coord is None:
        return None
    if isinstance(coord, tuple):
        return coord
    if hasattr(coord, "as_tuple"):
        return coord.as_tuple()
    try:
        return tuple(coord)
    except Exception:
        return None



def _surface_degraded(self, s) -> bool:
    """True if the surface is breached/degraded enough for water to pass."""
    if s is None:
        return False
    if hasattr(s, "degradation"):
        try:
            return float(s.degradation) <= 0.0
        except Exception:
            pass
    return False

def _boundary_allows_water(self, s1, s2) -> bool:
    """
    Water can pass only if the *interface* is intentionally open (hollow)
    or physically breached/degraded. (Doors/windows being 'open' are ignored
    here per your spec.)
    """
    if s1 is None or s2 is None:
        return False
    if getattr(s1, "hollow", False) or getattr(s2, "hollow", False):
        return True
    if self._surface_degraded(s1) or self._surface_degraded(s2):
        return True
    return False

def _reachable_cubes_within(self, start_coord, max_steps: int):
    """
    BFS over surface_neighbor links, requiring passable boundaries.
    max_steps counts *edges* (Manhattan distance), not Euclidean radius.
    """
    if start_coord is None:
        return set()
    visited = {start_coord}
    q = deque([(start_coord, 0)])
    while q:
        coord, d = q.popleft()
        if d >= max_steps:
            continue
        cube = self.model.get(coord)
        if not cube:
            continue
        # prefer named faces (they carry surface_neighbor)
        for name in ("left_wall","right_wall","front_wall","back_wall","floor","ceiling"):
            if not hasattr(cube, name):
                continue
            s1 = getattr(cube, name)
            s2 = getattr(s1, "surface_neighbor", None)
            cb = getattr(s2, "cube", None) if s2 is not None else None
            if s2 is None or cb is None:
                continue
            if not self._boundary_allows_water(s1, s2):
                continue
            nb = self._cube_to_coord(cb)
            if nb is None or nb in visited:
                continue
            visited.add(nb)
            q.append((nb, d + 1))
    return visited

# ----------- Probabilistic method helpers --------------------
def _draw_eta_seconds(self) -> float:
    """Sample (or return) one ETA in seconds according to current settings."""
    if self.probabilistic:
        return float(self._eta_sampler(size=1)[0])
    else:
        return self.default_response_time_s

@staticmethod
def _euclidean(a: Coordinate3D, b: Coordinate3D) -> float:
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5

@staticmethod
def _nearest(ref: Coordinate3D, coords: List[Coordinate3D]) -> Coordinate3D:
    return min(coords, key=lambda c: ((c[0]-ref[0])**2 + (c[1]-ref[1])**2 + (c[2]-ref[2])**2))

# Incident lifecycle
FireDepartment.receive_alarm = receive_alarm
FireDepartment.cancel_incident = cancel_incident

# Simulation tick integration
FireDepartment.step = step

# Tactics
FireDepartment._apply_suppression = _apply_suppression
FireDepartment._open_nearby_egress_points = _open_nearby_egress_points
FireDepartment._do_search_and_rescue = _do_search_and_rescue

# Utilities
FireDepartment.force_entry = force_entry
FireDepartment._ensure_path = _ensure_path
FireDepartment._advance_unit = _advance_unit
FireDepartment._iter_combustibles = _iter_combustibles
FireDepartment._adjacent_cubes = _adjacent_cubes
FireDepartment._cube_to_coord = _cube_to_coord
FireDepartment._surface_degraded = _surface_degraded
FireDepartment._boundary_allows_water = _boundary_allows_water
FireDepartment._reachable_cubes_within = _reachable_cubes_within
FireDepartment._draw_eta_seconds = _draw_eta_seconds
FireDepartment._euclidean = _euclidean
FireDepartment._nearest = _nearest

from typing import Optional, Tuple, Dict, List, Callable
from abc import ABC, abstractmethod
import random

Coord = Tuple[int, int, int]

# ---------------------------------------------------------------------------
# Minimalist movement framework
# ---------------------------------------------------------------------------

class Movement(ABC):
    """
    Strategy object:
      - Owns goal selection + pause logic
      - Proposes the *next* waypoint (single step) each tick
      - Agent/Sim still enforce gates via Agent.can_pass_between(...)
    """
    @abstractmethod
    def next_waypoint(self, agent: "Agent", sim: "FireSimulation") -> Optional[Coord]:
        ...

# ---------------------------------------------------------------------------
# Utilities (kept tiny)
# ---------------------------------------------------------------------------

def _adjacent_coords(c: Coord) -> List[Coord]:
    x, y, z = c
    return [(x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)]

# ---------------------------------------------------------------------------
# Weighted goal selection by agent role + rooms (now uses agent-provided weights)
# ---------------------------------------------------------------------------

class WeightedTargetSelector:
    """
    Picks a target coord by:
      1) Selecting a room-category using weights (from a provider or a dict)
      2) Picking a random coord from that category

    catalog: {category: [coords...]}  (must be pre-populated)
    role_weights (optional): {role: {category: weight, ...}}
    weights_provider (optional): callable(role, categories, agent) -> {category: weight}
      - If provided, it overrides role_weights and can pull weights from the agent object
        (e.g., agent.room_target_weights[agent.role]).
    """
    def __init__(
        self,
        catalog: Dict[str, List[Coord]],
        role_weights: Optional[Dict[str, Dict[str, float]]] = None,
        weights_provider: Optional[Callable[[str, List[str], Optional["Agent"]], Dict[str, float]]] = None,
    ):
        self.catalog = {k: list(v) for k, v in catalog.items() if v}
        self.role_weights = {k: dict(v) for k, v in (role_weights or {}).items()}
        self.weights_provider = weights_provider

    def _weights_for(self, role: str, cats: List[str], agent: Optional["Agent"]) -> Dict[str, float]:
        # Provider wins
        if callable(self.weights_provider):
            try:
                w = self.weights_provider(role, cats, agent) or {}
                return {c: float(w.get(c, 0.0)) for c in cats}
            except Exception:
                pass

        # Static dict fallback
        w = self.role_weights.get(role) or self.role_weights.get("default") or {}
        return {c: float(w.get(c, 0.0)) for c in cats}

    def pick(self, role: str, agent: Optional["Agent"] = None) -> Optional[Coord]:
        if not self.catalog:
            return None
        cats = list(self.catalog.keys())
        weights_map = self._weights_for(role, cats, agent)
        ws = [max(0.0, weights_map.get(cat, 0.0)) for cat in cats]
        if sum(ws) <= 0.0:
            ws = [1.0] * len(cats)  # uniform fallback
        chosen_cat = random.choices(cats, weights=ws, k=1)[0]
        coords = self.catalog.get(chosen_cat) or []
        return random.choice(coords) if coords else None

# ---------------------------------------------------------------------------
# Goal‑oriented random walk with pause + re‑target + unreachable fallback
# ---------------------------------------------------------------------------

class GoalOrientedRandomWalk(Movement):
    """
    Minimal behavior set:
      (1) Goal orientation using WeightedTargetSelector (reads agent weights)
      (2) Random walk steps respecting Agent.can_pass_between
      (3) Pause at target for N ticks, then reassign a new target
      (4) Detect unreachable targets and reassign
      (5) Hook for environmental modifiers (blueprint)

    How to wire in sim loop (inside _process_agent_movement):
        if (not agent.path or len(agent.path) < 2) and agent.movement:
            nxt = agent.movement.next_waypoint(agent, self)
            if nxt and nxt != agent.location:
                agent.path = [agent.location, nxt]
    """
    def __init__(self,
                 target_selector: Optional[WeightedTargetSelector] = None,
                 dwell_ticks: int = 10,
                 reassign_after_ticks: int = 300,
                 prefer_cooler: float = 0.5,
                 avoid_backtrack: float = 0.6,
                 max_air_temp: float = 150.0,
                 validate_path: bool = True,
                 max_stuck_ticks: int = 10,
                 policy_passthrough: Optional[Dict[str, object]] = None,
                 env_effects: Optional[Callable[["Agent", "FireSimulation", dict], dict]] = None):
        self.selector = target_selector
        self.dwell_ticks_cfg = max(0, int(dwell_ticks))
        self.reassign_after = max(1, int(reassign_after_ticks))
        self.prefer_cooler = float(prefer_cooler)
        self.avoid_backtrack = float(avoid_backtrack)
        self.max_air_temp = float(max_air_temp)
        self.validate_path = bool(validate_path)
        self.max_stuck = int(max_stuck_ticks)
        self.policy_passthrough = policy_passthrough or {}
        self.env_effects = env_effects  # blueprint hook

        # State
        self._goal: Optional[Coord] = None
        self._pause_left: int = 0
        self._last: Optional[Coord] = None
        self._ticks_since_progress: int = 0
        self._assigned_at_simt: Optional[int] = None

    def next_waypoint(self, agent: "Agent", sim: "FireSimulation") -> Optional[Coord]:
        self._apply_environment(agent, sim)

        if self._pause_left > 0:
            self._pause_left -= 1
            return None

        if self._need_new_goal(sim):
            self._assign_new_goal(agent, sim)
            if self._goal is None:
                return None

        if agent.location == self._goal:
            self._pause_left = self.dwell_ticks_cfg
            self._goal = None
            return None

        nxt = self._random_biased_step(agent, sim)
        if nxt is None:
            self._ticks_since_progress += 1
            if self._ticks_since_progress >= self.max_stuck:
                self._assign_new_goal(agent, sim)
            return None

        self._ticks_since_progress = 0
        self._last = agent.location
        return nxt

    # --- internals ---
    def _need_new_goal(self, sim: "FireSimulation") -> bool:
        if self._goal is None:
            return True
        if self._assigned_at_simt is None:
            return True
        return (getattr(sim, "time", 0) - self._assigned_at_simt) >= self.reassign_after

    def _assign_new_goal(self, agent: "Agent", sim: "FireSimulation") -> None:
        self._goal = None
        self._assigned_at_simt = getattr(sim, "time", 0)

        cand = None
        if self.selector is not None:
            cand = self.selector.pick(getattr(agent, "role", "default"), agent=agent)
        if cand is None and sim.global_model:
            cand = random.choice(list(sim.global_model.keys()))

        if cand is not None and self.validate_path:
            path = self._quick_path(sim, agent.location, cand)
            if not path:
                for _ in range(10):
                    alt = self.selector.pick(getattr(agent, "role", "default"), agent=agent) if self.selector else None
                    if alt is None:
                        break
                    path = self._quick_path(sim, agent.location, alt)
                    if path:
                        cand = alt
                        break
                else:
                    cand = None

        self._goal = cand

    def _quick_path(self, sim: "FireSimulation", a: Coord, b: Coord) -> List[Coord]:
        pf = getattr(sim, "_pathfind", None)
        if callable(pf):
            try:
                return list(pf(a, b))
            except Exception:
                pass
        if sum(abs(x-y) for x, y in zip(a, b)) == 1:
            return [b]
        return []

    def _random_biased_step(self, agent: "Agent", sim: "FireSimulation") -> Optional[Coord]:
        here = agent.location
        options: List[Coord] = []

        options.extend(_adjacent_coords(here))
        cube = sim.global_model.get(here)
        if cube is not None and hasattr(cube, "get_all_surfaces"):
            for s in cube.get_all_surfaces():
                for it in (getattr(s, "items", []) or []):
                    to = getattr(it, "leads_to", None)
                    if to is not None and not getattr(it, "is_blocked", False):
                        options.append(to)

        legal: List[Coord] = []
        for c in options:
            if c not in sim.global_model:
                continue
            ok, _ = agent.can_pass_between(
                sim.global_model, here, c,
                policy={
                    "avoid_fire": True,
                    "max_air_temp": self.max_air_temp,
                    "auto_open_doors": True,
                    "auto_unlock_doors": True,
                    **self.policy_passthrough,
                },
            )
            if ok:
                legal.append(c)

        if not legal:
            return None

        temps = [float(sim.global_model[c].air_temp) for c in legal]
        cool = [1.0 / (t + 1e-3) for t in temps]
        s = sum(cool) or 1.0
        cool_norm = [c / s for c in cool]
        w = [1.0 * (1.0 - self.prefer_cooler) + self.prefer_cooler * cn for cn in cool_norm]
        if self._last is not None and self.avoid_backtrack > 0:
            for i, c in enumerate(legal):
                if c == self._last:
                    w[i] *= (1.0 - self.avoid_backtrack)
        w = [max(1e-6, wi) for wi in w]

        return random.choices(legal, weights=w, k=1)[0]

    # -------------------------------------------------------------------
    # Environmental effects blueprint
    # -------------------------------------------------------------------
    def _apply_environment(self, agent: "Agent", sim: "FireSimulation") -> None:
        if not callable(self.env_effects):
            return
        try:
            overrides = self.env_effects(agent, sim, {
                "goal": self._goal,
                "pause_left": self._pause_left,
                "assigned_at": self._assigned_at_simt,
            }) or {}
        except Exception:
            return

        if "max_air_temp" in overrides:
            self.max_air_temp = float(overrides["max_air_temp"])
        if "prefer_cooler" in overrides:
            self.prefer_cooler = float(overrides["prefer_cooler"])
        if "dwell_ticks" in overrides:
            self.dwell_ticks_cfg = int(overrides["dwell_ticks"])
        if "reassign_after" in overrides:
            self.reassign_after = int(overrides["reassign_after"])
        if "selector" in overrides and isinstance(overrides["selector"], WeightedTargetSelector):
            self.selector = overrides["selector"]

# ---------------------------------------------------------------------------
# Convenience wiring for Agent (optional helpers)
# ---------------------------------------------------------------------------

def agent_set_movement(agent: "Agent", movement: Movement) -> None:
    """Attach a movement strategy to an agent (tiny helper)."""
    setattr(agent, "movement", movement)

def ensure_movement_hook_in_sim(sim: "FireSimulation") -> None:
    """
    Monkey-patch _process_agent_movement to consume single-step waypoints
    from any Movement strategy attached to agents.
    """
    if hasattr(sim, "_movement_hook_installed") and getattr(sim, "_movement_hook_installed"):
        return

    orig = getattr(sim, "_process_agent_movement")

    def wrapped(verbose: bool):
        for agent in getattr(sim, "agents", []) or []:
            if not getattr(agent, "alive", True):
                continue
            if (not getattr(agent, "path", None) or len(agent.path) < 2) and getattr(agent, "movement", None):
                nxt = agent.movement.next_waypoint(agent, sim)
                if nxt is not None and nxt != agent.location:
                    agent.path = [agent.location, nxt]
        return orig(verbose)

    setattr(sim, "_process_agent_movement", wrapped)
    setattr(sim, "_movement_hook_installed", True)

# ---------------------------------------------------------------------------
# Helper: build a selector that uses per-agent .room_target_weights
# ---------------------------------------------------------------------------

def make_selector_using_agent_weights(rooms_by_category: Dict[str, List[Coord]]) -> WeightedTargetSelector:
    """
    Uses agent.room_target_weights[agent.role] when available; otherwise uniform.
    Expected agent schema:
        agent.room_target_weights = {
            agent.role: { "downstairs_storage": 7, "upstairs_open_area": 5, ... }
        }
    """
    def provider(role: str, categories: List[str], agent: Optional["Agent"]) -> Dict[str, float]:
        default = {c: 1.0 for c in categories}
        if agent is None:
            return default
        weights_map = getattr(agent, "room_target_weights", {}) or {}
        role_map = weights_map.get(role, {})
        out = {c: float(role_map.get(c, 0.0)) for c in categories}
        if sum(out.values()) <= 0.0:
            return default
        return out

    return WeightedTargetSelector(
        catalog=rooms_by_category,
        role_weights=None,
        weights_provider=provider
    )



# ---------------------------------------------------------------------------
# Default/demo agent factories
# ---------------------------------------------------------------------------

def create_john_janitor(room_catalogue):
    """Create the default janitor agent used in example simulations."""
    john_janitor = create_agent("janitor")
    john_janitor.location = (1, 2, 0)

    selector = make_selector_using_agent_weights(room_catalogue)
    john_janitor.movement = GoalOrientedRandomWalk(
        target_selector=selector,
        dwell_ticks=10,
        reassign_after_ticks=200,
        prefer_cooler=0.6,
        avoid_backtrack=0.7,
    )
    return john_janitor


def create_office_elin():
    """Create the default office staff agent used in example simulations."""
    office_elin = create_agent("office_staff")
    office_elin.location = (2, 0, 0)
    office_elin.path = [(3, 0, 0), (4, 0, 0), (4, 1, 0)]
    return office_elin


def create_default_agents(room_catalogue):
    """Create all default agents for the sample simulation."""
    return [create_john_janitor(room_catalogue), create_office_elin()]
