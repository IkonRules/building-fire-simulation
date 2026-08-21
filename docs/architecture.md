# Building Fire Simulation Architecture

Building Fire Simulation is a layered exploratory model built around one shared,
mutable three-dimensional world. This document is the technical counterpart to
[`modelling_approach.md`](modelling_approach.md) and describes the current Python
implementation rather than the historical order in which it was developed.

The conceptual pipeline is:

```text
[Building] -> [Objects and materials] -> [Fire dynamics] -> [Safety, occupants and response] -> [Execution and history] -> [Analysis]
```

Probability is a cross-cutting input mechanism. It can replace selected fixed
parameters with sampled values before or during a run; it is not a fire-spread
stage and does not form a second simulation engine.

---

## 1. System overview

The runtime is organized around a coordinate-to-`Cube` mapping and a
`FireSimulation` instance that advances the objects stored in that mapping.
The repository keeps the reusable model and its consumers visibly separate:

| Repository area | Boundary |
| --- | --- |
| `src/building_fire_simulation/` | Installable package: domain, construction, simulation, runners, scenarios, persistence support and analysis |
| `demo/` | One reproducible public consumer that builds a fresh world and writes curated outputs |
| `scripts/` | Optional specialist consumers for local serialization, long/chunked runs and interactive analysis |
| `docs/` | Modelling rationale, implementation architecture and assumptions |
| `tests/` | Behavioural and package-integration checks |

Neither `demo/` nor `scripts/` is imported by the package. They depend on the
installed `building_fire_simulation` namespace and demonstrate or extend normal
consumer workflows.

```text
                       optional sampled parameters
                                  |
                                  v
[scenario settings] -> [building + domain objects] -> [FireSimulation.tick()]
                                                        |
                                                        v
                                              [selected snapshots]
                                                        |
                                                        v
                                                   [analysis]
```

The main responsibility boundaries are:

| Responsibility | Current owner |
| --- | --- |
| Model vocabulary and object state | `domain.py` |
| Coordinate-first world construction and placement | `building_factory.py` |
| Occupant passage, movement strategies and emergency response | `agents.py` |
| Ignition, heat, temperature, degradation, transfer and tick orchestration | `fire_simulation.py` |
| Optional distribution constructors | `probability_distributions.py` |
| Built-in world composition | `scenarios.py` |
| Named execution defaults | `simulation_settings.py` |
| Fixed, stop-condition and chunked execution | `simulation_runners.py` |
| Snapshot consumers and plots | `fire_analysis.py` |
| Repository-relative paths and generic pickle I/O | `config.py`, `io_utils.py` |

The strongest integrated path in the public repository is the built-in sample
world. The lower layers can represent another coordinate-built world, but the
repository does not yet expose a general declarative scenario schema or file
format.

## 2. Building representation

### 2.1 Coordinates and cube ownership

At runtime, a building is normally a dictionary:

```python
global_model: dict[tuple[int, int, int], Cube]
```

The dictionary key is the canonical tuple coordinate. Each `Cube` also owns a
`Coordinate` object containing the same `(x, y, z)` values. A cube carries:

- direct `items` inherited from `BuildingComponent`;
- persistent `air_temp`;
- an optional room reference;
- a convenience `is_on_fire` flag; and
- directional references to four walls, a floor and a ceiling.

`domain.py` also defines `CeilingRoof`, and `Cube` has a `roof` slot, but the
current `build_building_graph()` path constructs walls, floors and ceilings only.

### 2.2 Coordinate-first construction

`building_factory.py` separates spatial definition from object construction:

```text
create_constellation()
    -> translate_coordinates()
    -> combine coordinate sets
    -> build_model_from_coords()
    -> build_building_graph()
    -> initialize_surface_neighbors()
    -> carve rooms and configure objects
```

`build_model_from_coords()` instantiates one `Cube` per coordinate.
`build_building_graph()` then creates the directional surfaces owned by each
cube. Cover prototypes are deep-copied so every surface receives independent
`CoverMaterialItem` and `FireBehavior` state; structural `Material` objects are
shared catalogue values.

