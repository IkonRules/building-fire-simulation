"""Data extraction and plotting helpers for recorded simulation history."""

import os
from typing import Dict, Tuple, List, Optional, Iterable, Union
import pickle
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, LinearSegmentedColormap
from matplotlib import colormaps
import pandas as pd

from fire_building_sim.config import DATA_DIR

Coord = Tuple[int, int, int]

from fire_building_sim.domain import (
    Cube, Item
)

from fire_building_sim.building_factory import (
    find_room_objects, draw_cube_faces
)

from fire_building_sim.fire_simulation import (
    FireSimulation
)


# Define paths
data_path = str(DATA_DIR)
global_model_path = os.path.join(data_path, "global_model.pkl")
room_catalogue_path = os.path.join(data_path, "room_catalogue.pkl")

def load_from_pickle(filepath):
    with open(filepath, 'rb') as f:
        return pickle.load(f)

def save_to_pickle(obj, filepath):
    with open(filepath, 'wb') as f:
        pickle.dump(obj, f)

def _burning_coords_from_snapshot(snapshot: dict, epsilon_kJ: float = 1e-6):
    """
    Return a list of coords that are actively releasing heat in this snapshot,
    based on latest_heat_output from items and surface covers.
    """
    comps = snapshot.get("components") or {}
    burning = []
    for coord, block in comps.items():
        # Items
        any_heat = any((it.get("latest_heat_output") or 0.0) > epsilon_kJ
                       for it in (block.get("items") or []))
        # Surface covers
        if not any_heat:
            for s in (block.get("surfaces") or {}).values():
                if any((cov.get("latest_heat_output") or 0.0) > epsilon_kJ
                       for cov in (s.get("covers") or [])):
                    any_heat = True
                    break
        if any_heat:
            burning.append(coord)
    return burning

def display_burning_cubes(sim: FireSimulation, max_steps: Optional[int] = None):
    if not getattr(sim, "history", None):
        print("No history recorded.")
        return

    ticks = sorted(sim.history.keys())
    if max_steps is not None:
        ticks = ticks[-max_steps:]

    if len(ticks) >= 2:
        inferred_interval = ticks[1] - ticks[0]
    else:
        inferred_interval = getattr(sim, "snapshot_interval", 1)
    total_ticks = getattr(sim, "time", ticks[-1] if ticks else 0)

    print(
        f"Fire spread summary ({total_ticks} ticks total, "
        f"snapshots every ~{inferred_interval} ticks):\n"
    )

    for t in ticks:
        snapshot = sim.history[t]
        burning = _burning_coords_from_snapshot(snapshot)
        print(f"Timestep {t:4d}: {len(burning)} cubes releasing heat")
        if len(burning) <= 50:
            print(f"    {burning}")


def log_fire_state_changes(sim: FireSimulation, max_steps: Optional[int] = None):
    if not getattr(sim, "history", None):
        print("No history recorded.")
        return

    ticks = sorted(sim.history.keys())
    if max_steps is not None:
        ticks = ticks[-max_steps:]
    if len(ticks) < 2:
        print("Not enough snapshots to detect changes.")
        return

    change_log = []

    prev_burning = set(_burning_coords_from_snapshot(sim.history[ticks[0]]))
    for t in ticks[1:]:
        curr_burning = set(_burning_coords_from_snapshot(sim.history[t]))
        ignited = sorted(curr_burning - prev_burning)
        extinguished = sorted(prev_burning - curr_burning)

        if ignited:
            change_log.append((t, "IGNITED", ignited))
        if extinguished:
            change_log.append((t, "EXTINGUISHED", extinguished))

        prev_burning = curr_burning

    if change_log:
        for tick, change_type, coords in change_log:
            print(f"Timestep {tick:4d}: {change_type} → {len(coords)} cube(s)")
            print(f"    {coords}")
    else:
        print("No ignition/extinguish changes detected.")

