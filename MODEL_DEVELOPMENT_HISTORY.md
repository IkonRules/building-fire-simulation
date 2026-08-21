# Building Fire Simulation — Model Development History

> **Document status:** reconstructed factual history  
> **Covered period:** 15 June 2025–21 August 2026  
> **Primary evidence:** preserved project chats, surviving project artifacts, and the current repository  
> **Purpose:** provide a traceable factual basis for later, more narrative accounts of the project

## 1. Purpose and scope

This document reconstructs how the Building Fire Simulation project developed from its first nbdev setup into the present Python package. It emphasizes:

- when the principal modules and model layers appeared;
- what each module or layer was intended to do;
- major implementation problems and their resolutions;
- how the building, room, fire-spread, heat-release, item, safety, agent, emergency-response, probability, history, and analysis ideas changed over time; and
- which parts of the current design are directly evidenced, inferred, or still uncertain.

The history is intentionally factual. It records design changes and debugging outcomes without trying to turn them into a polished project story.

The attached `MODEL_DEVELOPMENT_HISTORY.md` from another project was used only as a structural reference. Its subject matter and embedded text were not treated as instructions for this project.

## 2. Evidence method

The reconstruction uses the following labels:

- **[CHAT]** — supported by a preserved conversation. A chat proposal is not automatically treated as implemented; user test results, later discussions, or repository evidence are used where possible.
- **[REPO]** — directly supported by surviving source code, documentation, Git history, tests, or data artifacts.
- **[INFERENCE]** — a cautious conclusion from the sequence of chats and surviving code.
- **[GAP]** — the exact historical state cannot be recovered from the available evidence.

### 2.1 Chat coverage

The historical search found 26 directly relevant chats:

- 15 in **Building simulation model**;
- 2 in **Building model simulation 2.0**;
- 1 in the later **building_model_simulation** project;
- 8 unfiled chats whose titles and content were unambiguously about this project.

The first project chat is dated **15 June 2025**. This reaches the documented beginning of the project, so no older project folder was required to establish its origin. The final 2025 development chat found in the two main folders is dated 24 August 2025. A later migration chat from 8–9 June 2026 documents the notebook-to-package restructuring. **[CHAT]**

The historical attachments themselves were not always recoverable from the chat interface. Where a message says that files were attached but their contents are unavailable, only the surrounding discussion is used. **[GAP]**

### 2.2 Repository coverage

The original 2025 repository history is not preserved in the present Git repository. The current repository has one initial Git commit dated 13 August 2026, so 2025 creation dates come primarily from chats rather than commits. **[REPO] [GAP]**

Several development artifacts survived outside Git:

- a copy of the restructured package dated 8–9 June 2026;
- the Karlsson heat-model paper saved on 1 July 2025;
- a room catalogue saved on 24 August 2025;
- material-register notes dated 8 August 2025;
- large snapshot files dated 13 August 2025, including ten roughly 78–107 MB chunks and one approximately 1.04 GB pickle. **[REPO]**

These artifacts corroborate the chat chronology and, especially, the history-storage problem discussed below.

## 3. Executive summary

The project began as a graph-based 3D building model, not as a fire simulator. Cubes represented spatial cells; walls, floors, ceilings, and roofs were graph components. The first difficult problem was making the topology consistent when separately created cube constellations were merged, carved into rooms, traversed, and visualized. **[CHAT]**

The fire module was added on 19 June 2025. Its first spread model used a per-timestep probability determined by surface type and fire heat. That approach was progressively replaced by a more causal chain:

```text
combustible contents or covers ignite
        ↓
finite heat energy is released
        ↓
cell air temperature rises
        ↓
surfaces degrade and neighboring cells receive heat
        ↓
contents or covers in neighboring cells ignite
        ↓
that cell becomes an active fire
```

By August 2025, the model included rooms, independent paired surfaces, structural and cover materials, finite-energy contents, ignition exposure, growth/plateau/decay heat-release curves, cooling, safety devices, occupants, doors and access control, stairs, a fire department, detailed snapshots, analysis functions, and optional probability distributions. **[CHAT] [REPO]**

In June 2026, the notebook-based nbdev code was reorganized into a conventional package with explicit modules and scenario functions. In August 2026, it was prepared as a public-facing repository with packaging metadata, tests, documentation, a reproducible example, and a stronger statement of limitations. **[CHAT] [REPO]**

The central development pattern was repeated separation of concerns. Coordinate generation was separated from graph construction; physical objects from scenario setup; fire energy from air temperature; ignition from heat release; deterministic parameters from sampled values; simulation execution from history storage; and analysis from the core update loop.

## 4. Module lineage

The names changed during the 2026 restructuring. The table distinguishes the historical notebook/module name from its principal present-day successor.

| Current module | Historical origin | First evidenced period | Main responsibility |
|---|---|---:|---|
| `domain.py` | chiefly `building_core.py` / `01_building_core.ipynb` | initial classes 16 June 2025; separated core visible by late June | Materials, fire behavior, items, safety devices, building components, cubes, rooms, doors, windows, stairs |
| `building_factory.py` | `building_model.py` / `02_building_model.ipynb` | construction functions 16 June 2025 | Coordinates, building graph, surface neighbors, room carving, item placement, sample building, room catalogue, building visualization |
| `fire_simulation.py` | `simulate_fire.py` / `03_simulate_fire.ipynb` | 19 June 2025 | Fire state, ignition, heat release, air temperature, cooling, transfer, degradation, tick orchestration, snapshots |
| `fire_analysis.py` | `analyze_fire.py` and analysis cells | new analysis work 13 July 2025 | Fire changes, temperatures, item energy and heat, agent routes, fire-department actions, loss, visualization |
| `agents.py` | agent classes in the core, then `agents_and_actors.py` | human classes 18 July 2025; dedicated module present by August | Agents, access-aware movement, role subclasses, movement strategies, fire units, fire department |
| `probability_distributions.py` | new probabilistic module | 19 August 2025 | Reusable seeded samplers and distribution plots |
| `scenarios.py` | extracted scenario/setup cells | 8–9 June 2026 | Explicit construction of worlds and complete runs without notebook globals |
| `simulation_runners.py` | run-until-extinguished and chunk functions formerly in analysis | first functions 30 July–13 August 2025; separated June 2026 | Fixed-tick, until-extinguished, chunked, and disk-backed execution |
| `simulation_settings.py` | notebook/script settings blocks | separated June 2026 | Named simulation and snapshot configurations |
| `io_utils.py` | repeated pickle helpers | first used June–July 2025; separated June 2026 | Small persistence helpers |
| `config.py` | path and project constants | separated June 2026 | Package-level configuration |
| `tests/` | `testing_module.py` and notebook test cells | first evidenced 17 June 2025 | Structural invariants and present behavioral regression tests |