The global node-ID counter is reset by `create_sample_building()` before the
built-in world is constructed. Callers assembling another world through the
lower-level functions are responsible for resetting it if stable per-world IDs
matter.

### 2.3 Paired directional surfaces

Adjacent cubes do not share one wall or slab object. Each cube owns its side of
the boundary:

```text
Cube A.right_wall.surface_neighbor is Cube B.left_wall
Cube B.left_wall.surface_neighbor  is Cube A.right_wall
```

Vertical pairs use the same rule:

```text
upper_cube.floor.surface_neighbor  is lower_cube.ceiling
lower_cube.ceiling.surface_neighbor is upper_cube.floor
```

`initialize_surface_neighbors()` establishes these links after all surfaces
exist. The practical invariant is:

> For every in-model adjacent cell pair, each facing surface points to the
> opposite surface, and the opposite link points back.

The test suite checks this reciprocity for a representative wall pair. Several
later behaviours assume it without rebuilding adjacency:

- occupant step validation;
- vertical stair checks;
- fire-department suppression reach;
- explicit paired item attachment; and
- some heat and boundary operations.

The two sides deliberately keep independent `structure_material`,
`cover_material`, `degradation`, `hollow` and surface ignition-wrapper state.
Code that changes a physical interface must therefore decide whether the change
is one-sided or must be applied to both surfaces.

### 2.4 Hollow boundaries and rooms

`carve_room_shape()` marks both faces of every internal boundary in a coordinate
set as `hollow=True`. `find_room_objects()` then performs a graph traversal over
hollow walls, floors and ceilings and creates `Room` groupings.

A `Room` stores a set of cube coordinates plus derived component and surface
collections. It does not own temperature, fire energy, fuel or a room-air
balance. Those remain on cells and objects.

The built-in room catalogue adds names such as
`downstairs_storage` and `upstairs_open_area`. Its current implementation maps
those names to numeric room IDs expected from the sample-building carving order.
It is therefore sample-specific; changing the carving order or geometry can
invalidate the ID mapping even when room discovery itself still works.

### 2.5 Objects on paired boundaries

Items can be placed directly in a cube or in a surface's `items` list.
`attach_item_to_surface_pair()` creates one item instance and appends the same
instance to both paired surfaces. This is useful for a door or stair that should
represent one physical accessory from either side, but consumers must deduplicate
by identity if they iterate both cells.

`initialize_items_on_surfaces()` instead deep-copies a prototype onto one named
surface. The sample building uses both patterns depending on whether an object
is one-sided or represents a shared boundary accessory.

## 3. Domain objects and materials

### 3.1 Core relationships

`domain.py` provides the object vocabulary rather than constructing one complete
world:

```text
BuildingComponent
    -> Cube
    -> Wall / FloorSurface / CeilingSurface / CeilingRoof

Item
    -> InventoryItem
    -> CoverMaterialItem
    -> FireSafetyItem -> Sprinkler / SmokeAlarm
    -> BuildingAccessory -> Door / Window / Stairs
    -> AccessCard / AccessPanel

Item -> optional FireBehavior -> Material
```

The object model favours composition for combustion. `Item.fire_behavior` may be
`None`; the item hierarchy alone does not imply that an object burns. Catalogue
entries combine a material and mass into an independent `FireBehavior` where
combustion is required.

### 3.2 Structural material and combustible cover

Each surface stores two different physical concepts:

| Surface state | Role |
| --- | --- |
| `structure_material` | Supplies `burn_resistance` used by degradation |
| `cover_material` | A `CoverMaterialItem` whose `FireBehavior` may ignite and release energy |

Changing a cover through `modify_room_surfaces()` deep-copies the new cover and
resets its combustion state. Changing the structural material assigns the shared
catalogue `Material` value. A surface can therefore have a resistant structure
and a combustible finish without collapsing those behaviours into one property.

