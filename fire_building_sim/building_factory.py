"""Building graph construction, room carving, and sample-world creation."""

import os



from fire_building_sim.config import DATA_DIR
data_path = str(DATA_DIR)

# Typing and collections
from typing import List, Tuple, Dict, Set

# Core building classes and constants
from fire_building_sim.domain import (
    Coordinate, BuildingComponent, Cube, Room,
    Wall, FloorSurface, CeilingSurface,
    STRUCTURAL_MATERIALS, CoverMaterialItem, COVER_MATERIAL_ITEMS, Material,
    FIRE_SAFETY_ITEMS,
    FURNITURE_ITEMS, FURNISHING_ITEMS, OFFICE_SUPPLY_ITEMS, MISCELLANIOUS_ITEMS_GROUP,
    DOORS, WINDOWS, STAIRS,
    ACCESS_PANELS
)

# Plotting
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib import colormaps

# Data serialization
import pickle
import pandas as pd
from copy import deepcopy

def get_neighbors(coord: Tuple[int, int, int]) -> Dict[str, Tuple[int, int, int]]:
    x, y, z = coord
    return {
        "left": (x - 1, y, z),
        "right": (x + 1, y, z),
        "front": (x, y + 1, z),
        "back": (x, y - 1, z),
        "below": (x, y, z - 1),
        "above": (x, y, z + 1),
    }


def get_opposite_direction(direction: str) -> str:
    return {
        "left": "right",
        "right": "left",
        "front": "back",
        "back": "front"
    }.get(direction, "")


node_id_counter = 0


def next_node_id():
    global node_id_counter
    node_id_counter += 1
    return node_id_counter


def reset_node_id_counter():
    """Reset the global node ID counter (used before rebuilding the graph)."""
    global node_id_counter
    node_id_counter = 0


def create_constellation(x_len: int, y_len: int, z_len: int) -> List[Tuple[int, int, int]]:
    """Create a list of coordinates for a 3D block of cubes."""
    if x_len < 1 or y_len < 1 or z_len < 1:
        raise ValueError("All dimensions must be at least 1")

    return [(x, y, z) for x in range(x_len) for y in range(y_len) for z in range(z_len)]


def translate_coordinates(coords: List[Tuple[int, int, int]], new_origin: Tuple[int, int, int]) -> List[Tuple[int, int, int]]:
    """Translate a list of coordinates to a new origin in global space."""
    dx, dy, dz = new_origin
    return [(x + dx, y + dy, z + dz) for (x, y, z) in coords]


def build_model_from_coords(coords: List[Tuple[int, int, int]]) -> Dict[Tuple[int, int, int], Cube]:
    """Create cube model from a list of coordinates."""
    return {coord: Cube(node_id=next_node_id(), coordinate=Coordinate(*coord)) for coord in coords}

def build_building_graph(
    cubes: Dict[Tuple[int, int, int], Cube],
    default_wall_structure: str = "brick",
    default_wall_cover: str = "particle board",
    default_floor_structure: str = "concrete",
    default_floor_cover: str = "paper on particle board",
    default_ceiling_structure: str = "concrete",
    default_ceiling_cover: str = "textile on gypsum"
) -> List[BuildingComponent]:
    """
    Create and connect all walls, floors, ceilings for each cube,
    assigning structural and cover materials separately.

    Each cube owns its own wall, floor, and ceiling surfaces, even if they
    are adjacent to other cubes.
    """
    components: List[BuildingComponent] = []

    for coord, cube in cubes.items():
        x, y, z = coord
        neighbors = get_neighbors(coord)

        # Resolve defaults once (structure usually immutable; covers deepcopied per surface)
        wall_struct = STRUCTURAL_MATERIALS.get(default_wall_structure, STRUCTURAL_MATERIALS["brick"])
        wall_cover_proto = COVER_MATERIAL_ITEMS.get(default_wall_cover, COVER_MATERIAL_ITEMS["particle board"])

        floor_struct = STRUCTURAL_MATERIALS.get(default_floor_structure, STRUCTURAL_MATERIALS["concrete"])
        floor_cover_proto = COVER_MATERIAL_ITEMS.get(default_floor_cover, COVER_MATERIAL_ITEMS["paper on particle board"])

        ceiling_struct = STRUCTURAL_MATERIALS.get(default_ceiling_structure, STRUCTURAL_MATERIALS["concrete"])
        ceiling_cover_proto = COVER_MATERIAL_ITEMS.get(default_ceiling_cover, COVER_MATERIAL_ITEMS["textile on gypsum"])

        # --- WALLS ---
        for direction in ["left", "right", "front", "back"]:
            if getattr(cube, f"{direction}_wall") is None:
                neighbor_coord = neighbors[direction]
                is_exterior = neighbor_coord not in cubes

                wall = Wall(
                    node_id=next_node_id(),
                    cube=cube,
                    direction=direction,
                    is_exterior=is_exterior,
                    structure_material=wall_struct,
                    # deepcopy so each surface has its own CoverMaterialItem + FireBehavior state
                    cover_material=deepcopy(wall_cover_proto)
                )
                setattr(cube, f"{direction}_wall", wall)
                components.append(wall)

        # --- FLOOR ---
        if cube.floor is None:
            floor = FloorSurface(
                node_id=next_node_id(),
                cube=cube,
                structure_material=floor_struct,
                cover_material=deepcopy(floor_cover_proto)
            )
            cube.floor = floor
            components.append(floor)

        # --- CEILING ---
        if cube.ceiling is None:
            ceiling = CeilingSurface(
                node_id=next_node_id(),
                cube=cube,
                structure_material=ceiling_struct,
                cover_material=deepcopy(ceiling_cover_proto)
            )
            cube.ceiling = ceiling
            components.append(ceiling)

    return list(cubes.values()) + components