The precise day on which `building_core.py` and `agents_and_actors.py` first became separate physical files is not preserved. Their concepts and later module names are clear, but the exact split date remains a **[GAP]**.

## 5. Chronological development

### 5.1 15 June 2025 — nbdev project initialization

The first project chat created an nbdev Python library named `building_model_simulation`. The intended setup used notebooks in `nbs`, an exported library directory, generated documentation, a `main` branch, Python 3.9 or newer, and an initial version of 0.0.1. **[CHAT]**

The first technical obstacle occurred immediately on Windows. `nbdev_new` received a full GitHub URL where a local repository name/path was expected, producing `WinError 123`. The discussion clarified that the library name had to be a valid Python package name rather than a URL or slash-separated repository identifier. **[CHAT]**

This setup established two traits that shaped later work:

1. notebooks were the source of truth and exported `.py` files were generated artifacts;
2. the project grew interactively through notebook cells, which later created execution-order, hidden-global, export, and method-binding problems.

### 5.2 16–18 June 2025 — building graph, composable structures, and rooms

#### Initial blueprint

On 16 June, the program was defined as a model of a building for event simulation. The proposed building was a connected graph whose nodes were object instances: cubes, interior walls, exterior walls, bottom floors, intermediate ceiling/floor slabs, and ceiling roofs. Cubes were unit cells with unique 3D coordinates and six connections. Components also had `items`, anticipating later simulation effects. Interior surfaces could be `hollow`. **[CHAT]**

The first class layer included:

- `Coordinate`;
- `BuildingComponent` with a unique `node_id` and items;
- `Cube`;
- `InteriorWall` and `ExteriorWall`;
- `BottomFloor`, `CeilingFloor`, and `CeilingRoof`.

The building process was initially divided into two functions: create cubes from coordinate tuples, then infer their walls, floors, ceilings, and roofs from adjacency. A two-cube vertical stack was used as an early invariant: two cubes, eight exterior walls, one bottom floor, one shared ceiling/floor slab, and one roof, for 13 nodes total. **[CHAT]**

#### Substructures and one global Euclidean space

The design then introduced reusable cube constellations. Each substructure began at local `(0, 0, 0)`, could be translated to a global origin, and was merged into a larger building. When two translated structures became adjacent, their exterior boundaries had to be replaced by an interior connection. A Matplotlib 3D view was added to verify the coordinates visually. **[CHAT]**

This first implementation became overly complicated because cube instances and graph objects were created at multiple stages. On 17 June, the pipeline was simplified from:

```text
create substructure objects
→ translate object copies
→ merge objects
→ repeatedly rebuild graph
```

to:

```text
create local coordinate list
→ translate coordinates
→ combine all coordinates
→ instantiate cubes once
→ build the complete graph once
```

This change removed `merge_substructure_into_building` from the normal path and made coordinates the stable intermediate representation. **[CHAT]**

#### Graph-integrity problems

Several bugs exposed the importance of object identity and symmetric references:

- repeated graph construction created different wall instances for cubes that should share one connection;
- resetting `cube.interior_walls` inside the graph-building loop erased a wall previously attached from another cube;
- exterior walls were stored as a dictionary while interior walls were a list, causing inconsistent access and `.values()` failures;
- `interior_wall` versus `interior_walls` naming caused lookups and tests to use the wrong attribute;
- a module-level node counter was difficult to import and reset safely;
- top-level notebook test code was exported into the module and ran during import, causing `NameError` for `global_model`;
- equality of `Coordinate` objects was initially ambiguous without `__eq__` and `__hash__`.

The resulting invariants were: create every shared connection exactly once, append it to both cubes, reset connection state before rather than during construction, build the complete graph once, and test bidirectional ownership explicitly. **[CHAT]**

The test suite grew from nine to twelve and then fourteen tests. It checked single cubes, horizontal and vertical pairs, duplicate coordinates, translation, constellation output, unique surface references, and round-trip equivalence. Several reported failures were faults in test assertions rather than in the model—for example, using `{0, 0, 0}` instead of `{(0, 0, 0)}`. **[CHAT]**

#### Room concept and carving

On 17 June, a room was defined as a connected component of cubes reachable through hollow interior walls or hollow ceiling/floor slabs. A single cube with no hollow neighbors was also a room. `find_rooms` used depth-first traversal. **[CHAT]**

On 18 June, room construction became template-based. A local coordinate constellation was translated into an already existing building; instead of adding cubes, it marked every shared internal boundary in the template as hollow. This became `carve_room_shape`. **[CHAT]**

Vertical rooms were substantially harder than horizontal rooms. A 2×2×2 carve often appeared as two 2×2 rooms, and a 3×3×3 carve could split by floor. The underlying model allowed a middle cube to participate in two vertical slabs while the cube stored an insufficient or asymmetric reference. The fixes iterated through:

- checking both floor and ceiling references;
- assigning one shared slab to both cubes;
- distinguishing a cube's bottom and top boundary;
- making shared-component lookup symmetric;
- ensuring all six surfaces remained available for later item effects.

These problems later contributed to a more fundamental redesign in which every cube owned six directional surface objects. **[CHAT]**

#### Early visualization

The first visualizer drew semi-transparent cube faces and coordinate labels. It was then made aware of hollow walls and slabs. Repeated issues included faint Matplotlib edges on transparent faces, incorrect top/bottom ownership, `BottomFloor` lacking a `hollow` attribute, and vertical faces not becoming transparent. Room-size colors were eventually preferred over making all internal faces invisible: rooms of two to forty cells were mapped from green through yellow to red, while single-cell rooms retained the default appearance. **[CHAT]**

### 5.3 19–30 June 2025 — first fire module and transition away from direct probability