### 3.3 FireBehavior

`FireBehavior` owns object-level combustion state:

- continuous time above the material ignition temperature;
- current ignition state and ignition time;
- total and released energy in kJ;
- latest per-update heat output;
- growth exponent, effective peak time, plateau duration and decay constant; and
- the internal timestamps needed to integrate release between calls.

Total energy is calculated from mass and material energy density. The
heat-release curve grows as a power law, may hold at a feasible peak and then
decays exponentially. The curve is precomputed so its peak and duration are
bounded by the available energy. `heat_release()` integrates kW across elapsed
seconds to kJ and clips the increment to remaining energy.

The object clears `is_ignited` when its energy is exhausted or when the
post-peak heat-release-rate tail falls below the implemented threshold. This is
an exploratory rule, not a calibrated combustion law.

### 3.4 State ownership

The model retains several related state flags. Their responsibilities are:

| State | Meaning |
| --- | --- |
| `FireBehavior.is_ignited` | Object or cover is currently combusting |
| `FireBehavior.latest_heat_output` | Energy emitted by that object in its latest update |
| surface `is_ignited` | Compatibility/telemetry mirror of the cover's state |
| `Cube.is_on_fire` | Convenience flag derived from active object and cover behaviour |
| `FireSimulation.fire_status[coord]` | Per-cell `FireState` used by the simulation loop and snapshots |
| `FireState.heat` | Pending per-cell fire-energy buffer, consumed into `Cube.air_temp` on a later update |
| `Cube.air_temp` | Persistent modelled environmental temperature |

`Cube.has_active_fire()` derives activity from cover and item `FireBehavior`.
`Cube.refresh_fire_flag()` synchronizes the cube convenience flag. The
simulation also maintains `FireState.is_on_fire`, so update order matters when
reading these related views.

## 4. Fire simulation

### 4.1 Run initialization

`fire_simulation.run_simulation()` receives an already-built model, run settings
and an agent list. It currently performs the following initialization:

1. create `FireSimulation` and one `FireState` per coordinate;
2. install the goal-oriented movement wrapper;
3. seed Python's random module and create a seeded NumPy generator when a
   `random_seed` is provided;
4. discover exits from surface accessories;
5. construct `FireDepartment` and connect it to the model and agents;
6. enable and redraw probabilistic safety-device parameters when requested;
7. configure snapshot interval and selected fields;
8. force-ignite the requested starting cube;
9. save the initial state at simulation time `0`; and
10. call `tick()` for the requested number of steps.

`start_fire()` force-ignites every cover and direct cube item that has a
`FireBehavior`. It is an explicit scenario intervention, not a thermal ignition
test. The normal propagation path uses each object's continuous exposure logic.

### 4.2 Current tick order

The current `FireSimulation.tick()` order is:

```text
1. save a pre-update snapshot when due
2. update object and cover ignition exposure in every cube
3. activate FireState for newly active cubes
4. for each active FireState:
     a. convert previously buffered fire energy into cell-air temperature
     b. run surface-mounted safety-device callbacks in that cube
     c. calculate new object and cover heat release
     d. update degradation and transfer heat across permitted boundaries
     e. synchronize cover, cube and FireState activity
5. propose and validate occupant movement
6. cool every cube toward ambient
7. collect triggered alarms and advance FireDepartment
8. increment simulation time
```

This sequence has two timing consequences:

- `FireState.heat` generated in step 4c is normally converted into air
  temperature when that cell is processed on the following tick; and
- history records the state at the start of a tick, before that tick's ignition,
  movement, cooling and response updates.

The initial snapshot saved by `run_simulation()` and the snapshot saved at the
start of the first tick use the same key `0`, so the latter overwrites the former
with an equivalent pre-update phase. After `n` fixed ticks, `sim.time == n`, but
with interval one the final in-memory snapshot key is normally `n - 1`.

### 4.3 Ignition and active-fire derivation

