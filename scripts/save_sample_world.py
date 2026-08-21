"""Serialize a freshly constructed sample world into the data directory."""

from building_fire_simulation.scenarios import save_default_data


def main() -> None:
    global_model, room_catalogue = save_default_data()
    print(f"Saved sample building with {len(global_model)} cubes.")
    print(f"Saved room catalogue with {len(room_catalogue)} categories.")


if __name__ == "__main__":
    main()