#### Creation of `simulate_fire`

On 19 June the user explicitly started a new module to simulate fire. The first version:

- started a fire in a chosen or random cube;
- stored a `FireState` per coordinate;
- advanced in discrete timesteps;
- attempted spread to adjacent cubes with a probability based on the connecting surface type;
- used configurable base values for wall, floor, and ceiling spread;
- increased probability with heat;
- saved state history; and
- visualized burning cells in pink, with darker color intended to represent greater heat. **[CHAT]**

The initial example probabilities—such as wall 0.2, floor 0.05, and ceiling 0.1—were explicitly interpreted as per-neighbor, per-tick probabilities. Custom spread functions were added so probability logic could inspect the exact connecting component rather than only its category. **[CHAT]**

#### Module and visualization problems

The first fire module encountered circular imports between `building_model` and the new simulation module, partly because notebook-exported modules imported one another and also created global models at import time. The fire overlay was repeatedly disconnected from the room visualizer or showed the same state for every requested timestep. The eventual direction was to save snapshots and render a selected historical state using the established building visualization. A Matplotlib `get_cmap` deprecation also triggered the chat title, although it was not the main substantive work. **[CHAT]**

#### Items, fire load, and materials

On 21 June, `Item` became an explicit base class rather than an unstructured list entry. `FireLoad` was introduced for combustible contents. Materials were assigned to surfaces, initially with a `spread_modifier`. Fire load first increased fire-spread probability, but the user rejected that coupling: contents should increase the heat and duration of the fire, while spread should result indirectly from the thermal and boundary conditions. **[CHAT]**

This decision was the first major move away from the original probability-only spread model.

#### Rooms as objects and independent surfaces

From 22 to 24 June, room utilities attempted to group all room components into floor, ceiling, intermediate floor, and directional wall categories. Shared wall objects made direction perspective-dependent: the same physical wall could be “right” from one cube and “left” from the other. Surface counts were frequently missing or assigned to the wrong category. **[CHAT]**

On 23 June, `Room` became a class containing cube coordinates, components, and categorized surfaces. On 24 June, the topology was redesigned: instead of two cubes sharing one wall object, every cube would own its own left, right, front, back, floor, and ceiling surface. Adjacent surfaces would be paired. Exterior status became an attribute of a directional `Wall` rather than a separate graph shape. **[CHAT]**

This design survives in the current repository: each cube owns directional surface instances, and paired boundaries refer to one another through `surface_neighbor`. **[REPO]**

#### Deterministic degradation replaces direct spread probability

On 27 June, two alternatives were considered:

1. retain probability-based spread with heat and material modifiers;
2. let heat degrade the two surfaces separating cells and allow propagation only after the boundary failed.

The second approach was selected. Degradation began at 100 and decreased under sustained heat. For paired boundaries, the first experimental rule degraded one surface fully and then the other. `spread_probs` and `spread_modifier` became redundant in the deterministic path. **[CHAT]**

The fire state also acquired burn time and a heat cap. Formula functions were separated for easier inspection. Early heat increase used an exponential baseline plus a fire-load factor, but an empty cube then risked zero growth or, after other changes, unbounded growth. These issues led to later removal of artificial baseline growth. **[CHAT]**

#### Object-identity and degradation debugging

Between 28 and 30 June, a long debugging sequence investigated why the simulation appeared to spread fire while inspected surfaces still showed degradation 100. The work checked wall identity, material identity, deep copies, global-model imports, history snapshots, and whether the simulation held the same model object. **[CHAT]**

Several distinct issues were uncovered over the sequence:

- some test runs were using newly created global models;
- degradation belonged to the surface, not to the reusable `Material` object;
- some update functions were not reached because adjacency helpers returned nothing;
- `get_adjacent_components` assigned a local `surface` but failed to append it to the return list in one version;
- the joint-degradation function's `if/elif` could leave the second surface undegraded;
- fire could be marked as spread without the expected self-surface update.

The final simplified rule at that stage degraded the burning cube's boundary and the neighbor's mirrored boundary separately, then permitted spread when both reached zero. **[CHAT]**

### 5.4 1–5 July 2025 — literature-informed heat, ignition, and surface-neighbor topology

#### Karlsson paper and material parameters

On 1 July, the project used a saved paper by Björn Karlsson concerning heat release in the room-corner test. Discussion of Table I introduced or clarified:

- maximum heat-release rate, `q_max`;
- decay constant, `lambda_decay`;
- ignition exposure time, `t_ignition`;
- later, ignition temperature;
- the difference between ignition delay and structural burn resistance. **[CHAT] [REPO]**

The material model expanded accordingly. Structural materials and cover materials were separated because a concrete or brick structural layer and a combustible wall covering play different roles. Structural material controlled degradation resistance; cover material could ignite and release heat. Registers were created for both categories. **[CHAT]**

`burn_resistance` was normalized conceptually to 0–1. The degradation rule changed from division by resistance to a tunable damage expression of the form:

```text
damage = c × temperature × (1 − burn_resistance)
degradation = degradation − damage
```

The current code retains this family of rule, applies it only above a threshold temperature, and clamps degradation at zero. **[CHAT] [REPO]**

#### One tick equals one nominal second

On 2 July, the timestep was explicitly interpreted as one second. This made realistic degradation and ignition durations require many ticks. Rather than enlarging the timestep, the selected solution was to retain one-second updates but save snapshots only every configurable number of seconds. **[CHAT]**

#### Fire energy versus cell air temperature

The model had previously used `FireState.heat` ambiguously as fire intensity, temperature, and accumulated energy. On 2 July, `Cube.air_temp` was added so even a non-burning cell had a temperature. The temporary idea of renaming heat to `fire_temp` was rejected to avoid widespread breakage. **[CHAT]**

The durable conceptual split became:

- `FireState.heat`: energy accumulated from currently burning contents/covers during a tick;
- `Cube.air_temp`: a persistent environmental temperature;
- ignition: continuous exposure of an item's or cover's `FireBehavior` to sufficient `air_temp`;
- degradation: later based on `air_temp`, not directly on fire energy. **[CHAT] [REPO]**

#### Surface ignition and directional debugging