For ordinary thermal ignition, `update_items_ignition()` and
`update_surface_ignition()` call `FireBehavior.update_ignition()` with the
current cube air temperature and absolute simulation time. Exposure resets when
temperature falls below the material threshold.

These ignition passes cover direct cube items and each surface's cover. They do
not iterate arbitrary items mounted in `surface.items`, so a combustible door,
window or decoration attached there is not normally thermally ignited by the
current loop even if it has `FireBehavior`.

`_try_ignite_new_cubes()` marks a cell's `FireState` active when a cover or item
has active `FireBehavior`. The function also contains a legacy `300 °C` hot-air
fallback that can temporarily mark a hot cube active even when no object-level
source has been identified. The later active-fire checks clear cells with no
heat and no active burner.

At the end of active-cell processing, the model clears stale surface wrappers
and switches off `FireState.is_on_fire` when no new heat and no active object or
cover remain. `get_burning_cubes()` performs another defensive stale-state
cleanup for runner stop conditions.

### 4.4 Fire energy and air temperature

`heat_increment_formula()` sums energy released during the update from:

- all surface covers;
- direct cube items; and
- items attached to surfaces.

The sum is placed in `FireState.heat`. `update_air_temp_from_fire()` converts the
buffer to a temperature increment using assumed air mass, a temperature-adjusted
specific heat and a decreasing transfer efficiency. The buffer is then reset to
zero. Cell temperature is capped at `1000 °C`.

The default `Cube` does not define the optional `air_mass_kg`, and
`FireSimulation` does not set the optional `CP_AIR_KJ_PER_KGK` attribute used by
the physical seeding branch in `start_fire()`. The current sample therefore uses
the legacy startup fallback that places an ignition-temperature number into the
energy buffer. This unit-mixing shortcut affects only explicit forced ignition,
but it should be removed or parameterized before physical interpretation.

### 4.5 Cooling, degradation and transfer

`apply_cooling()` combines a linear cooling term with a small temperature-scaled
term and moves each cell toward `20 °C` after occupant movement.

Surface degradation is reduced only above the configured `300 °C` threshold and
is scaled by `1 - burn_resistance`. In the main local degradation pass, the
function receives `Cube.air_temp`. The neighbour-transfer pass also invokes it
with the current `FireState.heat` buffer for the two interface surfaces. Those
inputs have different meanings and units; the second call is a current
implementation inconsistency rather than a conceptual requirement.

For two adjacent cells, heat transfer is allowed only when both sides of the
interface satisfy at least one gate:

- the surface is hollow;
- the surface is fully degraded; or
- an attached `BuildingAccessory` allows passage.

When allowed, `transfer_heat_between_cubes()` adds 20% of the positive
temperature difference to the target cell. It does not subtract energy or
temperature from the source. Transfer is therefore directional and
non-conservative.

The target is not directly ignited by this operation. Its own objects and covers
receive the higher local `air_temp` and are evaluated by the ordinary ignition
step.

### 4.6 Current implementation form

Only `FireSimulation.__init__` is defined inside the class body. Most simulation
functions are defined at module scope and assigned to `FireSimulation` near the
end of `fire_simulation.py`. The same pattern appears for several
`FireDepartment` methods in `agents.py`.

This notebook-era method binding is a current maintenance characteristic. It is
not part of the conceptual architecture, and callers should not depend on it as
an extension mechanism.

## 5. Safety systems, occupants and emergency response

### 5.1 Smoke alarms and sprinklers

Safety devices are `FireSafetyItem` instances stored in surface `items` lists.
During active-cell processing, the simulation calls `respond_to_fire()` for
every such item on that cube's surfaces.

`SmokeAlarm`:

- checks a fixed or sampled temperature threshold;
- starts a hold timer after the threshold is crossed;
- applies a fixed or sampled detection lag;
- applies a reliability gate; and
- sets `triggered=True` when detection succeeds.

At the end of the tick, `_collect_triggered_alarm_coords()` scans the building.
Any triggered alarm can start the fire-department incident.

