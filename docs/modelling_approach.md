# Modelling Approach

Building Fire Simulation is an exploratory computational model of how spatial
structure, physical objects, fire dynamics, occupants and emergency response can
interact inside the same three-dimensional environment.

The project did not begin as a fire model. Its starting point was a more general
question: **how can a building be represented in enough detail that events can
propagate through it in a structured and interpretable way?**

An early version of this idea was explored in spreadsheet form. Moving to Python
made it possible to represent the building as a three-dimensional system of
interacting objects rather than as a fixed table of relationships.

The central modelling question gradually became:

> **How can building-wide behaviour emerge from local interactions between
> spatial cells, physical objects and agents without hard-coding the resulting
> event?**

The present model can be understood through the following conceptual layers:

```text
building representation
    -> physical objects and materials
    -> fire dynamics
    -> safety systems, occupants and emergency response
    -> scenario execution and history
    -> analysis
```

Selected parameters can additionally be replaced by probability distributions,
allowing the deterministic model to remain the baseline for stochastic
experiments.

This document follows that modelling structure rather than the chronology of
every implementation change. The project developed iteratively: changes in the
fire model repeatedly created new requirements for the building representation,
while new building features enabled more detailed fire, movement and response
behaviour. The present architecture is therefore the result of the layers
evolving together rather than one completed model being placed on top of
another.

---

## 1. Building representation

The spatial model was the starting point of the project.

The basic idea was to divide a building into discrete three-dimensional cells.
Each cell is represented by a cube with a unique coordinate. Collections of
cubes can form rooms, floors and multi-storey buildings.

This representation offered an important advantage: complex geometry could be
constructed from one simple spatial unit. The difficult part was not creating
the cubes themselves, but defining the relationships between them.

If two cubes are adjacent, the model must know:

- which surfaces face one another;
- whether the boundary is open or closed;
- what materials exist on either side;
- whether heat can pass through it;
- whether people can cross it;
- whether a door, stair or other feature connects the cells; and
- how a change on one side should affect the other.

The earliest implementations treated walls and slabs as shared graph
components. This created increasingly difficult questions of ownership and
direction. A wall between two cells, for example, could be the right wall of one
cube and the left wall of another. Vertical relationships created the same
problem for floors and ceilings.

The eventual solution was to give every cube six directional surfaces of its
own and explicitly pair each surface with the corresponding surface of the
adjacent cube:

```text
[Cube A surface] <-> [Cube B surface]
```

The `surface_neighbor` relationship became the common interface between
neighbouring cells. This increased the number of model objects but simplified
the behaviour built on top of them. Each side of a boundary could now have its
own material, cover and degradation state while the relationship between the
cells remained explicit. Doors and stairs could use the same paired-boundary
structure for passage, and heat-transfer logic no longer had to reconstruct
adjacency from direction labels during every update.

The construction process also became coordinate-first. Spatial constellations
are defined and positioned before model objects are created. Their coordinates
are combined, cubes are instantiated once, and the complete graph is built once.
This avoids duplicate or stale surface objects and gives the whole building one
consistent spatial identity. The current `building_factory.py` retains this
construction philosophy.

### 1.1 Rooms

Rooms are built on top of the cell representation rather than replacing it.

A room is a collection of cubes connected through boundaries that have been
opened or marked as hollow. Room templates can therefore be carved into an
existing cube structure without introducing a second spatial system. Named
rooms and room categories later provide higher-level destinations and search
areas for devices, occupants and emergency responders.

This distinction remains important. A room is not modelled as one perfectly
mixed thermodynamic volume. Fire, temperature, contents and boundaries still
belong to individual cells. A room is a higher-level grouping over those cells.

The resulting spatial hierarchy is approximately:

```text
building
    -> rooms
        -> cubes
            -> directional surfaces
                -> paired neighbouring surfaces
```

This spatial layer became the foundation on which every later part of the model
depended.

---

## 2. Physical objects and materials