Cover ignition became dependent on air temperature exceeding a material ignition temperature continuously for `t_ignition` seconds. Equal surfaces in the same cube were expected to behave deterministically and identically. When only some walls degraded, debug traces revealed that surfaces could be processed multiple times in one tick and that front/back direction labels were being interpreted from different viewpoints. A consistent global convention was established: all surfaces of a given direction face the same coordinate direction. **[CHAT]**

#### `surface_neighbor`

Horizontal propagation eventually worked, but vertical propagation and mirrored-surface lookup remained fragile. On 5 July, each surface class gained `surface_neighbor`: a direct reference to the paired surface in the adjacent cube. Initialization was moved into building-graph construction. Room carving then marked both surfaces in each paired boundary hollow. **[CHAT]**

This removed repeated directional searches from the fire loop and later allowed doors and stairs to be attached symmetrically. The current `initialize_surface_neighbors` function is a direct descendant of this decision. **[REPO]**

#### Hollow-room spread was deliberately not instantaneous

There was a temporary recursive breadth-first implementation that could propagate through all hollow boundaries within one tick. The user explicitly rejected simply igniting an entire room at once: hollow boundaries should permit controlled propagation, not simultaneous ignition of every cell. **[CHAT]**

That concern led to the more physical heat-transfer interpretation completed on 11 July.

### 5.5 5–11 July 2025 — composition-based fire behavior and heat transfer before ignition

#### From `FireLoad` subclass to `Item` plus `FireBehavior`

The item model was reorganized around composition. `Item` remained the common attachable object. Combustible behavior moved into a separate `FireBehavior` object containing a material, mass, ignition state, exposure time, heat release, and burnout state. Non-combustible objects such as alarms and sprinklers could still be items without a fire behavior. Monetary value became an optional property. **[CHAT]**

`InventoryItem` was introduced for furniture and contents. The early catalogue included a wooden chair and piano, followed by office and storage contents. Items could be placed intentionally into named coordinates with `initialize_items_in_cubes`, while the item catalogue and quantity syntax were retained. Both cubes and surfaces inherited `items` from `BuildingComponent`, but free-standing furniture was normally associated with the cube. **[CHAT]**

#### Heat-release chain

The intended chain became explicit:

```text
Item or cover FireBehavior.heat_release(...)
→ total heat increment in the cube
→ FireState.heat
→ conversion to Cube.air_temp
→ ignition/degradation/transfer decisions
```

Ignition updates remained separate from formula functions to avoid state-changing side effects inside heat calculations. **[CHAT]**

#### Module diagrams and refactoring

On 7–8 July, the project had become large enough that the user requested layered architecture, class hierarchy, and function-call trees. Graphviz and Mermaid were tried but were difficult to install or visually unsatisfactory in the notebook environment. Plain-text trees became the practical documentation method. **[CHAT]**

The diagrams exposed duplicated or misplaced logic. Item ignition was renamed and separated from surface ignition. Helper functions were extracted from `tick`. This was an early precursor of the August partitioning of the tick loop and the later 2026 modular package. **[CHAT]**

#### The key fire-spread conceptual change

On 11 July, the user questioned why opening or degrading a boundary immediately set the neighboring cube's `is_on_fire` state. The rule was changed:

- a hollow, open, or sufficiently degraded connection allows heat transfer;
- the neighboring cube's air temperature rises;
- its contents and covers undergo their own ignition checks;
- only their ignition marks the neighboring cube as burning.

The helper was renamed `transfer_heat_between_cubes`, and the recursive queue became unnecessary. This slowed room propagation and separated transport from combustion. **[CHAT]**

The present code retains this structure: boundary conditions control transfer, while ignition status is derived from local active fire behaviors. **[REPO]**

### 5.6 13–30 July 2025 — analysis, safety systems, agents, access, and cooling

#### Analysis and economic loss

On 13 July, a new analysis module was started. Its first task was to inspect inventory items after a run and sum the value of those that ignited. The definition was narrowed carefully: an inventory item was counted as lost only if it had ignited. This became the lineage of `calculate_inventory_loss`. **[CHAT] [REPO]**

Further analysis functions logged fire-state changes, visualized fire over the building, and later plotted air temperatures, remaining item energy, heat output, agent routes, and fire-department actions. **[CHAT] [REPO]**

#### Ignition and method-binding bugs

July 13–15 debugging focused on items that were flagged as ignited but returned no heat, ignition time offsets, and a surface ignition function receiving arguments in the wrong positions. The final cause of one major issue was that a function had been converted into a method but still had the old signature, so `self` shifted all arguments. **[CHAT]**

The episode also clarified that `Cube.get_all_components` included the cube itself, while surface ignition required a surface-only iterator. `get_all_surfaces` was added for this distinction. **[CHAT]**

#### Fire-safety devices

On 16 July, a `FireSafetyItem` abstraction was created, followed by specialized `Sprinkler` and `SmokeAlarm` classes. Important properties included trigger temperature, reliability, active/triggered state, maintenance metadata, range, and response behavior. **[CHAT]**

The sprinkler design evolved from two overlapping cooling parameters to one suppression effect. It was intended to reduce fire energy, which would then affect air temperature through the normal energy conversion. Trigger conditions moved from transient `FireState.heat` to persistent `Cube.air_temp`. **[CHAT]**

Safety devices were initially placed in `cube.items`, while the update loop searched surfaces. Separate placement on surfaces was added. Later, room and radius logic allowed a device to affect more than its mounting cell. Smoke alarms could conceptually detect within the room/range, while sprinkler effects required a hollow path so walls could block water. **[CHAT]**

#### Agents and building accessories

On 18 July, a `Human` superclass was proposed and then generalized to `Agent`. `OfficeStaff` and `Janitor` captured different awareness and competence. Panic was intended to change dynamically. Agents had health, role, location, speed, items, and a path. Speed was defined as the number of ticks required to move between cells. **[CHAT]**

Doors, windows, ladders/stairs, and similar objects became `BuildingAccessory` items. Doors and windows received fire behavior and open/closed, locked, and blocked states. `AccessCard` and `AccessPanel` governed who could unlock a door. A paired door object was attached to both surfaces of a boundary so both cubes referred to the same opening. **[CHAT]**