def initialize_surface_neighbors(model: Dict[Tuple[int, int, int], Cube]):
    """
    Initialize surface_neighbor for all surfaces in the building model.
    """
    for coord, cube in model.items():
        neighbors = get_neighbors(coord)

        # Wall neighbors
        for direction in ["left", "right", "front", "back"]:
            wall = getattr(cube, f"{direction}_wall", None)
            if wall is not None:
                neighbor_coord = neighbors[direction]
                if neighbor_coord in model:
                    neighbor_cube = model[neighbor_coord]
                    opposite_dir = {
                        "left": "right",
                        "right": "left",
                        "front": "back",
                        "back": "front"
                    }[direction]
                    neighbor_wall = getattr(neighbor_cube, f"{opposite_dir}_wall", None)
                    wall.surface_neighbor = neighbor_wall

        # Floor-Ceiling neighbors
        if cube.floor and "below" in neighbors:
            below_coord = neighbors["below"]
            if below_coord in model:
                neighbor_cube = model[below_coord]
                cube.floor.surface_neighbor = neighbor_cube.ceiling

        if cube.ceiling and "above" in neighbors:
            above_coord = neighbors["above"]
            if above_coord in model:
                neighbor_cube = model[above_coord]
                cube.ceiling.surface_neighbor = neighbor_cube.floor

def initialize_items_in_cubes(
    global_model: Dict[Tuple[int, int, int], Cube],
    explicit_placements: List[Dict]
) -> None:
    """
    Places specified items into specific cubes using structured placement instructions.

    Each entry in explicit_placements must include:
    - 'cube_coord': Tuple[int, int, int]
    - 'item_specs': Dict[str, int]  ← item_name → quantity
    - 'item_catalog': Dict[str, Item]  ← item_name → prototype
    """
    for entry in explicit_placements:
        coord = entry["cube_coord"]
        item_specs = entry["item_specs"]
        item_catalog = entry["item_catalog"]

        if coord not in global_model:
            raise ValueError(f"Cube at {coord} does not exist.")

        cube = global_model[coord]

        for name, count in item_specs.items():
            prototype = item_catalog[name]
            for _ in range(count):
                cube.items.append(deepcopy(prototype))

def initialize_items_on_surfaces(
    global_model: Dict[Tuple[int, int, int], Cube],
    explicit_placements: List[Dict]
) -> None:
    """
    Places specified items onto specific cube surfaces.

    Each entry in explicit_placements must include:
    - 'cube_coord': Tuple[int, int, int]
    - 'surface': str  ← one of: 'floor', 'ceiling', 'left_wall', 'right_wall', 'front_wall', 'back_wall'
    - 'item_catalog': Dict[str, Item]  ← item_name → prototype
    - 'item_specs': Dict[str, int]  ← item_name → quantity
    """
    for entry in explicit_placements:
        coord = entry["cube_coord"]
        surface = entry["surface"]
        item_catalog = entry["item_catalog"]
        item_specs = entry["item_specs"]

        if coord not in global_model:
            raise ValueError(f"Cube at {coord} does not exist.")
        if surface not in {"floor", "ceiling", "left_wall", "right_wall", "front_wall", "back_wall"}:
            raise ValueError(f"Invalid surface '{surface}'")

        component = getattr(global_model[coord], surface)

        for name, count in item_specs.items():
            prototype = item_catalog[name]
            for _ in range(count):
                component.items.append(deepcopy(prototype))

def carve_room_shape(
    local_coords: List[Tuple[int, int, int]],
    origin: Tuple[int, int, int],
    global_model: Dict[Tuple[int, int, int], Cube]
):
    """
    Carve a room shape into the global model by marking all **shared walls** and **vertical floor/ceiling pairs**
    between cubes in the shape as hollow. This is compatible with the model where each cube has its own surface instances.
    """
    dx, dy, dz = origin
    global_coords = [(x + dx, y + dy, z + dz) for x, y, z in local_coords]

    for coord in global_coords:
        if coord not in global_model:
            raise ValueError(f"Cannot carve room: cube {coord} not found in global model.")

    for coord in global_coords:
        cube = global_model[coord]
        neighbors = get_neighbors(coord)

        for direction, neighbor_coord in neighbors.items():
            if neighbor_coord not in global_model:
                continue
            if neighbor_coord not in global_coords:
                continue  # only carve internal connections

            neighbor = global_model[neighbor_coord]

            if direction == "left" and cube.left_wall and neighbor.right_wall:
                cube.left_wall.hollow = True
                neighbor.right_wall.hollow = True

            elif direction == "right" and cube.right_wall and neighbor.left_wall:
                cube.right_wall.hollow = True
                neighbor.left_wall.hollow = True

            elif direction == "front" and cube.front_wall and neighbor.back_wall:
                cube.front_wall.hollow = True
                neighbor.back_wall.hollow = True

            elif direction == "back" and cube.back_wall and neighbor.front_wall:
                cube.back_wall.hollow = True
                neighbor.front_wall.hollow = True

            elif direction == "below" and cube.floor and neighbor.ceiling:
                cube.floor.hollow = True
                neighbor.ceiling.hollow = True

            elif direction == "above" and cube.ceiling and neighbor.floor:
                cube.ceiling.hollow = True
                neighbor.floor.hollow = True

