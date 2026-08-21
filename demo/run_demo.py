"""Run the reproducible public demonstration and regenerate curated outputs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import warnings

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import pandas as pd

warnings.filterwarnings("ignore", message="FigureCanvasAgg is non-interactive.*")

from building_fire_simulation.fire_analysis import (
    agent_routes,
    calculate_inventory_loss,
    fd_actions_dataframe,
    plot_air_temp_in_cubes,
    plot_heat_output_in_cube,
    plot_item_energy_left_in_cube,
    visualize_building_with_fire,
)
from building_fire_simulation.scenarios import run_custom_simulation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
SEED = 2026
TICKS = 360
IGNITION_COORD = (0, 0, 0)
TEMPERATURE_COORDS = (IGNITION_COORD, (1, 0, 0), (0, 1, 0), (0, 0, 1))
HISTORY_FIELDS = (
    "fire_status",
    "air_temp",
    "components",
    "agents",
    "fire_department",
)
DISCLAIMER = "Synthetic exploratory output — not a validated fire-safety prediction."


def _burning_coords(snapshot: dict) -> list[tuple[int, int, int]]:
    return [
        coord
        for coord, state in (snapshot.get("fire_status") or {}).items()
        if bool(getattr(state, "is_on_fire", False))
    ]


def _save_current_figure(path: Path, subtitle: str | None = None) -> None:
    fig = plt.gcf()
    if subtitle:
        fig.text(0.5, 0.012, subtitle, ha="center", fontsize=9, color="#4f5660")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _first_arrival_tick(fd_actions: pd.DataFrame) -> int | None:
    if fd_actions.empty or "arrived" not in fd_actions:
        return None
    arrived = fd_actions.loc[fd_actions["arrived"] == True, "tick"]  # noqa: E712
    return None if arrived.empty else int(arrived.min())


def _progression_ticks(sim, fd_actions: pd.DataFrame) -> list[int]:
    ticks = sorted(sim.history)
    initial_count = len(_burning_coords(sim.history[ticks[0]]))
    first_spread = next(
        (tick for tick in ticks if len(_burning_coords(sim.history[tick])) > initial_count),
        ticks[len(ticks) // 3],
    )
    arrival = _first_arrival_tick(fd_actions) or ticks[(2 * len(ticks)) // 3]
    selected = [ticks[0], first_spread, arrival, ticks[-1]]

    if len(set(selected)) < 4:
        for index in (1, 2, 3):
            candidate = ticks[index * (len(ticks) - 1) // 4]
            if candidate not in selected:
                selected.append(candidate)
            if len(set(selected)) == 4:
                break
    return sorted(set(selected))[:4]


def _create_progression_figure(sim, fd_actions: pd.DataFrame) -> list[int]:
    selected_ticks = _progression_ticks(sim, fd_actions)
    with TemporaryDirectory() as temporary_directory:
        panel_paths = []
        for index, tick in enumerate(selected_ticks):
            visualize_building_with_fire(sim, sim.global_model, tick)
            panel_path = Path(temporary_directory) / f"panel_{index}.png"
            _save_current_figure(panel_path)
            panel_paths.append(panel_path)

        fig, axes = plt.subplots(2, 2, figsize=(15, 12), constrained_layout=True)
        for ax, tick, panel_path in zip(axes.flat, selected_ticks, panel_paths):
            ax.imshow(plt.imread(panel_path))
            ax.set_title(f"Saved tick {tick}", fontsize=12, weight="bold")
            ax.axis("off")
        fig.suptitle("Modelled fire progression in the sample building", fontsize=18, weight="bold")
        fig.text(0.5, 0.006, DISCLAIMER, ha="center", fontsize=9, color="#4f5660")
        fig.savefig(OUTPUT_DIR / "fire_progression.png", dpi=180, facecolor="white")
        plt.close(fig)
    return selected_ticks


def _create_analysis_figures(sim) -> None:
    plot_air_temp_in_cubes(sim, TEMPERATURE_COORDS)
    _save_current_figure(OUTPUT_DIR / "air_temperature.png", DISCLAIMER)

    plot_item_energy_left_in_cube(sim, IGNITION_COORD)
    _save_current_figure(OUTPUT_DIR / "item_energy.png", DISCLAIMER)

    plot_heat_output_in_cube(sim, IGNITION_COORD)
    _save_current_figure(OUTPUT_DIR / "item_heat_output.png", DISCLAIMER)


def _tidy_agent_routes(routes: pd.DataFrame) -> pd.DataFrame:
    records = []
    for tick, row in routes.iterrows():
        for name, location in row.items():
            if location is not None:
                records.append(
                    {
                        "tick": int(tick),
                        "agent": name,
                        "x": location[0],
                        "y": location[1],
                        "z": location[2],
                    }
                )
    return pd.DataFrame(records, columns=("tick", "agent", "x", "y", "z"))


def _released_energy(snapshot: dict) -> float:
    released = 0.0
    for block in (snapshot.get("components") or {}).values():
        for item in block.get("items") or []:
            released += float(item.get("released_energy") or 0.0)
        for surface in (block.get("surfaces") or {}).values():
            for cover in surface.get("covers") or []:
                released += float(cover.get("released_energy") or 0.0)
    return released


def _triggered_devices(sim) -> dict[str, int]:
    counts: dict[str, int] = {}
    seen: set[int] = set()
    for cube in sim.global_model.values():
        items = list(getattr(cube, "items", []) or [])
        for surface in sim._iter_all_surfaces(cube):
            items.extend(getattr(surface, "items", []) or [])
        for item in items:
            if id(item) in seen:
                continue
            seen.add(id(item))
            if hasattr(item, "triggered") and bool(item.triggered):
                name = type(item).__name__
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _summary(sim, routes: pd.DataFrame, fd_actions: pd.DataFrame, visualized_ticks: list[int]) -> dict:
    ticks = sorted(sim.history)
    peak_tick, peak_temperature = max(
        (
            (tick, max(float(value) for value in sim.history[tick]["air_temp"].values()))
            for tick in ticks
        ),
        key=lambda pair: pair[1],
    )
    ever_burning = {
        coord for tick in ticks for coord in _burning_coords(sim.history[tick])
    }
    final_locations = {
        name: list(location)
        for name, location in routes.iloc[-1].items()
        if location is not None
    }
    fd_totals = {
        column: int(fd_actions.groupby("tick")[column].first().sum())
        for column in ("opened_egress", "cooled_cubes", "agents_helped", "force_entries")
        if not fd_actions.empty and column in fd_actions
    }
    return {
        "scenario": "fixed_parameter_sample_building",
        "disclaimer": DISCLAIMER,
        "seed": SEED,
        "probabilistic_parameters": False,
        "requested_ticks": TICKS,
        "final_simulation_time": int(sim.time),
        "saved_snapshots": len(sim.history),
        "history_fields": list(HISTORY_FIELDS),
        "ignition_coordinate": list(IGNITION_COORD),
        "visualized_ticks": visualized_ticks,
        "peak_modelled_air_temperature_c": round(peak_temperature, 2),
        "peak_temperature_tick": int(peak_tick),
        "cells_ever_marked_burning": len(ever_burning),
        "burning_cells_at_last_saved_tick": len(_burning_coords(sim.history[ticks[-1]])),
        "released_combustible_energy_at_last_snapshot_kj": round(
            _released_energy(sim.history[ticks[-1]]), 2
        ),
        "triggered_safety_devices": _triggered_devices(sim),
        "first_fire_department_arrival_tick": _first_arrival_tick(fd_actions),
        "fire_department_action_totals": fd_totals,
        "final_saved_agent_locations": final_locations,
        "modelled_inventory_loss_helper_at_end": round(
            calculate_inventory_loss(sim, sim.global_model), 2
        ),
    }


def _write_summary(summary: dict) -> None:
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    device_text = ", ".join(
        f"{name}: {count}" for name, count in summary["triggered_safety_devices"].items()
    ) or "none"
    markdown = f"""# Demonstration summary