Stairs were added on 28 July. The same paired-item helper was reused. Open doors and stairs became alternate ways for transfer or passage even when the structural surfaces themselves were not hollow. The shared property eventually became `allows_passage`. **[CHAT] [REPO]**

#### Running until extinction and thermal runaway

On 30 July, a runner was requested that continued until no fires remained. At the same time, an example reached an air temperature above 1.4 million in model units. Artificial exponential baseline growth was removed, finite object energy was expected to stop combustion, cooling was introduced, and air-temperature caps were discussed. **[CHAT]**

The current thermal layer includes finite energy, temperature-dependent transfer efficiency, a maximum cell-air temperature, Newtonian/radiative-like cooling, and no mandatory artificial baseline-growth term. These remain simplified modelling rules rather than a validated heat-balance solver. **[REPO]**

### 5.7 4–13 August 2025 — tick decomposition, mature heat-release curve, and scalable history

#### Breaking up the tick loop

On 4 August, the single large `tick` function was partitioned into helpers for preparation, ignition, burning-cube processing, suppression, heat/degradation updates, neighbor transfer, movement, cooling, and later fire-department processing. Missing helper calls were checked against the intended call tree. **[CHAT]**

The present `tick` is a short orchestrator calling these stages, although the current source retains the notebook-era pattern of defining many functions at module scope and binding them to classes. **[REPO]**

#### Heat-release curve evolution

Early item heat release used immediate peak output followed by `q_max × exp(−lambda × t)`. The user identified that a realistic object should normally grow to a peak, possibly hold a plateau, and then decay. `t_peak` was introduced on 4 August. Several candidate formulas were examined, including a t-squared growth curve and piecewise growth/decay. **[CHAT]**

On 12 August, the design was rebuilt around:

- continuous temperature exposure for ignition;
- a growth phase;
- an optional plateau;
- exponential decay;
- finite energy calculated from mass and energy density;
- per-tick integration of heat-release rate;
- automatic burnout when energy was exhausted or the decay tail became negligible.

Surface covers became `CoverMaterialItem` instances with their own `FireBehavior`, rather than raw `Material` objects. This unified free-standing contents and combustible covers under the same combustion mechanism. **[CHAT]**

The current `FireBehavior` precomputes an energy-feasible growth/hold/decay curve, integrates kW over the elapsed timestep to kJ, clips to remaining energy, and clears ignition at burnout. **[REPO]**

#### Extinction-state bugs

Repeated August bugs left cubes marked on fire after all contained objects had stopped producing heat. Part of the problem was duplicate ignition flags on surfaces and their cover fire behaviors. The design converged on `FireBehavior` as the source of combustion state, while legacy surface flags were synchronized with the cover's `FireBehavior` rather than allowed to drift independently. Cube activity became a derived property of active contents and covers rather than a permanently latched event. **[CHAT]**

#### Configurable snapshots and analysis serialization

Snapshots evolved through several stages:

1. fire-state copies only;
2. optional deep copies of the full model;
3. interval-based capture;
4. a dictionary keyed by tick;
5. selected fields such as fire status, air temperature, components, agents, and fire department;
6. explicit serializers for surfaces, covers, items, and agents.

This supported plots of remaining energy and per-item heat output without depending on mutated live objects. Duplicate surfaces and unclear labels in plots led to further serializer fixes. **[CHAT]**

The memory cost was severe. A one-gigabyte snapshot file and several hundred-megabyte chunk sequences survive from 13 August. Chunked run/save functions were introduced so long runs could be performed in bounded groups and written to disk. **[CHAT] [REPO]**

One attempted chunk-saving workflow accidentally overwrote the data folder. The chat records the loss and an immediate return to the original code before redesigning the runner with explicit output paths and numbered `snapshot_data_{chunk}` files. This is an important historical failure and explains the later emphasis on `out_dir`, file naming, and separation of run and persistence functions. **[CHAT]**

### 5.8 13–18 August 2025 — access-aware movement and fire department

#### Agent movement integration

On 14 August, fixed agent paths were integrated into the simulation. Movement checked directional paired surfaces directly through `surface_neighbor`. It respected doors, locks, access panels, access cards, stairs, fire, and high-temperature hazards. **[CHAT]**

The work also exposed registry aliasing: retrieving the same registered agent or door twice returned the same mutable object. Factory functions or deep copies were introduced so repeated placements produced distinct instances, except where the same physical paired door intentionally had to be shared across two surfaces. **[CHAT]**

Agent snapshots and route DataFrames were added on 15 August. **[CHAT] [REPO]**

#### `FireDepartment` and `FireUnit`

The first explicit fire-department design appeared on 13 August. `FireUnit` represented a responding crew; `FireDepartment` was a high-level incident controller with alarm reception, ETA, unit movement, suppression, opening egress, forced entry, and search and rescue. It depended on callbacks into the simulation for fire state, temperature, pathfinding, and exits. **[CHAT]**

Integration occurred on 15–18 August:

- triggered alarms notified the department;
- units counted down response time and moved to alarm coordinates;
- exits were discovered from building accessories marked `is_exit`;
- nearby agents could be assigned paths to exits;
- units could unlock or force openings;
- action history was added to snapshots and analysis.

An initial ventilation tactic was removed because opening windows had no oxygen/ventilation coupling and would imply unsupported physics. Only opening useful egress points was retained. **[CHAT]**

Suppression also changed. The first sketch cooled `FireState.heat` and cell air directly. Later, the user required water to act on burning objects and covers so their heat output fell and they could extinguish. Water reach was constrained by distance and, later, by hollow or degraded boundaries. **[CHAT]**

One difficult integration bug occurred because notebook methods were defined outside the class and bound later. The exported binding cell had been omitted, so the loaded `FireDepartment` class had no `step` method despite the notebook showing one. Exporting the binding cell fixed it. **[CHAT]**

### 5.9 19–24 August 2025 — deterministic baseline plus optional probability and continuous movement

#### Probability module

On 19 August, the project was explicitly described as a deterministic five-module model. A sixth module was created to hold probability distributions without replacing the deterministic baseline. **[CHAT]**

Reusable samplers were added for:

- lognormal;
- normal;
- exponential;
- gamma;
- Weibull;
- uniform;
- beta;
- Bernoulli.