`Sprinkler`:

- checks a fixed or sampled trigger temperature;
- applies a reliability gate on each eligible callback until it triggers;
- computes suppression from `suppression_rate` and cell burn time; and
- subtracts that amount from `FireState.heat`, with a current floor of `20.0`.

The device's `effect_radius` attribute is currently stored but not read by the
simulation. A sprinkler does not search nearby cells and does not directly
change object remaining energy or `released_energy`.

### 5.2 Occupant location and passage

Each `Agent` owns a coordinate `location`, optional `target`, waypoint `path`,
items and behavioural attributes. `Agent.can_pass_between()` is the principal
passage gate.

For adjacent movement it:

1. identifies the source directional surface;
2. follows `surface_neighbor` to the facing surface and target cube;
3. applies target-fire and temperature gates;
4. requires stairs for vertical movement;
5. accepts a hollow horizontal opening; otherwise
6. requires a door that is open or can be unlocked/opened with the agent's
   access card and the door's access panel.

Non-adjacent movement is accepted only through an accessory with a matching
`leads_to` coordinate. The built-in sample primarily uses adjacent paired
surfaces and stair presence.

`GoalOrientedRandomWalk` selects named-room destinations with role weights, then
chooses legal neighbouring steps with a bias toward cooler cells and away from
immediate backtracking. A wrapper installed per simulation asks the movement
strategy for a waypoint when an agent has no usable path. The underlying
simulation mover revalidates the step and throttles movement using `agent.speed`.

The generic `_pathfind()` helper used for quick goal validation is a Manhattan
coordinate path that does not itself inspect walls or doors. Illegal proposed
steps are rejected later, and the current mover drops the rejected waypoint
rather than computing a full topology-aware replacement path.

Agent fields for health, heat exposure, smoke exposure, panic and awareness are
stored and serialized, but the current tick loop does not update a validated
health, smoke or decision model from them.

### 5.3 FireDepartment and FireUnit

Triggered alarms call `FireDepartment.receive_alarm()` once per inactive
incident. The department creates an `Engine 1` unit, assigns an ETA and chooses
the nearest alarm coordinate as its initial target.

After arrival, the current response loop:

- moves the unit along the simple Manhattan path at one cell per second;
- retargets idle arrived units to the nearest cube whose convenience
  `is_on_fire` flag is active;
- suppresses active object and cover `FireBehavior` within a boundary-limited
  breadth-first radius;
- opens nearby unlocked, unblocked doors and windows;
- marks nearby occupants as evacuating and gives pathless occupants a simple
  path to the nearest discovered exit; and
- records per-tick telemetry and demobilizes after a no-fire cooldown.

Suppression reach follows `surface_neighbor` links and accepts hollow or fully
degraded boundaries. Open doors are intentionally not considered by that water
reach function. Available suppression energy is divided across active
combustibles; because `FireBehavior` has no `quench_by_energy()` method, the
current fallback reduces `latest_heat_output` and clears ignition below a
threshold. It does not restore or remove `released_energy`.

Fire-unit movement does not call `Agent.can_pass_between()` and therefore does
not enforce doors, stairs, locks or hazards. `force_entry()` exists as a callable
method and telemetry has a forced-entry counter, but `step()` does not invoke it
automatically. Search-and-rescue is limited to nearby-agent flags and route
assignment; there is no carrying, health or tenability model.

### 5.4 Module boundaries

| Module | Safety/agent responsibility |
| --- | --- |
| `domain.py` | Defines devices, accessories, cards, panels and their local callbacks/state |
| `agents.py` | Defines occupant passage/movement and fire-department response behaviour |
| `fire_simulation.py` | Calls devices and agents in tick order and connects alarms/response to shared fire state |

## 6. Deterministic and stochastic configuration

### 6.1 Distribution primitives