def modify_room_surfaces(
    surface_dict: Dict[str, List[BuildingComponent]],
    surface_type: str,
    mod_type: str,
    set_to,
    only_non_hollow: bool = False
):
    """
    Modify surfaces of a given type by setting attributes like 'structure_material' or 'cover_material'.

    - For structure_material: uses STRUCTURAL_MATERIALS (kept by reference)
    - For cover_material: uses COVER_MATERIAL_ITEMS and **deepcopies** the value so each surface
      has its own independent CoverMaterialItem + FireBehavior state.
    """
    surfaces = surface_dict.get(surface_type, [])
    for surface in surfaces:
        if only_non_hollow and getattr(surface, "hollow", False):
            continue

        if mod_type in {"structure_material", "cover_material"}:
            if mod_type == "structure_material":
                registry = STRUCTURAL_MATERIALS
                expected_type = Material
                use_deepcopy = False   # structural materials are typically immutable/shared
            else:
                registry = COVER_MATERIAL_ITEMS
                expected_type = CoverMaterialItem
                use_deepcopy = True    # covers carry FireBehavior state → must not be shared

            if isinstance(set_to, str):
                value = registry.get(set_to)
                if value is None:
                    raise ValueError(f"{mod_type} '{set_to}' not found in registry.")
                new_val = deepcopy(value) if use_deepcopy else value
            elif isinstance(set_to, expected_type):
                new_val = deepcopy(set_to) if use_deepcopy else set_to
            else:
                raise TypeError(f"Invalid type for {mod_type}: expected {expected_type}, got {type(set_to)}")

            setattr(surface, mod_type, new_val)

            # If we changed the cover material, clear any stale ignition flags on the surface
            # and (if present) on its FireBehavior.
            if mod_type == "cover_material":
                if hasattr(surface, "is_ignited"):
                    surface.is_ignited = False
                if hasattr(surface, "time_above_ignition_temp"):
                    surface.time_above_ignition_temp = 0.0

                fb = getattr(new_val, "fire_behavior", None)
                if fb:
                    # Make sure the fresh cover starts "cold"
                    setattr(fb, "is_ignited", False)
                    setattr(fb, "time_above_ignition_temp", 0.0)
                    setattr(fb, "latest_heat_output", 0.0)
                    # Don't assume total_energy; released_energy definitely should reset:
                    setattr(fb, "released_energy", 0.0)

        else:
            # Any other attribute change passes through directly
            setattr(surface, mod_type, set_to)

def modify_multiple_room_surfaces(
    surface_dict: Dict[str, List[BuildingComponent]],
    surface_types: List[str],
    mod_type: str,
    set_to,
    only_non_hollow: bool = False
):
    """
    Modify multiple surface types in a room using modify_room_surfaces.
    """
    for surface_type in surface_types:
        modify_room_surfaces(
            surface_dict=surface_dict,
            surface_type=surface_type,
            mod_type=mod_type,
            set_to=set_to,
            only_non_hollow=only_non_hollow
        )

def attach_item_to_surface_pair(surface, item, clone=True):
    """
    Attach a single *instance* of an item to a surface and its surface_neighbor.
    If clone=True, make a fresh copy from the given prototype.
    """
    if not hasattr(surface, "items"):
        raise TypeError(f"{surface} does not support item attachment.")

    inst = deepcopy(item) if clone else item  # clone once per doorway
    if inst not in surface.items:
        surface.items.append(inst)

    neighbor = getattr(surface, "surface_neighbor", None)
    if neighbor and inst not in neighbor.items:
        neighbor.items.append(inst)

def find_room_objects(model: Dict[Tuple[int, int, int], Cube]) -> List[Room]:
    """
    Traverse the model through hollow walls and ceilings to discover room-connected cubes.
    Returns a list of Room objects.
    """
    visited = set()
    rooms = []

    def get_connected_neighbors(coord: Tuple[int, int, int]) -> List[Tuple[int, int, int]]:
        """Get adjacent cube coordinates that are connected via hollow surfaces."""
        cube = model[coord]
        connections = []

        for direction, attr in [
            ("left", cube.left_wall), ("right", cube.right_wall),
            ("front", cube.front_wall), ("back", cube.back_wall),
            ("above", cube.ceiling), ("below", cube.floor)
        ]:
            neighbor_coord = get_neighbors(coord).get(direction)
            if neighbor_coord in model:
                surface = attr
                if surface and getattr(surface, "hollow", False):
                    connections.append(neighbor_coord)

        return connections

    def dfs(coord: Tuple[int, int, int], current_room: Set[Tuple[int, int, int]]):
        visited.add(coord)
        current_room.add(coord)
        for neighbor_coord in get_connected_neighbors(coord):
            if neighbor_coord not in visited:
                dfs(neighbor_coord, current_room)

    for coord in model:
        if coord not in visited:
            room_coords = set()
            dfs(coord, room_coords)
            room = Room(room_id=len(rooms), cubes=room_coords, model=model)
            rooms.append(room)

    return rooms

def get_room_surface_dict(room_id: int, rooms: List[Room], exclude_hollow: bool = False) -> Dict[str, List[BuildingComponent]]:
    """
    Return a dictionary of categorized surfaces for a given room ID, using actual surface directions.

    Parameters:
        room_id (int): The ID of the room.
        rooms (List[Room]): List of all room objects.
        exclude_hollow (bool): If True, exclude surfaces marked as hollow.

    Returns:
        Dict[str, List[BuildingComponent]]: Surface dictionary for the specified room.
    """
    room = next((room for room in rooms if room.room_id == room_id), None)
    if not room:
        raise ValueError(f"Room ID {room_id} not found.")

    surface_dict = {
        'floor': [],
        'ceiling': [],
        'walls_left': [],
        'walls_right': [],
        'walls_front': [],
        'walls_back': [],
    }

    for comp in room.components:
        if exclude_hollow and getattr(comp, "hollow", False):
            continue

        if isinstance(comp, FloorSurface):
            surface_dict['floor'].append(comp)
        elif isinstance(comp, CeilingSurface):
            surface_dict['ceiling'].append(comp)
        elif isinstance(comp, Wall):
            direction = getattr(comp, "direction", None)
            if direction in {"left", "right", "front", "back"}:
                key = f"walls_{direction}"
                surface_dict[key].append(comp)
            else:
                raise ValueError(f"Unexpected wall direction: {direction}")
        else:
            # Optionally handle or skip unknown surface types
            continue

    return surface_dict


def get_cube_at_coord(coord: Tuple[int, int, int], model: Dict[Tuple[int, int, int], Cube]) -> Cube:
    """
    Returns the Cube object at the specified coordinate.

    Raises:
        KeyError: If the coordinate does not exist in the global model.
    """
    cube = model.get(coord)
    if cube is None:
        raise KeyError(f"Cube at coordinate {coord} not found in global model.")
    return cube