Each had a corresponding plotting helper. The fire-department ETA was the first example. Poisson was rejected because it models counts; positive, right-skewed response time was better represented by lognormal, gamma, or Weibull, with lognormal selected for the initial implementation. **[CHAT]**

The simulation acquired a `probabilistic` mode while retaining fixed defaults. Reproducible NumPy generators were discussed so all subsystems could share controlled randomness. **[CHAT]**

#### Device variability

Sprinkler trigger temperature, effective suppression duration, reliability, and smoke-alarm behavior were candidates for stochastic treatment. The design distinguished:

- device-level traits drawn once and retained;
- incident-level values redrawn before each run.

`enable_probabilistic_devices` chose the mode and built samplers; `reset_probabilistic_params` drew a new incident realization. A small `ProbabilisticDeviceMixin` was preferred over adding probability methods to every item. **[CHAT]**

A failure occurred when objects constructed with `probabilistic=False` were later switched only by setting the flag: their samplers had never been built. Explicit `enable_probabilistic` hooks resolved this. **[CHAT]**

#### Role-weighted continuous movement

On 22–24 August, finite agent paths were replaced conceptually by a movement strategy that could continue for an entire simulation. Agents selected goals from named room categories with role-specific weights, followed a short path, and chose a new goal when needed. Weights did not need to sum to one because target selection normalized them. **[CHAT]**

The `room_catalogue.pkl` artifact dated 24 August corroborates the named-room catalogue work. The current `WeightedTargetSelector` and `GoalOrientedRandomWalk` implement this lineage. **[REPO]**

### 5.10 8–9 June 2026 — migration from notebooks to a conventional package

After a development hiatus in the recovered chats, the notebook project was reopened in Spyder. Jupyter installation and nbdev environment problems prompted a decision to convert the notebooks into ordinary Python files. Simply running exported files in sequence produced missing globals such as `john_janitor` and import behavior that no longer matched notebook execution. **[CHAT]**

The project was therefore restructured into the present conceptual package:

- `domain.py` for the simulation vocabulary;
- `building_factory.py` for construction;
- `agents.py` for people, movement, and emergency response;
- `fire_simulation.py` for the update engine;
- `fire_analysis.py` for inspection and plots;
- `probability_distributions.py` for stochastic helpers;
- `scenarios.py` for explicit object composition;
- `simulation_runners.py` and `simulation_settings.py` for execution modes;
- `io_utils.py` and `config.py` for support concerns.

The crucial change was that package modules contained definitions rather than relying on notebook cells to have created global objects. Scenario functions explicitly created `global_model`, agents, fire department, settings, and runs. **[CHAT] [REPO]**

Run modes were separated into fixed-tick, until-extinguished, full-history, chunked-history, and chunk-to-disk variants. Analysis remained in `fire_analysis` rather than a second overlapping analysis module. **[CHAT] [REPO]**

### 5.11 August 2026 — public repository preparation

The present Git repository was initialized on 13 August 2026. It now includes:

- a `pyproject.toml` package definition and minimal dependency list;
- MIT license text;
- `.gitignore` rules excluding local data, outputs, and generated artifacts;
- a README with architecture, installation, example, limitations, and data provenance;
- lightweight behavioral tests;
- a reproducible example scenario;
- a model-assumptions document explicitly stating that the project is exploratory and not a validated fire-engineering tool. **[REPO]**

The public example uses the built-in 5×5×2, 50-cell building, two occupants, a configured fire department, a seed of 2026, and 120 ticks. The recorded reference run reached 434.65 °C maximum modelled cell temperature and retained four burning cells at the final saved tick. These are synthetic regression/demo outputs, not validation results. **[REPO]**

## 6. How the major ideas evolved

### 6.1 Building representation

```text
Shared graph nodes for physical walls/slabs
        ↓
translated cube substructures with repeated graph rebuilds
        ↓
coordinates first, cubes once, graph once
        ↓
every cube owns six directional surfaces
        ↓
adjacent surfaces linked by surface_neighbor
        ↓
doors/stairs/accessories define passage across paired boundaries
```

The independent-surface model increased object count but simplified direction, room categorization, per-side material state, degradation, access, and transfer. It is one of the project's most consequential architectural changes.

### 6.2 Room representation

```text
room = DFS component through hollow shared graph nodes
        ↓
room templates carve hollow connections into an existing building
        ↓
Room class stores cells, components, and directional surface groups
        ↓
rooms linked to cells and named in a catalogue
        ↓
room/radius/hollow-path queries support alarms, sprinklers, and movement
```

Rooms never became independent volumes with a single thermodynamic state. They remain groups of cells connected by traversable/hollow boundaries. **[REPO]**

### 6.3 Fire spread

The word “spread” referred to different mechanisms at different times:

1. **19 June:** direct probability that a burning cell ignites a neighbor during a tick.
2. **21 June:** probability modified by heat, materials, and fire load.
3. **27 June:** deterministic permission after paired surfaces degrade.
4. **5 July:** hollow or degraded paired surfaces permit recursive propagation.
5. **11 July onward:** an open/hollow/degraded boundary permits heat transfer; the target cell becomes a fire only after its own contents or covers ignite.
6. **19 August onward:** deterministic thermal logic remains the baseline, while device and response parameters can be sampled per run.

The current design is closest to stage 5 with optional stochastic subsystems. **[REPO]**

### 6.4 Heat and combustion

```text
heat += fixed amount
        ↓
exponential baseline plus lumped fireload factor
        ↓
q_max × exponential decay for ignited contents
        ↓
mass and energy density limit total energy
        ↓
t_peak adds an initial growth phase
        ↓
energy-feasible growth → plateau → exponential decay
        ↓
integrated kW over each tick produces kJ added to FireState
```

This work also separated persistent cell air temperature from transient accumulated fire energy and introduced temperature-dependent heating efficiency plus cooling.

### 6.5 Items and fire behavior

The model moved from dictionaries and a monolithic `FireLoad` subclass to composition:

```text
Item
├── optional monetary value
├── optional FireBehavior
└── subtype-specific behavior

FireBehavior
├── Material parameters
├── mass and total energy
├── continuous-exposure ignition
├── heat-release curve
└── burnout state
```

This allowed inventory, cover layers, safety devices, access cards, access panels, doors, windows, and stairs to share the same attachable-object infrastructure without pretending that all items burn.