`probability_distributions.py` provides sampler factories for lognormal, normal,
exponential, gamma, Weibull, uniform, beta and Bernoulli distributions. Each
factory returns a callable backed by a supplied or newly created NumPy
`Generator`. Diagnostic plotting helpers are colocated with the samplers.

### 6.2 Current consumers

| Consumer | Sampled values | Realization |
| --- | --- | --- |
| `Sprinkler` | trigger temperature, maximum burn-time scale | drawn once when probabilistic parameters are reset |
| `SmokeAlarm` | trigger temperature, detection lag | drawn once when probabilistic parameters are reset |
| `FireDepartment` | response ETA | drawn when an incident is dispatched |

`ProbabilisticDeviceMixin` owns the safety-device opt-in, sampler construction
and cached per-incident draws. `enable_probabilistic_devices()` scans
surface-mounted items for that protocol. `reset_probabilistic_params()` redraws
enabled device values.

The deterministic fire and thermal functions do not branch to an alternative
probabilistic spread model. Sampled values enter through configured device and
response parameters.

### 6.3 Reproducibility boundary

When supplied, `run_simulation(random_seed=...)` seeds:

- Python's module-level `random` generator, used by occupant choices and device
  reliability gates; and
- one NumPy `Generator` passed to probabilistic safety devices.

The probabilistic `FireDepartment` constructs its lognormal ETA sampler without
receiving that generator, so it creates an independent NumPy generator. A seed
therefore does not currently guarantee full probabilistic-run reproducibility
once an alarm dispatch samples its ETA.

With `probabilistic=False`, safety-device thresholds/delays and response time are
fixed, but smoke-alarm and sprinkler reliability checks still call Python
`random.random()`. Fixed-parameter mode becomes fully repeatable when Python
random is seeded; it is strictly deterministic only if those reliability gates
are also configured to certainty.

No repository evidence establishes the sampler parameters as fitted empirical
uncertainty distributions.

## 7. Scenario construction and execution

### 7.1 Scenario boundary

`scenarios.py` removes notebook execution order by explicitly composing the
built-in world:

```text
create_sample_building()
    -> build_room_catalog_from_model()
    -> create_default_agents()
    -> run_simulation(...)
```

`build_sample_world()` returns `(global_model, room_catalogue, agents)`.
`run_sample_simulation()` constructs those dependencies, adds run settings and
returns the advanced `FireSimulation` object.

`run_custom_simulation()` currently customizes run arguments but still calls
`build_sample_world()`. Its name should not be interpreted as support for
arbitrary geometry. The actual lower-level custom-world interface is
`fire_simulation.run_simulation(global_model=..., agents=..., ...)`.

The scenario layer currently places geometry, materials, contents, devices and
accessories in `create_sample_building()`, occupants in `create_default_agents()`,
and ignition/response/run settings in the scenario launcher. There is no single
serializable `Scenario` object.

### 7.2 Settings

`simulation_settings.py` contains visible constants for:

- default tick counts and until-extinguished caps;
- ignition and response coordinates;
- response time;
- snapshot interval and fields;
- chunk size;
- probabilistic/history flags; and
- the names of five supported public run modes.

The settings module is a preset catalogue, not a configuration parser. Scenario
functions use many of its constants as default arguments.

### 7.3 Runner modes

`simulation_runners.py` mutates an existing `FireSimulation` by calling
`sim.tick()`:

| Mode | Functionality |
| --- | --- |
| Fixed ticks | `run_for_n_ticks()` advances exactly `n` steps |
| Until extinguished | `run_fire_until_extinguished()` stops on no burning cubes or a cap |
| Fixed chunked | `run_sim_in_chunks()` divides a fixed run into progress-sized chunks |
| Until extinguished, chunked | `run_sim_in_chunks_until_extinguished()` repeats bounded chunks |
| Until extinguished, chunked to disk | `run_and_save_sim_in_chunks_until_extinguished()` writes and clears each history batch |

The corresponding convenience launchers in `scenarios.py` initialize the sample
world with zero ticks and then delegate to these runners. Chunking by itself does
not reduce the final in-memory history: only the disk-backed runner saves and
clears each batch.