def get_room_info(room_id: int, model: Dict[Tuple[int, int, int], Cube], exclude_hollow: bool = False) -> pd.DataFrame:
    rooms = find_room_objects(model)
    _room = next((room for room in rooms if room.room_id == room_id), None)
    if not _room:
        raise ValueError(f"Room ID {room_id} not found.")

    # Room specifics.
    sorted_cubes = sorted(_room.cube_coords)
    cube_items = {cube_coord: get_cube_at_coord(cube_coord, model).items for cube_coord in sorted_cubes}
    cubes_info = {'Room ID': _room.room_id,
                  'Total number of components in room': len(_room.components),
                  'Cube coordinates in room': sorted_cubes,
                  'Cube items': cube_items}

    room_surface_dict = get_room_surface_dict(room_id, rooms, exclude_hollow)

    data = []
    for surface_type, surfaces in room_surface_dict.items():
        for surface in surfaces:
            struct_mat = getattr(surface, "structure_material", None)
            cover_mat = getattr(surface, "cover_material", None)
            cube = getattr(surface, "cube", None)
            cube_coord = cube.coordinate
            surface_items = surface.items

            data.append({
                "surface_type": surface_type,
                "node_id": surface.node_id,
                "structure_material": struct_mat.name if struct_mat else None,
                "cover_material": cover_mat.name if cover_mat else None,
                "degradation": getattr(surface, "degradation", None),
                "hollow": getattr(surface, "hollow", None),
                "is_exterior": getattr(surface, "is_exterior", None),
                "direction": getattr(surface, "direction", None),
                "class": surface.__class__.__name__,
                "cube_coord": cube_coord,
                "surface_items": surface_items
            })

    room_dict = {'cubes_info': cubes_info, 'surface_info': pd.DataFrame(data)}
    return room_dict

def is_connected_via_hollow_path(start: Tuple[int, int, int],
                                 target: Tuple[int, int, int],
                                 model: Dict[Tuple[int, int, int], "Cube"],
                                 max_steps: int = 20) -> bool:
    from collections import deque

    visited = set()
    queue = deque([start])

    def neighbors(coord):
        cube = model.get(coord)
        if not cube:
            return []
        result = []
        for direction, surface in [
            ("left", cube.left_wall), ("right", cube.right_wall),
            ("front", cube.front_wall), ("back", cube.back_wall),
            ("above", cube.ceiling), ("below", cube.floor)
        ]:
            neighbor_coord = get_neighbors(coord).get(direction)
            if neighbor_coord in model and surface and getattr(surface, "hollow", False):
                result.append(neighbor_coord)
        return result

    while queue and max_steps > 0:
        current = queue.popleft()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        queue.extend(neighbors(current))
        max_steps -= 1

    return False

from typing import Dict, List, Tuple
# adjust import path if needed

Coord = Tuple[int,int,int]

def build_room_catalog_from_model(model: Dict[Coord, object]) -> Dict[str, List[Coord]]:
    """
    Build {room_name: [coords...]} using get_room_info(room_id, model).
    Pass the MODEL (coords -> Cube), not precomputed rooms.
    """
    room_ids = {
        # Downstairs
        "downstairs_large_office": 0,
        "downstairs_storage": 3,
        "downstairs_meeting_room": 8,
        "downstairs_entry_hall": 9,
        # Upstairs
        "upstairs_large_office": 10,
        "upstairs_small_office_1": 1,
        "upstairs_small_office_2": 2,
        "upstairs_small_office_3": 4,
        "upstairs_small_office_4": 5,
        "upstairs_small_office_5": 6,
        "upstairs_open_area": 7,
    }

    catalog: Dict[str, List[Coord]] = {}

    for name, rid in room_ids.items():
        info = get_room_info(rid, model)

        # Try dict-like structure (matches your pasted example)
        coords = None
        if isinstance(info, dict):
            coords = info.get("cubes_info", {}).get("Cube coordinates in room", None)

        # If it's a pandas DataFrame (per your type hint), try to extract the coords column
        if coords is None:
            try:
                # If info is a DataFrame where one row/column stores the list
                if hasattr(info, "to_dict"):
                    d = info.to_dict(orient="list")  # or "records" depending on your DF shape
                    # Try common keys
                    for key in ["Cube coordinates in room", "cube_coords", "coords", "cubes"]:
                        if key in d:
                            coords = d[key]
                            # If it's a single row DF, coords may be [ [ (..), (..), ... ] ]
                            if len(coords) == 1 and isinstance(coords[0], list):
                                coords = coords[0]
                            break
            except Exception:
                pass

        if coords is None:
            coords = []  # fall back to empty

        catalog[name] = list(coords)

    return catalog

def draw_cube_faces(ax, x, y, z, face_alphas, size=1, color='skyblue'):
    """Draw each face of a cube with hollow faces fully transparent and no edge lines."""
    r = [0, size]
    vertices = [
        (x + r[0], y + r[0], z + r[0]), (x + r[1], y + r[0], z + r[0]),
        (x + r[1], y + r[1], z + r[0]), (x + r[0], y + r[1], z + r[0]),
        (x + r[0], y + r[0], z + r[1]), (x + r[1], y + r[0], z + r[1]),
        (x + r[1], y + r[1], z + r[1]), (x + r[0], y + r[1], z + r[1])
    ]
    face_indices = [
        [0, 1, 2, 3],  # bottom
        [4, 5, 6, 7],  # top
        [0, 1, 5, 4],  # front
        [2, 3, 7, 6],  # back
        [1, 2, 6, 5],  # right
        [0, 3, 7, 4],  # left
    ]
    for i, indices in enumerate(face_indices):
        alpha = face_alphas[i]
        is_hollow = alpha < 0.1
        poly = Poly3DCollection(
            [[vertices[j] for j in indices]],
            facecolors=color,
            linewidths=0 if is_hollow else 0.5,
            edgecolors='none' if is_hollow else 'gray',
            alpha=alpha
        )
        ax.add_collection3d(poly)

