# Model assumptions and parameter provenance

This project is an exploratory computational model, not a validated fire-engineering
package. Its outputs are synthetic and should not be used for design, compliance, or
life-safety decisions.

## Spatial and temporal representation

- The building is a discrete three-dimensional grid of cubic cells.
- Each simulation tick advances the current update loop by one nominal second.
- Walls, floors, ceilings, doors, windows, and stairs determine adjacency and passage.
- The model does not solve continuous fluid dynamics, smoke transport, or detailed
  ventilation.

## Fire and heat

- Combustible objects use a growth/plateau/exponential-decay heat-release curve bounded
  by their available energy.
- Ignition is based on continuous exposure above a material-specific temperature.
- Cell air temperature, cooling, inter-cell heat transfer, and surface degradation use
  simplified lumped relationships.
- Fire spread is enabled by open/hollow passages or sufficiently degraded boundaries;
  it is not a flame-front or CFD calculation.

## Occupants, safety systems, and response

- Occupants follow discrete paths and probabilistic, rule-based movement strategies.
- Smoke alarms and sprinklers use simplified thresholds, reliability, and response
  behavior.
- Fire-department dispatch, travel, suppression, entry, and search are abstracted to
  grid movement and configured timing.

## Parameters and provenance

Material and behavioral values in `fire_building_sim/domain.py` are modelling inputs
used for this project. They have not been calibrated as a validated material database.
Some heat-release modelling concepts were informed by the fire-safety literature,
including:

> B. Karlsson, "A mathematical model for calculating heat release rate in the room
> corner test," *Fire Safety Journal*, 20(2), 93-113, 1993.
> https://doi.org/10.1016/0379-7112(93)90032-L

Before scientific reuse, each numerical parameter needs a traceable source, unit check,
sensitivity analysis, and validation against appropriate experimental data.