`is_fire_extinguished()` prefers `sim.get_burning_cubes()`, which derives active
combustion and clears stale flags, rather than relying only on historical cell
flags.

## 8. State history and persistence

### 8.1 Snapshot configuration

`FireSimulation.snapshot_parameters` stores:

- `snapshot_interval`; and
- `fields_to_save`.

Snapshots are recorded only when `save_full_history` is true and
`sim.time % snapshot_interval == 0`. Unknown field names are silently skipped.

The supported fields are:

| Field | Current representation |
| --- | --- |
| `fire_status` | Deep copy of the coordinate-to-`FireState` dictionary |
| `air_temp` | Coordinate-to-number mapping |
| `components` | Selected combustion fields for direct cube items, surfaces and surface covers |
| `agents` | JSON-friendly agent attributes, coordinates, paths and owned-item summaries |
| `fire_department` | Latest response telemetry and unit states |

The `components` serializer is selective. For each surface it stores class,
label and aggregated cover combustion values. It does **not** currently preserve
the structural material, `hollow`, degradation, attached surface accessories or
all arbitrary object attributes. It is therefore an analysis schema, not a full
world checkpoint.

`fire_status` remains a deep copy of Python objects, while the other major
fields are dictionaries/lists of selected values. The mixed representation is
convenient for current analysis but is not a stable cross-version interchange
format.

### 8.2 Snapshot phase

Snapshots occur at the start of `tick()`. A record with key `t` therefore
describes the state immediately before the update that advances time from `t`
to `t + 1`.

This phase must be considered when aligning fire-department telemetry, movement
and heat output. Telemetry stored in a snapshot is the latest available
department record, generally produced at the end of the preceding tick.

### 8.3 Memory and disk persistence

Ordinary runs keep snapshots in `sim.history`. Detailed `components` snapshots
scale with cells, surfaces and combustible objects and can become large.

The disk-backed chunk runner pickles the entire current history dictionary to
`snapshot_data_<chunk>.pkl`, then clears it in place. This bounds history retained
in the simulation object, but pickle files remain Python-specific, unsafe to
load from untrusted sources and potentially large.

`io_utils.py` exposes generic `save_pickle()` and `load_pickle()` helpers.
`config.py` resolves `data/` and `outputs/` by finding the repository's
`pyproject.toml`. A wheel installation used from a checkout falls back to the
current working directory; `BUILDING_FIRE_SIMULATION_ROOT` provides an explicit
override for other optional persistence workflows. There is no versioned
snapshot manifest or event-log format. Local pickles created with the package's
former import namespace are not a supported public interchange format after
the rename.

## 9. Analysis boundary

`fire_analysis.py` is downstream of state updates. Its functions read live
objects or `sim.history`; they do not participate in `FireSimulation.tick()`.

Current consumers include:

- active-heat summaries and ignition/extinguish change logs;
- occupant routes as pandas data frames;
- fire-department telemetry as a tidy data frame;
- cell-air-temperature plots;
- per-object remaining-energy and heat-output plots;
- room/building and fire visualizations; and
- a live inventory-loss helper.

Each analysis depends on specific snapshot fields. For example, burning-change,
remaining-energy and per-object heat-output functions require `components`,
while route analysis requires `agents`. The basic sample history does not
contain `components`; callers must request `ALL_HISTORY_PARAMETERS` or an
appropriate custom field tuple.

`calculate_inventory_loss()` is different from the history-based functions. It
iterates direct cube items in the current live model and sums the values of
flammable items whose `FireBehavior` is currently active. It omits surface items
and burned-out historical items, so it should not be interpreted as total
incident loss.

Visualization and regression outputs explain one configured run. They do not
validate the thermal, behavioural or response model.

## 10. Module map