As the building became more detailed, geometry alone was no longer sufficient.

The simulation needed a vocabulary for describing **what exists inside the
building** independently of the functions used to construct a particular
building. This responsibility eventually became concentrated in `domain.py`,
which contains materials, fire behaviour, contents, safety devices, building
components and accessories.

This separation allows the cube graph to act as a spatial framework that can be
configured with different physical properties.

A boundary is not important merely because it separates two cells. Its
structural material can affect how it responds to sustained heat. A combustible
cover attached to it can ignite and release energy. A cell can contain furniture
or equipment whose quantity and composition change the potential fire.

The object model gradually moved from dictionaries and a dedicated `FireLoad`
subclass toward composition:

```text
Item
    -> optional FireBehavior
    -> optional monetary value
    -> subtype-specific properties
```

`FireBehavior` contains the state and parameters required for combustion,
including material, combustible mass, ignition exposure, heat-release behaviour,
remaining energy and burnout. Objects that do not burn can still participate in
the simulation without pretending to have combustion behaviour.

The distinction between **structural material** and **combustible cover** became
especially important. A structural surface may resist degradation while a cover
on that surface can ignite and contribute heat. Treating them as separate
objects allows the outcome to result from their interaction rather than from one
generic wall-flammability value.

The same attachable-object infrastructure is used for several different roles:

- furniture, equipment and other inventory;
- combustible wall and ceiling covers;
- smoke alarms and sprinklers;
- doors, windows and stairs; and
- access cards and access panels.

These objects do not all behave alike. What they share is a place in the same
building model and a clear relationship to a cell, surface, agent or boundary.
Different arrangements of materials and contents can therefore create different
fire behaviour even when the building geometry is unchanged.

---

## 3. Fire dynamics

The fire model changed more fundamentally than any other part of the project.

### 3.1 From direct spread probability to a causal model

The first implementation treated fire spread mainly as a stochastic event. At
each timestep, a burning cell had a probability of igniting a neighbouring cell,
with different values for different boundary types.

This was suitable for the first version of the simulation, but it became harder
to justify as materials and contents were added. If a room contained more
combustible material, simply increasing a spread probability would not explain
how that material changed the fire. Material modifiers, fire-load modifiers and
temperature could easily become overlapping explanations for the same event.

The model therefore moved toward a causal local chain:

```text
combustible object or cover ignites
    -> it releases a finite amount of heat energy
    -> cell air temperature rises
    -> heat affects surfaces and neighbouring cells
    -> another object or cover receives sufficient thermal exposure
    -> that object ignites
    -> the new cell becomes an active fire
```

The important change is that a boundary no longer directly ignites a neighbour.
An open, hollow or sufficiently degraded boundary permits heat transfer. The
contents and covers in the receiving cell must then satisfy their own ignition
conditions before that cell becomes an active fire.

This also prevents an open room from becoming fully ignited in one recursive
update. Heat can move through the room, but combustion still develops from local
conditions.

### 3.2 Fire energy, air temperature and ignition

Early versions used one `heat` value for several different concepts: fire
intensity, accumulated energy and environmental temperature. These concepts were
later separated.

- `FireState.heat` represents energy contributed by actively burning contents
  and covers during an update;
- `Cube.air_temp` represents the persistent modelled temperature of the cell;
- each combustible object's `FireBehavior` tracks its own ignition exposure,
  energy release and burnout; and
- surface degradation responds to cell temperature rather than directly to a
  generic fire-spread value.

This separation makes a non-burning cell capable of heating up before ignition
and allows cooling to continue after active combustion has stopped.

Ignition is based on continuous exposure above a threshold rather than a single
instantaneous comparison. The heat-release model likewise developed from an
immediate peak followed by exponential decay into a piecewise growth, optional
plateau and decay process constrained by finite combustible energy.

Conceptually:

```text
temperature exposure
    -> ignition
    -> growth
    -> optional plateau
    -> decay
    -> burnout
```