def visualize_building(global_model: Dict[Tuple[int, int, int], Cube]):
    """Visualize cubes with transparency based on hollow surfaces and color by room size."""

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    # Find room groupings
    rooms = find_room_objects(global_model)

    # Define color mapping by room size
    norm = Normalize(vmin=2, vmax=40)
    cmap = colormaps.get_cmap("RdYlGn_r")

    for room in rooms:
        room_size = len(room.cube_coords)
        color = 'skyblue' if room_size == 1 else cmap(norm(room_size))
        alpha_solid = 0.8 if room_size > 1 else 0.3

        for coord in room.cube_coords:
            cube = global_model[coord]
            x, y, z = coord

            def alpha(surface):
                return 0.05 if (surface and getattr(surface, "hollow", False)) else alpha_solid

            face_alphas = [
                alpha(cube.floor),        # bottom
                alpha(cube.ceiling),      # top
                alpha(cube.front_wall),   # front
                alpha(cube.back_wall),    # back
                alpha(cube.right_wall),   # right
                alpha(cube.left_wall),    # left
            ]

            draw_cube_faces(ax, x, y, z, face_alphas, size=1, color=color)

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
    plt.show()

def create_sample_building(return_info_dict=False) -> Dict[Tuple[int, int, int], Cube]:
    """
    Constructs and returns a sample global_model with rooms carved and materials assigned.
    """
    global node_id_counter
    node_id_counter = 0

    # --- CREATE BUILDING MODEL CONSTELLATION ---

    # Create local constellations.
    coords1 = create_constellation(5, 5, 2)

    # Translate coordinates into global space.
    global_coords1 = translate_coordinates(coords1, (0, 0, 0))

    # Combine and build cube model.
    all_coords = global_coords1
    global_model = build_model_from_coords(all_coords)

    # Build graph from all cubes.
    components = build_building_graph(global_model)
    node_lookup = {c.node_id: c for c in components}  # kept if referenced elsewhere

    # Initialize surface neighbors.
    initialize_surface_neighbors(global_model)

    # --- CARVE ROOMS IN MODEL ---

    # Carve room 1, floor 1.
    hollow_coords_1_1 = create_constellation(2, 2, 1)
    carve_room_shape(hollow_coords_1_1, (0, 0, 0), global_model)

    # Carve room 2, floor 1.
    hollow_coords_2_1 = create_constellation(2, 3, 1)
    carve_room_shape(hollow_coords_2_1, (0, 2, 0), global_model)

    # Carve room 3, floor 1.
    hollow_coords_3_1 = create_constellation(3, 2, 1)
    carve_room_shape(hollow_coords_3_1, (2, 0, 0), global_model)

    # Carve room 4, floor 1.
    hollow_coords_4_1 = create_constellation(3, 3, 1)
    carve_room_shape(hollow_coords_4_1, (2, 2, 0), global_model)

    # Carve room 1, floor 2.
    hollow_coords_1_2_1 = create_constellation(2, 5, 1)
    carve_room_shape(hollow_coords_1_2_1, (1, 0, 1), global_model)
    hollow_coords_1_2_2 = create_constellation(2, 3, 1)
    carve_room_shape(hollow_coords_1_2_2, (3, 0, 1), global_model)
    get_cube_at_coord((2, 0, 1), global_model).right_wall.hollow = True
    get_cube_at_coord((2, 1, 1), global_model).right_wall.hollow = True
    get_cube_at_coord((2, 2, 1), global_model).right_wall.hollow = True
    get_cube_at_coord((3, 0, 1), global_model).left_wall.hollow = True
    get_cube_at_coord((3, 1, 1), global_model).left_wall.hollow = True
    get_cube_at_coord((3, 2, 1), global_model).left_wall.hollow = True

    # Carve room 2, floor 2.
    hollow_coords_2_2 = create_constellation(2, 2, 1)
    carve_room_shape(hollow_coords_2_2, (3, 3, 1), global_model)

    # --- LABEL ROOMS ---
    rooms = find_room_objects(global_model)

    # Downstairs rooms.
    downstairs_large_office = get_room_surface_dict(0, rooms)
    downstairs_storage = get_room_surface_dict(3, rooms)
    downstairs_meeting_room = get_room_surface_dict(8, rooms)
    downstairs_entry_hall = get_room_surface_dict(9, rooms)

    # Upstairs rooms.
    upstairs_large_office = get_room_surface_dict(10, rooms)
    upstairs_small_office_1 = get_room_surface_dict(1, rooms)
    upstairs_small_office_2 = get_room_surface_dict(2, rooms)
    upstairs_small_office_3 = get_room_surface_dict(4, rooms)
    upstairs_small_office_4 = get_room_surface_dict(5, rooms)
    upstairs_small_office_5 = get_room_surface_dict(6, rooms)
    upstairs_open_area = get_room_surface_dict(7, rooms)

    # --- SET ROOM PARAMETERS ---

    ''' Modify small upstairs offices.

    Structure materials:
        - Wood structural.
    Cover materials:
        - Insulating fiberboard.
    Inventory items:
        - Wooden chair.
        - Bookshelf.
        - Table.
    Building accessory items:
        - Mediocre window.
        - Mediocre door to open area.
    Fire safety items:
        - Smoke alarm x1 on left wall.
        - Sprinkler a1 in ceiling.
    '''

    upstairs_small_offices = [upstairs_small_office_1, upstairs_small_office_2, upstairs_small_office_3,
                              upstairs_small_office_4, upstairs_small_office_5]

    for office in upstairs_small_offices:
        # Modify office structural materials.
        modify_multiple_room_surfaces(
            surface_dict=office,
            surface_types=["walls_left", "walls_right", "walls_front", "walls_back"],
            mod_type="structure_material", set_to="wood (structural)"
        )

        # Modify office cover materials.
        modify_multiple_room_surfaces(
            surface_dict=office,
            surface_types=["walls_left", "walls_right", "walls_front", "walls_back"],
            mod_type="cover_material", set_to="insulating fiberboard"
        )

    # Initialize cube items.
    small_office_coords = [(0, 0, 1), (0, 1, 1), (0, 2, 1), (0, 3, 1), (0, 4, 1)]
    for coord in small_office_coords:
        initialize_items_in_cubes(global_model, [
            {"cube_coord": coord,
             "item_catalog": FURNITURE_ITEMS,
             "item_specs": {"wooden_chair": 1, "wooden_bookshelf": 1, "wooden_table": 1}},
            {"cube_coord": coord,
             "item_catalog": MISCELLANIOUS_ITEMS_GROUP,
             "item_specs": {"low_cost_small_set": 1}}])

        # Create doors and windows to the offices.
        cube = get_cube_at_coord(coord, global_model)
        attach_item_to_surface_pair(cube.right_wall, DOORS["door_mediocre"])  # Shared objects.
        initialize_items_on_surfaces(global_model, [
            {"cube_coord": coord,
             "surface": "left_wall",
             "item_catalog": WINDOWS,
             "item_specs": {"window_mediocre": 1}}])

        # Place fire safety items.
        initialize_items_on_surfaces(global_model, [
            {"cube_coord": coord,
             "surface": "ceiling",
             "item_catalog": FIRE_SAFETY_ITEMS,
             "item_specs": {"sprinkler_a1": 1}},
            {"cube_coord": coord,
             "surface": "left_wall",
             "item_catalog": FIRE_SAFETY_ITEMS,
             "item_specs": {"smoke_alarm_x1": 1}}])

    ''' Modify large upstairs office.

    Structure materials:
        - Supersteel.
    Cover materials:
        - Wood panel, spruce.
    Inventory items:
        - Oak table.
        - Chesterfield chair.
        - 2 wooden chairs.
    Building accessory items:
        - 4 good windows.
        - Dual doors to open area.
    Fire safety items:
        - Smoke alarm x1 in ceiling.
        - Sprinkler a1 in ceiling.
    '''

    # Modify office structural materials.
    modify_multiple_room_surfaces(
        surface_dict=upstairs_large_office,
        surface_types=["walls_left", "walls_right", "walls_front", "walls_back"],
        mod_type="structure_material", set_to="supersteel"
    )

    # Modify office cover materials.
    modify_multiple_room_surfaces(
        surface_dict=upstairs_large_office,
        surface_types=["walls_left", "walls_right", "walls_front", "walls_back"],
        mod_type="cover_material", set_to="wood panel, spruce"
    )

    # Initialize inventory items.
    initialize_items_in_cubes(global_model, [
        {"cube_coord": (4, 4, 1),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"wooden_table_oak": 1, "chesterfield_machester_wing_chair": 1}},
        {"cube_coord": (4, 3, 1),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"wooden_chair": 2}},
        {"cube_coord": (3, 3, 1),
         "item_catalog": MISCELLANIOUS_ITEMS_GROUP,
         "item_specs": {"medium_cost_small_set": 1}},
        {"cube_coord": (3, 4, 1),
         "item_catalog": MISCELLANIOUS_ITEMS_GROUP,
         "item_specs": {"medium_cost_small_set": 1}},
        {"cube_coord": (4, 3, 1),
         "item_catalog": MISCELLANIOUS_ITEMS_GROUP,
         "item_specs": {"medium_cost_small_set": 1}},
        {"cube_coord": (4, 4, 1),
         "item_catalog": MISCELLANIOUS_ITEMS_GROUP,
         "item_specs": {"medium_cost_small_set": 1}}])

    # Create door.
    door_to_upstairs_office = deepcopy(DOORS["dual_doors"])
    door_to_upstairs_office.is_locked = True
    attach_item_to_surface_pair(get_cube_at_coord((3, 3, 1), global_model).back_wall, door_to_upstairs_office)

    # Create windows along exterior facing walls.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (3, 4, 1),
         "surface": "front_wall",
         "item_catalog": WINDOWS,
         "item_specs": {"window_good": 1}},
        {"cube_coord": (4, 4, 1),
         "surface": "front_wall",
         "item_catalog": WINDOWS,
         "item_specs": {"window_good": 1}},
        {"cube_coord": (4, 4, 1),
         "surface": "right_wall",
         "item_catalog": WINDOWS,
         "item_specs": {"window_good": 1}},
        {"cube_coord": (4, 3, 1),
         "surface": "right_wall",
         "item_catalog": WINDOWS,
         "item_specs": {"window_good": 1}}])

    # Hang painting.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (4, 3, 1),
         "surface": "back_wall",
         "item_catalog": FURNISHING_ITEMS,
         "item_specs": {"expensive_painting": 1}}])

    # Place fire safety items.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (3, 3, 1),
         "surface": "ceiling",
         "item_catalog": FIRE_SAFETY_ITEMS,
         "item_specs": {"sprinkler_a1": 1, "smoke_alarm_x1": 1}}])

    ''' Modify upstairs open area.

    Structure materials:
        - Brick.
    Cover materials:
        - Particle board.
    Inventory items:
        - 2 soffas.
        - Wooden table.
        - Cheap paintings.
    Building accessory items:
        - Doors to small offices.
        - Door to large office.
        - Windows along exterior walls.
        - Staircase to downstairs entry hall.
    Fire safety items:
        - Smoke alarm.
        - Sprinkler.
    '''

    # Initialize inventory items.
    initialize_items_in_cubes(global_model, [
        {"cube_coord": (2, 0, 1),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"decent_soffa": 1}},
        {"cube_coord": (2, 1, 1),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"decent_soffa": 1, "wooden_table": 1}}])

    for coord in [(4, 0, 1), (4, 1, 1), (2, 3, 1)]:
        initialize_items_on_surfaces(global_model, [
            {"cube_coord": coord,
             "surface": "right_wall",
             "item_catalog": FURNISHING_ITEMS,
             "item_specs": {"cheap_painting": 1}}])

    # Initialize miscellanious items in some of the cubes.
    for coord in [(1, 2, 1), (2, 0, 1), (2, 3, 1), (3, 1, 1), (4, 1, 1), (4, 2, 1)]:
        initialize_items_in_cubes(global_model, [
            {"cube_coord": coord,
             "item_catalog": MISCELLANIOUS_ITEMS_GROUP,
             "item_specs": {"low_cost_small_set": 1}}])

    # Create windows along back walls.
    for coord in [(1, 0, 1), (2, 0, 1), (3, 0, 1), (4, 0, 1)]:
        initialize_items_on_surfaces(global_model, [
            {"cube_coord": coord,
             "surface": "back_wall",
             "item_catalog": WINDOWS,
             "item_specs": {"window_mediocre": 1}}])

    # Create windows along right walls (except for painting).
    for coord in [(4, 1, 1), (4, 2, 1)]:
        initialize_items_on_surfaces(global_model, [
            {"cube_coord": coord,
             "surface": "right_wall",
             "item_catalog": WINDOWS,
             "item_specs": {"window_mediocre": 1}}])

    # Create stairs leading down to the first floor.
    attach_item_to_surface_pair(get_cube_at_coord((2, 4, 1), global_model).floor, STAIRS["oak_stairs"])

    # Place fire safety items.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (2, 2, 1),
         "surface": "ceiling",
         "item_catalog": FIRE_SAFETY_ITEMS,
         "item_specs": {"sprinkler_a1": 1, "smoke_alarm_x1": 1}}])

    ''' Modify downstairs storage.

    Structure materials:
        - Brick.
    Cover materials:
        - Particle board.
    Inventory items:
        - Plastic shelves.
        - Paper boxes.
        - Copy machine.
        - Toner cartridges.
        - Shipping boxes.
        - Old files archive.
    Fire safety items:
        - Smoke alarm.
        - Sprinkler.
    '''

    # Initialize inventory items.
    for coord in [(0, 2, 0), (0, 3, 0), (0, 4, 0)]:
        initialize_items_in_cubes(global_model, [
            {"cube_coord": coord,
             "item_catalog": OFFICE_SUPPLY_ITEMS,
             "item_specs": {"plastic_shelves": 1, "paper_boxes": 2}}])

    initialize_items_in_cubes(global_model, [
        {"cube_coord": (1, 3, 0),
         "item_catalog": OFFICE_SUPPLY_ITEMS,
         "item_specs": {"old_files_archive": 1, "shipping_boxes": 1}}])

    initialize_items_in_cubes(global_model, [
        {"cube_coord": (1, 4, 0),
         "item_catalog": OFFICE_SUPPLY_ITEMS,
         "item_specs": {"copy_machine": 1, "toner_cartridges": 1}}])

    # Initialize miscellanious items.
    for coord in [(0, 2, 0), (0, 3, 0), (0, 4, 0), (1, 3, 0), (1, 4, 0)]:
        initialize_items_in_cubes(global_model, [
            {"cube_coord": coord,
             "item_catalog": MISCELLANIOUS_ITEMS_GROUP,
             "item_specs": {"medium_cost_medium_set": 1}}])

    # Place fire safety items.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (0, 3, 0),
         "surface": "ceiling",
         "item_catalog": FIRE_SAFETY_ITEMS,
         "item_specs": {"sprinkler_a1": 1}},
        {"cube_coord": (1, 2, 0),
         "surface": "back_wall",
         "item_catalog": FIRE_SAFETY_ITEMS,
         "item_specs": {"smoke_alarm_x1": 1}}])

    # Create door to storage with access panel.
    door_to_storage = deepcopy(DOORS["door_good"])     # important: deepcopy
    door_to_storage.access_panel = ACCESS_PANELS["panel_lvl_3"]
    attach_item_to_surface_pair(get_cube_at_coord((1, 2, 0), global_model).right_wall, door_to_storage)


    ''' Modify large downstairs office.

    Structure materials:
        - Supersteel.
    Cover materials:
        - Wood panel, spruce.
    Inventory items:
        - Oak table.
        - Chesterfield chair.
        - 2 wooden chairs.
    Building accessory items:
        - 4 good windows.
        - Dual doors to meeting room.
    Fire safety items:
        - Smoke alarm x1 in ceiling.
        - Sprinkler a1 in ceiling.
    '''

    # Modify office structural materials.
    modify_multiple_room_surfaces(
        surface_dict=downstairs_large_office,
        surface_types=["walls_left", "walls_right", "walls_front", "walls_back"],
        mod_type="structure_material", set_to="supersteel"
    )

    # Modify office cover materials.
    modify_multiple_room_surfaces(
        surface_dict=downstairs_large_office,
        surface_types=["walls_left", "walls_right", "walls_front", "walls_back"],
        mod_type="cover_material", set_to="wood panel, spruce"
    )

    # Initialize inventory items.
    initialize_items_in_cubes(global_model, [
        {"cube_coord": (0, 0, 0),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"wooden_table_oak": 1, "chesterfield_machester_wing_chair": 1}},
        {"cube_coord": (1, 0, 0),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"wooden_chair": 2}}])

    # Initialize miscellanious items.
    for coord in [(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0)]:
        initialize_items_in_cubes(global_model, [
            {"cube_coord": coord,
             "item_catalog": MISCELLANIOUS_ITEMS_GROUP,
             "item_specs": {"high_cost_small_set": 1}}])

    # Create between downstairs office and meeting room.
    door_to_downstairs_office = deepcopy(DOORS["dual_doors"])
    door_to_downstairs_office.is_locked = True
    attach_item_to_surface_pair(get_cube_at_coord((1, 0, 0), global_model).right_wall, door_to_downstairs_office)

    # Create windows along exterior facing walls.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (0, 1, 0),
         "surface": "left_wall",
         "item_catalog": WINDOWS,
         "item_specs": {"window_good": 1}},
        {"cube_coord": (0, 0, 0),
         "surface": "left_wall",
         "item_catalog": WINDOWS,
         "item_specs": {"window_good": 1}},
        {"cube_coord": (0, 0, 0),
         "surface": "back_wall",
         "item_catalog": WINDOWS,
         "item_specs": {"window_good": 1}},
        {"cube_coord": (1, 0, 0),
         "surface": "back_wall",
         "item_catalog": WINDOWS,
         "item_specs": {"window_good": 1}}])

    # Hang painting.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (1, 1, 0),
         "surface": "front_wall",
         "item_catalog": FURNISHING_ITEMS,
         "item_specs": {"expensive_painting": 1}}])

    # Place fire safety items.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (1, 1, 0),
         "surface": "ceiling",
         "item_catalog": FIRE_SAFETY_ITEMS,
         "item_specs": {"sprinkler_a1": 1, "smoke_alarm_x1": 1}}])

    ''' Modify downstairs meeting room.

    Structure materials:
        - Brick.
    Cover materials:
        - Particle board.
    Inventory items:
        - Long meeting table.
        - Plastic office chairs.
    Building accessory items:
        - Dual doors to office.
        - Door to lobby.
    Fire safety items:
        - Smoke alarm x1 in ceiling.
        - Sprinkler a1 in ceiling.
    '''

    # Initialize inventory items.
    initialize_items_in_cubes(global_model, [
        {"cube_coord": (4, 0, 0),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"office_chair": 2}},
        {"cube_coord": (4, 1, 0),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"office_chair": 2}},
        {"cube_coord": (3, 0, 0),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"office_chair": 2}},
        {"cube_coord": (3, 1, 0),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"office_chair": 2}}])

    # Initialize wall-to-wall carpet in meeting room.
    for coord in [(2, 0, 0), (2, 1, 0), (3, 0, 0), (3, 1, 0), (4, 0, 0), (4, 1, 0)]:
        initialize_items_in_cubes(global_model, [
            {"cube_coord": coord,
             "item_catalog": FURNITURE_ITEMS,
             "item_specs": {"wall-to-wall_carpet": 1}}])

    # Put table in both cubes by attaching to surfaces.
    attach_item_to_surface_pair(get_cube_at_coord((3, 0, 0), global_model).right_wall, FURNITURE_ITEMS["long_meeting_table"])

    # Create door between lobby and entry hall.
    attach_item_to_surface_pair(get_cube_at_coord((3, 1, 0), global_model).front_wall, DOORS["dual_doors"])

    # Place fire safety items.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (3, 0, 0),
         "surface": "ceiling",
         "item_catalog": FIRE_SAFETY_ITEMS,
         "item_specs": {"sprinkler_a1": 1, "smoke_alarm_x1": 1}}])

    ''' Modify downstairs entry hall.

    Structure materials:
        - Brick.
    Cover materials:
        - Particle board.
    Inventory items:
        - Reception desk.
        - Piano.
    Building accessory items:
        - Door to storage.
        - Door to meeting room.
        - Stair to upstairs open area.
    Fire safety items:
        - Smoke alarm x1 in ceiling.
        - Sprinkler a1 in ceiling.
    '''

    # Initialize inventory items.
    initialize_items_in_cubes(global_model, [
        {"cube_coord": (4, 4, 0),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"reception_desk": 1}},
        {"cube_coord": (4, 2, 0),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"decent_soffa": 2}},
        {"cube_coord": (4, 3, 0),
         "item_catalog": FURNITURE_ITEMS,
         "item_specs": {"decent_soffa": 2}}])

    # Initialize miscellanious items.
    for coord in [(2, 4, 0), (3, 4, 0), (4, 3, 0), (4, 4, 0)]:
        initialize_items_in_cubes(global_model, [
            {"cube_coord": coord,
             "item_catalog": MISCELLANIOUS_ITEMS_GROUP,
             "item_specs": {"medium_cost_small_set": 1}}])

    # Place fire safety items.
    initialize_items_on_surfaces(global_model, [
        {"cube_coord": (3, 3, 0),
         "surface": "ceiling",
         "item_catalog": FIRE_SAFETY_ITEMS,
         "item_specs": {"sprinkler_a1": 1, "smoke_alarm_x1": 1}}])

    # Add main entrance.
    attach_item_to_surface_pair(get_cube_at_coord((4, 4, 0), global_model).right_wall, DOORS["main_entry_door"])


    if return_info_dict:
        # Create dict with labeled rooms.
        global_model_labeled_rooms = {'downstairs_large_office': get_room_info(0, global_model),
                                      'downstairs_storage': get_room_info(3, global_model),
                                      'downstairs_meeting_room': get_room_info(8, global_model),
                                      'downstairs_entry_hall': get_room_info(9, global_model),
                                      'upstairs_large_office': get_room_info(10, global_model),
                                      'upstairs_small_office_1': get_room_info(1, global_model),
                                      'upstairs_small_office_2': get_room_info(2, global_model),
                                      'upstairs_small_office_3': get_room_info(4, global_model),
                                      'upstairs_small_office_4': get_room_info(5, global_model),
                                      'upstairs_small_office_5': get_room_info(6, global_model),
                                      'upstairs_open_area': get_room_info(7, global_model)}
        return global_model, global_model_labeled_rooms
    else:
        return global_model



def save_to_pickle(obj, filepath):
    with open(filepath, "wb") as f:
        pickle.dump(obj, f)



def create_sample_building_with_catalog():
    """Return (global_model, room_catalogue) for the built-in sample building."""
    global_model = create_sample_building()
    room_catalogue = build_room_catalog_from_model(global_model)
    return global_model, room_catalogue


def save_sample_building(data_dir=None):
    """Create and save the sample building plus its room catalogue."""
    if data_dir is None:
        data_dir = data_path
    os.makedirs(data_dir, exist_ok=True)

    global_model, room_catalogue = create_sample_building_with_catalog()
    save_to_pickle(global_model, os.path.join(data_dir, "global_model.pkl"))
    save_to_pickle(room_catalogue, os.path.join(data_dir, "room_catalogue.pkl"))
    return global_model, room_catalogue