This is synthetic exploratory output from the repository's reproducible fixed-parameter sample scenario. It is not a validated fire-safety prediction.

| Measure | Recorded value |
| --- | ---: |
| Requested ticks | {summary['requested_ticks']} |
| Saved snapshots | {summary['saved_snapshots']} |
| Peak modelled cell-air temperature | {summary['peak_modelled_air_temperature_c']:.2f} °C at tick {summary['peak_temperature_tick']} |
| Cells ever marked burning | {summary['cells_ever_marked_burning']} |
| Burning cells at final saved tick | {summary['burning_cells_at_last_saved_tick']} |
| Released combustible energy at final snapshot | {summary['released_combustible_energy_at_last_snapshot_kj']:.2f} kJ |
| First fire-department arrival | tick {summary['first_fire_department_arrival_tick']} |
| Triggered safety devices | {device_text} |
| Modelled inventory-loss helper at final live state | {summary['modelled_inventory_loss_helper_at_end']:.2f} |

The inventory-loss value is a final-state diagnostic from the current helper, not a cumulative historical damage estimate. See `summary.json` and the CSV files for the complete compact outputs.
"""
    (OUTPUT_DIR / "summary.md").write_text(markdown, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sim = run_custom_simulation(
        nr_ticks=TICKS,
        start_fire_at_coord=IGNITION_COORD,
        probabilistic=False,
        save_full_history=True,
        snapshot_interval=1,
        save_history_parameters=HISTORY_FIELDS,
        fire_dept_arrival_coords=(4, 4, 0),
        fire_dept_response_time=30,
        random_seed=SEED,
    )

    routes = agent_routes(sim)
    tidy_routes = _tidy_agent_routes(routes)
    fd_actions = fd_actions_dataframe(sim)
    tidy_routes.to_csv(OUTPUT_DIR / "agent_activity.csv", index=False)
    fd_actions.to_csv(OUTPUT_DIR / "fire_department_activity.csv", index=False)

    visualized_ticks = _create_progression_figure(sim, fd_actions)
    _create_analysis_figures(sim)
    summary = _summary(sim, routes, fd_actions, visualized_ticks)
    _write_summary(summary)

    print(f"Demonstration completed at tick {sim.time} with seed {SEED}.")
    print(f"Saved {len(sim.history)} snapshots.")
    print(f"Curated outputs: {OUTPUT_DIR.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