### 6.6 State and history

The history system changed from a visual convenience into a major subsystem. It had to preserve enough state to reconstruct fire, temperature, components, contents, agents, and emergency response without retaining unusable references to live objects. The large 2025 pickle files demonstrate that full deep-copy history did not scale. The later selected-field serializers and chunked runners were direct responses to this cost.

### 6.7 Deterministic and probabilistic layers

The deterministic formulas were deliberately retained as a baseline. Probability was added as configuration around selected parameters, not as a separate replacement simulation. This supports comparisons between fixed runs and stochastic runs and is compatible with seeded reproducibility. The current repository provides the sampling primitives and probabilistic-device hooks, but it does not yet present a complete calibrated Monte Carlo study. **[REPO]**

## 7. Major problem catalogue

| Period | Problem | Consequence | Resolution or current status |
|---|---|---|---|
| 15 June | nbdev treated a GitHub URL as a Windows path | project creation failed | use valid local repo/package names |
| 16–18 June | graph built multiple times | duplicate, stale, or non-shared walls | combine coordinates, instantiate once, build graph once |
| 17 June | connection lists reset inside cube loop | previously attached walls disappeared | reset all cubes before construction |
| 17 June | exterior/interior wall containers differed | access and test errors | normalize the interfaces |
| 17–18 June | middle cubes needed two vertical boundaries | five-surface cubes and failed vertical rooms | distinct top/bottom surfaces; later six independent surfaces |
| 18 June | room carving split by floor | incorrect room topology | symmetric paired surfaces and vertical traversal |
| 18–19 June | transparent faces retained edges or wrong ownership | misleading visualizer | per-face alpha/edge logic; later room colors |
| 21 June | circular imports and top-level notebook code | partially initialized modules | reduce import-time execution; later explicit scenarios |
| 22–25 June | shared wall direction was perspective-dependent | missing/misclassified room surfaces | one directional surface per cube plus paired neighbor |
| 28–30 June | live surfaces appeared unchanged | misleading degradation inspection | fix object sourcing, adjacency return, and surface—not material—state |
| 2–4 July | heat conflated energy and temperature | unrealistic ignition and runaway values | separate `FireState.heat` from `Cube.air_temp` |
| 5 July | horizontal transfer worked but vertical did not | multi-floor rooms failed | initialize `surface_neighbor` for walls, floors, and ceilings |
| 13–15 July | ignition method arguments shifted | cube, surface, and simulation objects exchanged roles | add `self` and use surface-only iterators |
| 16–17 July | safety devices placed where update loop did not search | sprinklers/alarms never triggered | explicit surface placement and room/range logic |
| 30 July–12 August | heat grew to extreme values | implausible cell temperatures | remove artificial baseline, finite energy, cooling, caps, reduced efficiency at high temperature |
| 9–12 August | duplicate surface and fire-behavior ignition flags | fires stayed active or plots disagreed | use `FireBehavior` as the combustion source and synchronize wrapper flags |
| 10–13 August | full history consumed large memory/disk | slow loading and gigabyte pickles | selected fields, serializers, chunked execution |
| 13 August | output code overwrote the data directory | material local data loss | restart from original code; explicit output directory and numbered files |
| 14 August | registries returned the same mutable instance | agents, doors, and paths interfered | factories/deep copies except intentional paired sharing |
| 17 August | exported `FireDepartment` lacked bound methods | `step` missing at runtime | export the notebook binding cell |
| 21 August | probabilistic flag enabled without samplers | device sampling attributes missing | explicit enable hooks and probabilistic mixin |
| June 2026 | converted scripts depended on notebook globals | names and imports missing in Spyder | package definitions plus explicit scenario functions |

## 8. Current module contents and their historical role

### 8.1 `domain.py`

This is the present vocabulary layer. It contains the descendants of the earliest graph classes and most 2025 object catalogues:

- coordinates and building-component base classes;
- materials and parameter registers;
- `FireBehavior`;
- generic, cover, inventory, miscellaneous, safety, and access items;
- probabilistic-device support;
- walls, floors, ceilings, roofs, cubes, and rooms;
- sprinklers and smoke alarms;
- doors, windows, and stairs.

Its historical purpose was to answer “what exists in the simulated world?” It should not construct a particular sample building or run a scenario. **[REPO]**

### 8.2 `building_factory.py`

This module implements the coordinate-first construction pipeline established in June 2025. It creates constellations, translates them, builds cubes and directional surfaces, initializes reciprocal surface neighbors, carves rooms, modifies surface materials, places objects, attaches paired accessories, creates named rooms, visualizes the building, and constructs the built-in sample world. **[REPO]**

### 8.3 `fire_simulation.py`

This is the timestep engine created on 19 June 2025. Its present stages include:

- explicit or random fire start;
- item and cover ignition updates;
- finite heat release and energy accumulation;
- conversion to air temperature;
- cooling and inter-cell transfer;
- surface degradation;
- boundary permission through hollow/degraded/open connections;
- safety-device suppression;
- agent movement;
- fire-department processing;
- selected-field history snapshots.

The current module retains an unusual notebook inheritance: numerous functions are defined at module level and then assigned to `FireSimulation`. This works but makes method discovery and static analysis harder. **[REPO]**

### 8.4 `fire_analysis.py`

The analysis module grew from the inventory-loss request of 13 July. It now covers fire-state changes, agent routes, fire-department action tables, inventory loss, 3D fire/building views, air-temperature plots, remaining-energy plots, and heat-output plots. **[CHAT] [REPO]**

### 8.5 `agents.py`

The module combines two historical layers:

- occupants and staff with access-aware movement;
- the organizational emergency-response controller.

It includes `Agent`, `OfficeStaff`, `Janitor`, `FireUnit`, `FireDepartment`, access and passage checks, suppression and search helpers, weighted room targets, goal-oriented random movement, and default-agent factories. **[REPO]**

### 8.6 `probability_distributions.py`

The module created in August 2025 centralizes NumPy-based sampler closures and optional diagnostic plots. It exists so model classes can consume distributions without embedding distribution mathematics throughout the domain and simulation code. **[CHAT] [REPO]**

### 8.7 Orchestration and support modules

