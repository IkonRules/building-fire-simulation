"""Run and visualize the deterministic portfolio scenario from the repository root."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np

from fire_building_sim.scenarios import run_sample_simulation


SEED = 2026
TICKS = 120
IGNITION_COORD = (0, 0, 0)
HISTORY_FIELDS = ("fire_status", "air_temp", "agents", "fire_department")
IMAGE_PATH = PROJECT_ROOT / "docs" / "images" / "fire_simulation_overview.png"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "example_summary.json"
AGENT_COLORS = {"John": "#ed8b24", "Elin": "#377bd1"}


def _burning_coords(snapshot):
    return [coord for coord, state in snapshot["fire_status"].items() if state.is_on_fire]


def _agent_locations(snapshot):
    return {
        agent["name"]: tuple(agent["location"])
        for agent in snapshot.get("agents", [])
        if agent.get("name") and agent.get("location") is not None
    }


def _snapshot_panel(ax, snapshot, tick, all_coords, norm):
    temps = snapshot["air_temp"]
    values = np.array([float(temps[coord]) for coord in all_coords])
    xs, ys, zs = zip(*all_coords)
    ax.scatter(
        xs,
        ys,
        zs,
        c=values,
        cmap="inferno",
        norm=norm,
        marker="s",
        s=78,
        alpha=0.82,
        edgecolors="#222222",
        linewidths=0.25,
    )

    burning = _burning_coords(snapshot)
    if burning:
        bx, by, bz = zip(*burning)
        ax.scatter(bx, by, bz, marker="o", s=155, facecolors="none", edgecolors="#00e5ff", linewidths=2.0)

    for name, coord in sorted(_agent_locations(snapshot).items()):
        ax.scatter(*coord, marker="*", s=150, color=AGENT_COLORS.get(name, "#53d769"), edgecolors="black")
        ax.text(coord[0] + 0.12, coord[1] + 0.12, coord[2] + 0.12, name, fontsize=7)

    ax.set_title(f"Saved tick {tick} | burning cells: {len(burning)}", fontsize=10, weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_zlabel("floor", labelpad=-2)
    ax.set_xticks(range(5))
    ax.set_yticks(range(5))
    ax.set_zticks([0, 1])
    ax.view_init(elev=25, azim=-52)
    ax.set_box_aspect((1, 1, 0.45))


def create_figure(sim, image_path=IMAGE_PATH):
    ticks = sorted(sim.history)
    selected = [ticks[0], ticks[len(ticks) // 3], ticks[(2 * len(ticks)) // 3], ticks[-1]]
    all_coords = sorted(sim.global_model)
    all_temps = [
        float(temp)
        for tick in ticks
        for temp in sim.history[tick]["air_temp"].values()
    ]
    norm = Normalize(vmin=20.0, vmax=max(100.0, max(all_temps)))

    fig = plt.figure(figsize=(15, 8.5), constrained_layout=True)
    grid = fig.add_gridspec(2, 4, height_ratios=(1.2, 0.8))
    for column, tick in enumerate(selected):
        _snapshot_panel(
            fig.add_subplot(grid[0, column], projection="3d"),
            sim.history[tick],
            tick,
            all_coords,
            norm,
        )

    metrics_ax = fig.add_subplot(grid[1, :2])
    max_temps = [max(float(v) for v in sim.history[t]["air_temp"].values()) for t in ticks]
    burning_counts = [len(_burning_coords(sim.history[t])) for t in ticks]
    metrics_ax.plot(ticks, max_temps, color="#d64b32", linewidth=2.4, label="Maximum cell temperature (C)")
    metrics_ax.set_xlabel("Saved tick")
    metrics_ax.set_ylabel("Maximum temperature (C)", color="#d64b32")
    metrics_ax.tick_params(axis="y", labelcolor="#d64b32")
    metrics_ax.grid(alpha=0.25)
    count_ax = metrics_ax.twinx()
    count_ax.step(ticks, burning_counts, where="post", color="#1776b6", linewidth=2.0, label="Burning cells")
    count_ax.set_ylabel("Burning cells", color="#1776b6")
    count_ax.tick_params(axis="y", labelcolor="#1776b6")
    metrics_ax.set_title("Modelled fire progression", weight="bold")

    route_ax = fig.add_subplot(grid[1, 2:])
    route_names = sorted({name for t in ticks for name in _agent_locations(sim.history[t])})
    for name in route_names:
        route = [_agent_locations(sim.history[t]).get(name) for t in ticks]
        route = [coord for coord in route if coord is not None]
        if not route:
            continue
        xs, ys, _ = zip(*route)
        color = AGENT_COLORS.get(name, "#53d769")
        route_ax.plot(xs, ys, marker="o", markersize=2.5, linewidth=1.8, label=name, color=color)
        route_ax.scatter(xs[0], ys[0], marker="s", s=70, color=color, edgecolors="black")
        route_ax.scatter(xs[-1], ys[-1], marker="*", s=130, color=color, edgecolors="black")
    route_ax.scatter(IGNITION_COORD[0], IGNITION_COORD[1], marker="X", s=120, color="#e53935", label="Ignition")
    route_ax.set_xlim(-0.5, 4.5)
    route_ax.set_ylim(-0.5, 4.5)
    route_ax.set_xticks(range(5))
    route_ax.set_yticks(range(5))
    route_ax.set_aspect("equal")
    route_ax.grid(alpha=0.25)
    route_ax.set_xlabel("x")
    route_ax.set_ylabel("y")
    route_ax.set_title("Occupant paths projected across floors", weight="bold")
    route_ax.legend(loc="upper right", fontsize=8)

    scalar = plt.cm.ScalarMappable(norm=norm, cmap="inferno")
    scalar.set_array([])
    fig.colorbar(scalar, ax=fig.axes[:4], location="bottom", shrink=0.72, pad=0.03, label="Modelled cell air temperature (C)")
    fig.suptitle(
        "Building Fire Simulation | reproducible portfolio scenario",
        fontsize=17,
        weight="bold",
    )
    fig.text(0.5, 0.005, "Synthetic exploratory output - not a validated fire-safety prediction", ha="center", fontsize=9)

    image_path = Path(image_path)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(image_path, dpi=180, facecolor="white")
    plt.close(fig)
    return selected


def main():
    sim = run_sample_simulation(
        nr_ticks=TICKS,
        start_fire_at_coord=IGNITION_COORD,
        probabilistic=True,
        save_full_history=True,
        snapshot_interval=1,
        save_history_parameters=HISTORY_FIELDS,
        fire_dept_arrival_coords=(4, 4, 0),
        fire_dept_response_time=30,
        random_seed=SEED,
    )
    selected_ticks = create_figure(sim)

    last_tick = max(sim.history)
    last_snapshot = sim.history[last_tick]
    summary = {
        "seed": SEED,
        "requested_ticks": TICKS,
        "final_simulation_time": sim.time,
        "saved_snapshots": len(sim.history),
        "visualized_ticks": selected_ticks,
        "ignition_coordinate": IGNITION_COORD,
        "maximum_modelled_air_temperature_c": round(
            max(float(v) for snapshot in sim.history.values() for v in snapshot["air_temp"].values()),
            2,
        ),
        "burning_cells_at_last_saved_tick": len(_burning_coords(last_snapshot)),
        "final_saved_agent_locations": _agent_locations(last_snapshot),
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Simulation completed at tick {sim.time} with seed {SEED}.")
    print(f"Saved {len(sim.history)} snapshots.")
    print(f"Figure: {IMAGE_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Summary: {SUMMARY_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