| Module | Public architectural role | Important current boundary |
| --- | --- | --- |
| `domain.py` | Defines materials, items, components, rooms, devices and accessories | Large in-code catalogues; several state mirrors |
| `building_factory.py` | Builds coordinates, surfaces, rooms and the sample world | Named-room catalogue is tied to sample room IDs |
| `fire_simulation.py` | Owns `FireState`, tick orchestration and snapshots | Most methods are bound after class definition |
| `agents.py` | Implements passage, movement and response | Occupants and fire units use different routing gates |
| `probability_distributions.py` | Creates reusable distribution samplers | Parameters are modelling inputs, not fitted datasets |
| `scenarios.py` | Composes and launches the built-in sample world | `run_custom_simulation()` changes settings, not geometry |
| `simulation_settings.py` | Names defaults and supported run modes | Constants only; no schema or parser |
| `simulation_runners.py` | Advances an existing simulation | Only disk-backed chunking clears history |
| `fire_analysis.py` | Reads history/live state for tables and plots | Field-dependent; loss helper is not historical total loss |
| `io_utils.py`, `config.py` | Support persistence and repository paths | Pickle only; no versioned persistence contract |

The public documentation roles are separate:

- [`../README.md`](../README.md) is the accessible model overview;
- [`modelling_approach.md`](modelling_approach.md) explains the modelling
  rationale;
- this document describes the current technical implementation; and
- [`../MODEL_DEVELOPMENT_HISTORY.md`](../MODEL_DEVELOPMENT_HISTORY.md) is the
  evidence-labelled chronological reconstruction.

The demonstration is likewise downstream of the model: `demo/run_demo.py`
constructs and advances a scenario through the public package, then calls
`fire_analysis.py` and writes only compact figures, CSV files and summaries.
The optional scripts remain separate consumers rather than numbered stages in
the model pipeline.

## 11. Current implementation boundaries

### 11.1 Physical model

- Cells use lumped air temperature rather than fluid fields.
- Inter-cell heat transfer adds temperature to the target without removing it
  from the source.
- Forced-ignition startup currently uses a legacy mixed-unit energy seed.
- Surface degradation receives inconsistent inputs in its local and neighbour
  passes.
- There is no smoke, oxygen, ventilation-flow, flame geometry, structural
  mechanics or collapse model.
- A room is not a thermodynamic control volume.
- Material and device values require provenance, unit review, calibration and
  sensitivity analysis.

### 11.2 Safety, people and response

- Device `effect_radius` is not used by the current safety-device callback
  loop.
- Sprinklers change the cell energy buffer rather than object fuel state.
- Occupant cognition, exposure and health fields are largely passive state.
- Occupant goal validation begins with a topology-blind Manhattan helper and
  rejects illegal steps later.
- Fire-unit routing bypasses occupant passage, access and hazard checks.
- Forced entry is callable but not automatically integrated.
- Search, rescue, suppression and demobilization are functional abstractions,
  not validated tactical models.

### 11.3 Probability and reproducibility

- Reliability gates remain random when sampled parameter hooks are disabled.
- The fire-department ETA generator is not connected to the scenario NumPy
  generator.
- Distribution parameters are not calibrated uncertainty models.

### 11.4 State, history and scale

- Cell fire activity exists in both `FireState` and cube convenience flags and
  is synchronized during the tick rather than represented once.
- Snapshot fields are selected analysis records, not restartable full-world
  checkpoints.
- Snapshot phase is pre-update and the final simulation time normally has no
  same-key snapshot in a fixed run.
- Pickled history is Python-specific and detailed histories remain expensive.
- Notebook-era post-class method binding increases maintenance and inspection
  cost.

### 11.5 Validation boundary

The tests exercise selected software invariants and integration paths:

- sample-world size and coordinates;
- reciprocal surface pairing;
- room-catalogue coordinates;
- explicit ignition and absence of cool spontaneous ignition;
- history key progression;
- repeatability of the short seeded sample path;
- in-bounds occupant movement; and
- configured deterministic fire-department response timing.

They do not establish physical, behavioural, probabilistic or tactical validity.