`scenarios.py`, `simulation_runners.py`, `simulation_settings.py`, `io_utils.py`, and `config.py` were extracted during the June 2026 migration. They make dependencies and execution modes explicit and keep construction, running, persistence, and analysis out of the domain classes. **[CHAT] [REPO]**

## 9. Tests and experiments over time

The project used small structural experiments from the start:

- one cube;
- two horizontal cubes;
- two and three vertically stacked cubes;
- 2×2×2 and 3×3×3 room carving;
- assertions about unique walls and six surfaces;
- deterministic material comparisons;
- burning-cell visual overlays;
- long until-extinguished simulations;
- seeded probabilistic examples;
- agent access-card and locked-door tests;
- fire-department smoke tests.

The test history was uneven because many tests lived in notebook cells and were repeatedly rewritten as the architecture changed. The current public repository contains focused behavioral tests for construction, reciprocal adjacency, rooms, ignition, cool-world stability, history progression, seeded reproducibility, in-bounds movement, and response timing. **[CHAT] [REPO]**

The public example's fixed output should be treated as a regression demonstration only. No recovered chat or repository evidence establishes calibration against experimental fire data. **[REPO]**

## 10. Current limitations and open questions

1. **Parameter provenance and validation.** Most material, safety-device, occupant, and response parameters remain modelling inputs rather than a validated database. Each needs source tracing, units, sensitivity analysis, and experimental validation. **[REPO]**

2. **Thermodynamics.** The cell-air, cooling, transfer, and degradation formulas are lumped approximations. The model does not solve fluid flow, smoke transport, oxygen availability, ventilation, structural mechanics, or CFD. **[REPO]**

3. **Room thermodynamics.** A room is still a graph grouping of cells, not a single mixed-volume heat and smoke zone. **[REPO]**

4. **Probability calibration.** The sampler infrastructure is present, but distribution parameters are not shown to have been fitted to observed data. **[REPO]**

5. **Agent behavior.** Goal-oriented movement and access logic exist, but panic, perception, health effects, evacuation decisions, and dynamic replanning remain simplified. **[REPO]**

6. **Emergency response.** Dispatch, movement, water reach, forced entry, suppression, and search are abstractions. Tactics removed from the model, such as ventilation, should not be reintroduced without modelling their physical consequences. **[CHAT] [REPO]**

7. **Historical reproducibility.** The 2025 Git state and several chat attachments are missing. Exact code at every conversational decision point cannot be reconstructed. **[GAP]**

8. **Notebook-era method binding.** The present source still contains functions bound onto classes after definition. A future internal refactor could place methods directly in classes, but it should be behavior-preserving and covered by tests. **[REPO]**

9. **History scale.** Full component snapshots remain inherently expensive. Long Monte Carlo work will require compact event logs, incremental storage, or an analysis-specific schema rather than unrestricted object snapshots. **[INFERENCE]**

## 11. Central throughline

The project did not develop by adding fire to a finished building model. The topology and the fire model changed each other continuously.

- Rooms forced shared graph components to become directional paired surfaces.
- Directional surfaces enabled per-side materials, doors, stairs, degradation, and water reach.
- Materials and fire load forced heat to be separated from probability.
- Heat forced fire energy to be separated from air temperature.
- Air temperature allowed transport to be separated from ignition.
- Finite combustion forced history to capture object-level energy and state.
- Safety systems and agents forced rooms to support range, passage, access, and named destinations.
- Long histories forced running, storage, and analysis into separate layers.
- Probabilistic experiments forced configuration to be separated from per-run random realization.
- Leaving notebooks forced all hidden dependencies to become explicit scenario construction.

The present package is therefore best understood as the result of repeated attempts to make state ownership and causality explicit.

## Appendix A — recovered chat inventory

### Building simulation model

1. **Start nbdev Project** — 15 June 2025
2. **Building Model Blueprint Review** — 16 June–1 July 2025
3. **Matplotlib deprecation fix** — 19–30 June 2025
4. **Table I Fundamentals Summary** — 1–5 July 2025
5. **Surface neighbor initialization** — 5–6 July 2025
6. **Fireload Ignition Debugging** — 6–7 July 2025
7. **Module function diagram** — 8–11 July 2025
8. **Building Simulation Model Overview** — 13–15 July 2025
9. **Fire safety systems term** — 16–19 July 2025
10. **Fix Janitor class error** — 19–28 July 2025
11. **Flammable copy machine model** — 29–30 July 2025
12. **Function partitioning suggestion** — 4–7 August 2025
13. **Lower lambda decay values** — 8 August 2025
14. **Check stop burning logic** — 9 August 2025
15. **Code comparison explanation** — 9 August 2025

### Building model simulation 2.0

16. **Module summary** — 19–21 August 2025
17. **Smoke alarm setup sketch** — 22–24 August 2025

### building_model_simulation

18. **Running Jupyter Lab in Spyder** — 8–9 June 2026

### Relevant chats outside the project folders

19. **Objektmodifiering i Python** — 30 June 2025
20. **Renaming heat to fire_temp** — 2 July 2025
21. **Check simulate_fire module** — 9 August 2025
22. **Bug audit and fixes** — 10–11 August 2025
23. **Softening multiplier decay** — 11 August 2025
24. **Heat output curve explanation** — 12 August 2025
25. **Heat output curve formula** — 12–13 August 2025
26. **FireDepartment class sketch** — 13–18 August 2025

## Appendix B — surviving dated artifacts

| Artifact | Date | Historical significance |
|---|---:|---|
| `heat_model.pdf` | 1 July 2025 | source discussed when `q_max`, decay, and ignition parameters were introduced |
| `full_lambda_decay_registers.txt` | 8 August 2025 | preserved material-register tuning work |
| `snapshot_data.pkl` | 13 August 2025 | approximately 1.04 GB; evidence of full-history scale problem |
| `snapshot_data_0.pkl` … `snapshot_data_9.pkl` | 13 August 2025 | chunked-history experiment |
| `room_catalogue.pkl` | 24 August 2025 | named-room catalogue used for weighted agent movement |
| restructured Python package (now `building_fire_simulation`) | 8–9 June 2026 | notebook-free Spyder/package migration |
| current Git initial commit | 13 August 2026 | public repository baseline |