The current implementation integrates heat-release rate over each timestep,
limits released energy by what remains in the object and derives whether a cube
is actively burning from the fire behaviour of its contents and covers.

### 3.3 Boundaries, degradation and transfer

Structural materials influence boundary degradation under sustained high
temperature. Paired surfaces retain separate degradation state, so the two
sides of a wall can respond independently while remaining explicitly connected.

Whether heat or an agent can cross a boundary depends on its current state and
its accessories. A hollow boundary, an open door, a stair connection or a
sufficiently degraded separation can permit interaction, while a closed or
intact boundary can restrict it.

Heat transfer, combustion and passage are related but not identical concepts.
Keeping them separate allows the same spatial connection to support fire,
movement and response logic without requiring those processes to use one
undifferentiated rule.

The resulting thermal model includes finite fuel energy, cell-air heating,
temperature-dependent transfer, surface degradation, cooling and a maximum
modelled cell temperature. These are simplified modelling rules. They are not a
validated heat-balance solver, CFD model or substitute for fire-engineering
analysis.

---

## 4. Safety systems, occupants and emergency response

Once the building and fire layers could interact, the model expanded from a
fire-propagation experiment into a shared environment containing systems and
agents that could observe and change the event.

### 4.1 Detection and suppression

Smoke alarms and sprinklers are represented as specialized safety items. Their
properties include activation conditions, reliability, state and response
behaviour. A range value is also stored, although the current safety-device
callback does not yet use it.

The model distinguishes detection from suppression. In the current update loop,
surface-mounted alarms and sprinklers respond within the active burning cube
that contains them. Alarms use temperature, delay and reliability before
notifying the emergency-response layer. Sprinklers reduce the cube's current
fire-energy buffer; they do not currently change object fuel or remaining
energy. Fire-department suppression is a separate, boundary-limited operation
that reduces the latest heat output of reachable burning objects and covers.

These actions still feed into the shared causal chain by changing the fire state
that subsequent temperature, ignition and response updates read.

### 4.2 Occupants, access and movement

Occupants are represented as agents located in the same cells as the fire and
physical objects. Their movement uses the paired-boundary model and can take
doors, locks, access cards, access panels, stairs, fire and high-temperature
hazards into account.

The first movement logic used fixed paths. It later developed into
role-weighted, goal-oriented movement in which agents select destinations from
named room categories, follow a path and choose another goal when required.
Different roles can therefore use the same movement mechanism while assigning
different importance to possible destinations.

The implementation captures spatial movement and access constraints, but it
does not provide a validated model of perception, panic, health effects,
evacuation decisions or crowd behaviour.

### 4.3 Fire department

`FireDepartment` and `FireUnit` add an organizational response layer. The model
can represent alarm reception, response delay, simple grid movement,
boundary-limited suppression, opening useful egress and basic search-and-rescue
state changes.

Emergency response reads the same cells and burning objects as the fire
simulation, and suppression does not simply delete a cell fire state. Its
consequences flow through the shared object state. The current unit travel path,
however, is a simple Manhattan route and does not use the occupant passage and
access checks. Callable forced-entry support exists but is not invoked
automatically by the response loop.

The response model remains deliberately limited. Dispatch, routing, tactics,
water reach, forced entry and search are abstractions. Ventilation was removed
from the implementation because the model did not represent the oxygen and
airflow effects required to support it.

---

## 5. Deterministic baseline and optional probability

The earliest fire-spread model was stochastic, but the later material and
thermal layers gave the central simulation a largely deterministic structure.
Given the same configured world, parameters and event sequence, the same local
thermal rules produce the same result. Device reliability gates still use a
random draw even when sampled-parameter hooks are disabled.

Probability was later reintroduced around selected inputs without replacing
that baseline. The `probability_distributions.py` module provides reusable
samplers for common distributions, while model components can opt into sampled
parameters such as response times or safety-device behaviour.

This creates a useful separation:

```text
deterministic model rules
    + fixed parameter values
    -> baseline run

deterministic model rules
    + sampled parameter values
    -> stochastic experiment
```

Some traits can be drawn once for a device and retained, while incident-level
values can be redrawn before a new run. The scenario seed controls Python random
and the NumPy generator supplied to safety devices. The current probabilistic
fire-department ETA sampler creates its own generator, so full-run seed control
is not yet complete.

Probability is therefore a cross-cutting configuration layer rather than the
next sequential stage of the modelling pipeline. This makes it possible to
compare a fixed reference case with variations around the same underlying
model.

The repository provides the sampling primitives and probabilistic-device hooks.
It does not yet contain a complete calibrated Monte Carlo study, and the
distribution parameters should not be interpreted as empirically validated
without further provenance and fitting.

---

## 6. Scenario execution and history

The model originally grew in notebooks. That made experimentation fast, but it
also allowed hidden global state, execution order and import-time side effects to
become part of how a simulation was assembled.

The later package migration made those dependencies explicit. The current
execution structure separates:

- `domain.py`, which defines what can exist;
- `building_factory.py`, which constructs and configures spatial worlds;
- `agents.py` and `fire_simulation.py`, which define behaviour;
- `scenarios.py`, which composes a complete starting state;
- `simulation_settings.py`, which names execution and snapshot choices;
- `simulation_runners.py`, which advances the model; and
- `io_utils.py` and `config.py`, which support persistence and paths.

A scenario is therefore not the model itself. It is one explicit configuration
of the reusable model layers: a building, its materials and contents, occupants,
safety systems, emergency response, ignition point, settings and random seed.
Demos and examples remain useful as reproducible configurations, but they are
complements to the underlying model rather than its organizing principle.

The timestep engine follows the same separation of concerns. The original large
update function was divided into stages for preparation, ignition, combustion,
suppression, temperature and degradation, neighbour transfer, movement, cooling
and emergency response. `tick` now acts primarily as an orchestrator over those
stages.

### 6.1 Simulation history

History began as a way to redraw earlier fire states. As the model expanded, it
also had to support later inspection of temperature, selected surface-cover and
content combustion fields, agents and emergency-response actions.

Saving unrestricted deep copies of the complete object model proved too
expensive for long runs. History therefore evolved toward configurable snapshot
intervals, selected-field serialization and chunked execution that can write
bounded groups of snapshots to disk.

The available runners reflect different uses of the model:

- a fixed number of timesteps;
- execution until no active fires remain;
- full in-memory history;
- chunked in-memory history; and
- chunked, disk-backed execution.

This execution layer makes simulations reproducible and inspectable without
requiring all analyses to be embedded in the core update loop. Full component
histories remain inherently expensive, however, and large stochastic studies
will require compact event logs or analysis-specific storage formats.

---

## 7. Analysis

The analysis layer consumes live or serialized simulation state without
changing the underlying fire process.

It began with a narrow question: which inventory items had ignited, and what was
their monetary value? From there it expanded to include:

- changes in active fire state over time;
- modelled cell-air temperatures;
- remaining combustible energy and per-item heat output;
- three-dimensional views of the building and fire;
- occupant routes;
- fire-department actions; and
- a limited live inventory-loss estimate based on currently active direct cube
  items.

Separating analysis from execution is important because the same run can be
examined from several perspectives without adding plotting, tabulation or loss
logic to the simulation engine.

It also defines an interface requirement for history: state only needs to be
stored at the detail required by the intended analysis. A lightweight
temperature study, for example, should not require complete copies of every
object at every timestep.

The analysis functions explain model behaviour and support regression testing.
They do not establish empirical validation. A recorded example output is a
demonstration of a configured scenario, not evidence that the simulated fire or
response matches a real incident.

---

## 8. What the modelling process taught us

Although the repository is now organized as a layered pipeline, the project did
not develop as a clean top-down implementation.

Each new behaviour exposed assumptions in the layer below it:

- rooms revealed that shared surfaces made direction and ownership ambiguous;
- paired directional surfaces made per-side materials, doors, stairs and
  degradation manageable;
- combustible contents showed that fire load should affect energy and duration,
  not merely multiply a spread probability;
- thermal transfer required fire energy to be separated from air temperature;
- local ignition allowed heat transport to be separated from the event of a new
  fire starting;
- safety systems and occupants required rooms and boundaries to support range,
  passage, access and destinations;
- object-level combustion required history to preserve selected internal state;
- long histories required execution, persistence and analysis to become
  separate concerns;
- probabilistic experiments required fixed model rules to be separated from
  per-run parameter realization; and
- leaving notebooks required scenario dependencies to become explicit.

Several early failures were therefore not isolated implementation bugs. They
revealed that one object or variable had been given more than one responsibility:
a wall belonged to two perspectives, `heat` represented both energy and
temperature, a notebook module contained both definitions and an already-built
world, or a history object attempted to preserve everything for every possible
analysis.

The general principle that emerged is:

> **Keep state ownership and causal transitions explicit, so that each new
> behaviour can act on the shared model without redefining what the model
> objects mean.**

This principle explains the coordinate-first building process, paired surfaces,
composition-based fire behaviour, local ignition, explicit scenario assembly
and selected-field history.

The project is consequently best understood not as a collection of demos, but
as an evolving attempt to build one coherent environment in which spatial,
physical and agent-based processes can interact.

---

## 9. Current state and limitations

The current package brings the principal modelling layers into one explicit
structure. Its strongest implemented components are:

- coordinate-first construction of multi-cell, multi-storey buildings;
- reciprocal directional surfaces and room carving;
- configurable materials, covers, contents and building accessories;
- object-level ignition, finite-energy heat release and burnout;
- cell-air temperature, cooling, boundary degradation and inter-cell transfer;
- alarms, sprinklers, occupants, access-aware movement and emergency response;
- largely deterministic thermal rules and partially seeded probabilistic
  configuration;
- explicit scenario and runner interfaces;
- configurable and chunked state history; and
- analysis of fire, temperature, objects, agents, actions and loss.

The package also retains some historical implementation traits. In particular,
parts of `fire_simulation.py` still define functions at module scope and bind
them to `FireSimulation` afterwards. This works, but makes the class harder to
inspect and maintain than a conventional class definition.

More importantly, the scope of the model must remain clear.

### 9.1 Physical validity

The thermal layer uses lumped approximations. It does not solve fluid flow,
smoke transport, oxygen availability, ventilation, structural mechanics or CFD.
Many material and object parameters are modelling inputs whose units,
provenance, sensitivity and experimental validity still need systematic review.

### 9.2 Probability

The probability infrastructure is reusable and partly seedable, but the current
fire-department ETA sampler is not connected to the scenario NumPy generator.
Its parameters are not presented as distributions fitted to observed
populations or incident data. Stochastic runs therefore explore configured
uncertainty rather than establish calibrated real-world risk.

### 9.3 Occupants and response

Movement, access, dispatch, suppression and search are functional abstractions.
The model does not yet provide validated panic, perception, health, crowd or
fire-service tactical behaviour.

### 9.4 State and scale

Rooms remain graph groupings of cells rather than mixed thermodynamic zones.
Detailed history is costly, and large ensembles will need more compact storage
and analysis interfaces.

These limitations do not make the project directionless. They define what the
current implementation can support: reproducible experiments with a coherent,
inspectable interaction model. They also define what would be required before
any result could be interpreted as fire-engineering, evacuation or emergency
response evidence.

Building Fire Simulation is therefore not a validated fire predictor surrounded
by demonstrations. It is a layered exploratory model whose central contribution
is the connection between a configurable three-dimensional building, local
physical processes and agents acting in the same evolving state.

The question that continues to organize the project is the one that motivated
it from the beginning:

> **What representation is detailed enough for meaningful interactions to
> emerge locally, while remaining simple enough to construct, run and
> understand?**