def agent_routes(
    sim,
    tick_range: Optional[Union[Tuple[int, int], Iterable[int]]] = None,
    snapshot_field: str = "agents",
    agent_names: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Return a DataFrame of agent locations over time.
    Rows are ticks; columns are agent names; values are (x, y, z) tuples or None.

    Requirements: sim.history[t][snapshot_field] must exist and include agent 'location'.
    """

    # --- choose ticks ---
    if tick_range is None:
        ticks = sorted(k for k in sim.history.keys() if isinstance(k, int))
    elif isinstance(tick_range, tuple) and len(tick_range) == 2:
        start, end = tick_range
        ticks = list(range(start, end + 1))
    else:
        ticks = list(tick_range)

    # --- discover agent names if not provided ---
    if agent_names is None:
        names = set(getattr(a, "name", None) for a in getattr(sim, "agents", []) or [])
        # also scan history once for completeness
        for t in ticks:
            snap = sim.history.get(t, {})
            blob = snap.get(snapshot_field)
            if isinstance(blob, list):
                names.update(a.get("name") for a in blob if isinstance(a, dict))
            elif isinstance(blob, dict):
                names.update(blob.keys())
        agent_names = sorted(n for n in names if n)

    def _xyz(v):
        if isinstance(v, tuple) and len(v) == 3: return v
        if isinstance(v, list)  and len(v) == 3: return (v[0], v[1], v[2])
        return None

    # --- build rows ---
    rows = []
    for t in ticks:
        row = {"tick": t}
        snap = sim.history.get(t, {})
        blob = snap.get(snapshot_field)

        # make name -> location lookup for this tick
        by_name = {}
        if isinstance(blob, list):
            for rec in blob:
                if isinstance(rec, dict) and "name" in rec:
                    by_name[rec["name"]] = _xyz(rec.get("location"))
        elif isinstance(blob, dict):
            for nm, rec in blob.items():
                if isinstance(rec, dict):
                    by_name[nm] = _xyz(rec.get("location"))

        for nm in agent_names:
            row[nm] = by_name.get(nm)
        rows.append(row)

    df = pd.DataFrame(rows).set_index("tick").sort_index()
    return df

def fd_actions_dataframe(sim, tick_range=None):
    """
    Build a tidy DataFrame of Fire Department actions over time.
    Rows are per unit per tick with telemetry attached.
    """
    rows = []
    t_min, t_max = (None, None)
    if tick_range is not None:
        t_min, t_max = tick_range

    for t in sorted(getattr(sim, "history", {}).keys()):
        if t_min is not None and t < t_min:
            continue
        if t_max is not None and t > t_max:
            continue
        snap = sim.history.get(t, {})
        fd = snap.get("fire_department")
        if not fd:
            continue
        opened = fd.get("opened_egress", 0)
        cooled = fd.get("cooled_cubes", 0)
        helped = fd.get("agents_helped", 0)
        forced = fd.get("force_entries", 0)
        cmd = fd.get("command_mode")
        active = fd.get("active_incident", False)
        for us in (fd.get("unit_states") or []):
            rows.append({
                "tick": t,
                "unit": us.get("name"),
                "enroute": us.get("enroute"),
                "arrived": us.get("arrived"),
                "eta": us.get("eta"),
                "location": tuple(us["location"]) if us.get("location") is not None else None,
                "targets_remaining": us.get("targets_remaining"),
                # telemetry (same per unit at this tick; convenient for slicing)
                "opened_egress": opened,
                "cooled_cubes": cooled,
                "agents_helped": helped,
                "force_entries": forced,
                "command_mode": cmd,
                "active_incident": active,
            })
    return pd.DataFrame(rows)

def calculate_inventory_loss(sim: FireSimulation, global_model: Dict[Tuple[int, int, int], Cube]) -> float:
    """
    Sum value of flammable items whose FireBehavior is (or was) active.
    No dependency on cube fire flag.
    """
    total_loss = 0.0
    for coord, cube in global_model.items():
        if not cube or not getattr(cube, "items", None):
            continue
        for item in cube.items:
            fb = getattr(item, "fire_behavior", None)
            if isinstance(item, Item) and item.flammable and fb:
                # Prefer new helper if present
                if hasattr(fb, "is_active"):
                    active = fb.is_active()
                else:
                    # Fallback heuristic
                    active = bool(getattr(fb, "is_ignited", False) or
                                  (0.0 < float(getattr(fb, "released_energy", 0.0)) <
                                         float(getattr(fb, "total_energy", 0.0))))
                if active:
                    total_loss += float(getattr(item, "value", 0.0))
    return total_loss

def visualize_building(global_model: Dict[Tuple[int, int, int], Cube]):
    """Visualize cubes and color rooms based on their size. Returns fig, ax for overlay support."""
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    rooms = find_room_objects(global_model)  # <-- patched to use Room objects
    norm = Normalize(vmin=2, vmax=40)
    cmap = colormaps["RdYlGn_r"]

    for room in rooms:
        room_size = len(room.cube_coords)
        color = 'skyblue' if room_size == 1 else cmap(norm(room_size))
        alpha = 0.3 if room_size == 1 else 0.8

        for coord in room.cube_coords:
            cube = global_model[coord]

            def face_alpha(surface):
                return 0.05 if getattr(surface, "hollow", False) else alpha

            face_alphas = [
                face_alpha(cube.floor),         # bottom
                face_alpha(cube.ceiling),       # top
                face_alpha(cube.front_wall),    # front
                face_alpha(cube.back_wall),     # back
                face_alpha(cube.right_wall),    # right
                face_alpha(cube.left_wall),     # left
            ]

            x, y, z = coord
            draw_cube_faces(ax, x, y, z, face_alphas=face_alphas, size=1, color=color)

            ax.text(x + 0.5, y + 0.5, z + 0.5, f"{x},{y},{z}",
                    color='black', ha='center', va='center', fontsize=8)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    if global_model:
        xs, ys, zs = zip(*global_model.keys())
        ax.set_xlim(min(xs) - 1, max(xs) + 2)
        ax.set_ylim(min(ys) - 1, max(ys) + 2)
        ax.set_zlim(min(zs) - 1, max(zs) + 2)

    ax.set_title("Room Size Visualization (Color: Small → Large)")
    plt.tight_layout()
    return fig, ax


def visualize_building_with_fire(sim: FireSimulation, global_model: Dict[Coord, Cube], timestep: int):
    if not isinstance(sim.history, dict) or not sim.history:
        raise ValueError("No snapshots available in sim.history (expected a non-empty dict).")

    saved_ticks = sorted(sim.history.keys())
    if timestep in sim.history:
        tick_key = timestep
        snap_index = saved_ticks.index(tick_key)
    else:
        if timestep < 0 or timestep >= len(saved_ticks):
            raise IndexError(f"Timestep {timestep} is out of bounds (only {len(saved_ticks)} snapshots).")
        tick_key = saved_ticks[timestep]
        snap_index = timestep

    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    rooms = find_room_objects(global_model)
    norm = Normalize(vmin=2, vmax=40)
    cmap = colormaps["RdYlGn_r"]

    # Base room drawing
    for room in rooms:
        room_size = len(room.cube_coords)
        base_color = 'skyblue' if room_size == 1 else cmap(norm(room_size))
        alpha = 0.3 if room_size == 1 else 0.6
        for coord in room.cube_coords:
            cube = global_model[coord]
            def face_alpha(surface):
                return 0.05 if getattr(surface, "hollow", False) else alpha
            face_alphas = [
                face_alpha(cube.floor),
                face_alpha(cube.ceiling),
                face_alpha(cube.front_wall),
                face_alpha(cube.back_wall),
                face_alpha(cube.right_wall),
                face_alpha(cube.left_wall),
            ]
            x, y, z = coord
            draw_cube_faces(ax, x, y, z, face_alphas=face_alphas, size=1, color=base_color)

    # ---- Overlay by AIR TEMPERATURE (°C), but ONLY for cubes marked on fire ----
    pink_cmap = LinearSegmentedColormap.from_list("hot_pink", ["mistyrose", "hotpink", "deeppink"])
    snapshot = sim.history[tick_key]
    air_map = snapshot.get("air_temp", {}) or {}
    fire_status_map = snapshot.get("fire_status", {}) or {}

    def _is_on_fire(coord):
        state = fire_status_map.get(coord)
        return bool(getattr(state, "is_on_fire", False))

    # coord -> air temperature (float), filtered to burning cubes
    temp_map_all = {coord: float(t) for coord, t in air_map.items() if t is not None}
    temp_map = {coord: temp for coord, temp in temp_map_all.items() if _is_on_fire(coord)}

    if temp_map:
        t_min = min(temp_map.values())
        t_max = max(temp_map.values())
        if t_max <= t_min:
            t_max = t_min + 1.0
        temp_norm = Normalize(vmin=t_min, vmax=t_max)

        for coord, temp_c in temp_map.items():
            x, y, z = coord
            color = pink_cmap(temp_norm(temp_c))
            draw_cube_faces(ax, x, y, z, face_alphas=[0.9] * 6, size=1, color=color)
            ax.text(x + 0.5, y + 0.5, z + 0.5, f"{int(round(temp_c))}°", color='black',
                    ha='center', va='center', fontsize=8)

    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
    ax.set_title(f"Room + Fire Visualization at Saved Tick {tick_key} (snapshot #{snap_index}) — burning cubes colored by air temp")

    xs, ys, zs = zip(*global_model.keys())
    ax.set_xlim(min(xs) - 1, max(xs) + 2)
    ax.set_ylim(min(ys) - 1, max(ys) + 2)
    ax.set_zlim(min(zs) - 1, max(zs) + 2)

    plt.tight_layout()
    plt.show()

def plot_air_temp_in_cubes(sim, coords, tick_range: Optional[Tuple[int, int]] = None):
    if isinstance(coords, tuple) and not hasattr(coords[0], "__iter__"):
        coords = [coords]
    else:
        coords = list(coords)

    ticks_all = sorted(sim.history.keys())
    ticks = [t for t in ticks_all if (tick_range is None or (tick_range[0] <= t <= tick_range[1]))]
    if not ticks:
        raise ValueError("No ticks found in the specified range.")

    plt.figure(figsize=(10, 6))

    for coord in coords:
        temps = []
        for t in ticks:
            air_temp_map = sim.history[t].get("air_temp", {})
            val = air_temp_map.get(coord)
            temps.append(float(val) if val is not None else float('nan'))
        plt.plot(ticks, temps, linewidth=2, label=f"{coord}")

    plt.title("Air Temperature over Time in Selected Cubes")
    plt.xlabel("Tick"); plt.ylabel("Air Temperature (°C)")
    plt.legend(title="Cube Coordinates", loc="best")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout()
    plt.show()

def plot_item_energy_left_in_cube(
    sim,
    coord: Tuple[int, int, int],
    tick_range: Optional[Tuple[int, int]] = None,
    include_surfaces: bool = True,
    include_surface_aggregate: bool = False,  # optional summed line per surface
):
    """
    Plot % energy remaining (100 -> 0) for each object in a cube:
      - loose items
      - surface *covers* (e.g., 'left_wall: particle board')
    Uses snapshot['components'] produced by the patched serializer.
    """

    # ---- select ticks
    ticks_all = sorted(sim.history.keys())
    if not ticks_all:
        raise ValueError("No snapshots available.")
    if tick_range is not None:
        lo, hi = tick_range
        ticks = [t for t in ticks_all if lo <= t <= hi]
    else:
        ticks = ticks_all
    if not ticks:
        raise ValueError("No ticks in the specified range.")

    # ---- helpers
    def snap(t) -> Dict: return sim.history[t]
    def block(t) -> Dict: return (snap(t).get("components") or {}).get(coord) or {}
    def name_of(d: Dict, fallback: str) -> str: return str(d.get("name") or d.get("class") or fallback)

    def pct_left_of(d: Dict) -> Optional[float]:
        if d.get("energy_left_pct") is not None:
            return float(d["energy_left_pct"])
        total = d.get("total_energy")
        released = d.get("released_energy")
        if total and total > 0:
            return max(0.0, min(100.0, 100.0 * (1.0 - float(released or 0.0) / float(total))))
        return None

    # ---- gather per-tick values: name -> pct_left
    per_tick = []
    all_names = set()

    for t in ticks:
        b = block(t)
        curr: Dict[str, float] = {}

        # Items
        for it in (b.get("items") or []):
            nm = name_of(it, "Item")
            pct = pct_left_of(it)
            if pct is not None:
                curr[nm] = pct

        # Surfaces -> COVERS (labels like "left_wall: particle board")
        if include_surfaces:
            for label, s in (b.get("surfaces") or {}).items():
                # one line per cover
                for cov in (s.get("covers") or []):
                    nm = f"{label}: {name_of(cov, 'Cover')}"
                    pct = pct_left_of(cov)
                    if pct is not None:
                        curr[nm] = pct

                # optional aggregate per surface (sum over covers)
                if include_surface_aggregate:
                    nm = f"{label} [surface]"
                    pct = pct_left_of(s)
                    if pct is not None:
                        curr[nm] = pct

        per_tick.append(curr)
        all_names.update(curr.keys())

    if not all_names:
        raise ValueError(
            "No items/covers found. Ensure snapshots include 'components' and surfaces have 'covers'."
        )

    # ---- align series & forward-fill from 100%
    series = {nm: [] for nm in sorted(all_names)}
    last = {nm: 100.0 for nm in all_names}
    for tv in per_tick:
        for nm in series:
            if nm in tv:
                last[nm] = float(tv[nm])
            series[nm].append(last[nm])

    # ---- plot
    plt.figure(figsize=(11, 6))
    for nm, ys in series.items():
        plt.plot(ticks, ys, linewidth=2, label=nm)

    plt.title(f"Energy Remaining per Item in Cube {coord}")
    plt.xlabel("Tick")
    plt.ylabel("Energy Remaining (%)")
    plt.ylim(0, 100)
    plt.xlim(min(ticks), max(ticks))
    plt.legend(title="Item", loc="best")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.show()

def plot_heat_output_in_cube(
    sim,
    coord: Tuple[int, int, int],
    tick_range: Optional[Tuple[int, int]] = None,
    include_surfaces: bool = True,
    include_surface_aggregate: bool = False,  # if True: also plot summed line per surface
    as_power: bool = False,                   # False => kJ per tick; True => kW (kJ/s)
    seconds_per_tick: float = 1.0
):
    """
    Plot heat output over time for each object in a cube.

    Uses serialized snapshots in:
        sim.history[t]["components"][coord] = {
            "items": [
                { "name": str, "released_energy": float, "latest_heat_output": float, ... },
                ...
            ],
            "surfaces": {
                "<label>": {
                    "name": str, "released_energy": float, "latest_heat_output": float, ...,
                    "covers": [
                        { "name": str, "released_energy": float, "latest_heat_output": float, ... },
                        ...
                    ]
                },
                ...
            }
        }

    Notes:
    - Prefers 'latest_heat_output' (kJ for this tick); falls back to Δ(released_energy) between snapshots.
    - If as_power=True, divides by seconds_per_tick to get kW.
    - Surface containers themselves typically don't burn; heat comes from their 'covers'.
    """
    # ---- select ticks
    ticks_all = sorted(sim.history.keys())
    if not ticks_all:
        raise ValueError("No snapshots available in sim.history.")
    if tick_range is not None:
        lo, hi = tick_range
        ticks = [t for t in ticks_all if lo <= t <= hi]
    else:
        ticks = ticks_all
    if not ticks:
        raise ValueError("No ticks in the specified range.")

    # ---- helpers
    def snap_at(t) -> Dict: return sim.history[t]
    def block_at(t) -> Dict: return (snap_at(t).get("components") or {}).get(coord) or {}
    def name_of(d: Dict, fallback: str) -> str: return str(d.get("name") or d.get("class") or fallback)

    # ---- seed previous released_energy for delta fallback
    first = block_at(ticks[0])
    prev_released: Dict[str, float] = {}

    # Items
    for it in (first.get("items") or []):
        nm = name_of(it, "Item")
        prev_released[nm] = float(it.get("released_energy") or 0.0)

    # Surfaces + covers (and optional aggregate)
    for label, s in (first.get("surfaces") or {}).items():
        for cov in (s.get("covers") or []):
            nm = f"{label}: {name_of(cov, 'Cover')}"
            prev_released[nm] = float(cov.get("released_energy") or 0.0)
        if include_surface_aggregate:
            sn = f"{label} [surface]"
            prev_released[sn] = float(s.get("released_energy") or 0.0)

    # ---- build per-tick heat maps (name -> kJ this tick)
    heat_maps = []
    all_names = set()

    for t in ticks:
        data = block_at(t)
        curr: Dict[str, float] = {}

        # Items
        for it in (data.get("items") or []):
            nm = name_of(it, "Item")
            if it.get("latest_heat_output") is not None:
                val_kJ = float(it["latest_heat_output"])
            else:
                curr_rel = float(it.get("released_energy") or 0.0)
                val_kJ = max(0.0, curr_rel - prev_released.get(nm, curr_rel))
                prev_released[nm] = curr_rel
            curr[nm] = val_kJ

        # Surfaces -> covers (and optional aggregate)
        if include_surfaces:
            for label, s in (data.get("surfaces") or {}).items():
                # Covers (one line per cover)
                for cov in (s.get("covers") or []):
                    nm = f"{label}: {name_of(cov, 'Cover')}"
                    if cov.get("latest_heat_output") is not None:
                        val_kJ = float(cov["latest_heat_output"])
                    else:
                        curr_rel = float(cov.get("released_energy") or 0.0)
                        val_kJ = max(0.0, curr_rel - prev_released.get(nm, curr_rel))
                        prev_released[nm] = curr_rel
                    curr[nm] = val_kJ

                # Optional aggregate per surface (sum of covers)
                if include_surface_aggregate:
                    sn = f"{label} [surface]"
                    if s.get("latest_heat_output") is not None:
                        sval_kJ = float(s["latest_heat_output"])
                    else:
                        curr_rel = float(s.get("released_energy") or 0.0)
                        sval_kJ = max(0.0, curr_rel - prev_released.get(sn, curr_rel))
                        prev_released[sn] = curr_rel
                    curr[sn] = sval_kJ

        heat_maps.append(curr)
        all_names.update(curr.keys())

    if not all_names:
        raise ValueError(
            "No components (items/covers) found for this cube. "
            "Ensure snapshots include 'components' and surfaces have 'covers'."
        )

    # ---- align series by name
    series = {nm: [] for nm in sorted(all_names)}
    for hm in heat_maps:
        for nm in series:
            series[nm].append(float(hm.get(nm, 0.0)))

    # ---- convert to power if requested
    if as_power:
        denom = max(1e-9, float(seconds_per_tick))  # 1 kJ/s = 1 kW
        for nm in series:
            series[nm] = [v / denom for v in series[nm]]

    # ---- plot
    plt.figure(figsize=(11, 6))
    for nm, ys in series.items():
        plt.plot(ticks, ys, linewidth=2, label=nm)

    unit = "kW" if as_power else "kJ per tick"
    plt.title(f"Heat Output per Object in Cube {coord}")
    plt.xlabel("Tick")
    plt.ylabel(f"Heat Output ({unit})")
    plt.xlim(min(ticks), max(ticks))
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(title="Object", loc="best")
    plt.tight_layout()
    plt.show()
