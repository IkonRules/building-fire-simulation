# Local data and generated histories

The simulation builds its example scenario directly from Python source; no binary
data file is required for a clean run.

This directory is ignored except for this note because local development previously
produced very large pickle histories (`snapshot_data*.pkl`) and serialized sample
worlds. Those files are generated artifacts, are Python-version-sensitive, and should
not be downloaded from an untrusted source. Pickles created before the public package
rename may also contain the former module path and are not compatible public inputs;
the demonstration always constructs a fresh world from source.

An external paper was also stored locally as `heat_model.pdf`. It is not redistributed
with the public repository because its copyright remains with the author/publisher.
Relevant background citation:

> B. Karlsson, "A mathematical model for calculating heat release rate in the room
> corner test," *Fire Safety Journal*, 20(2), 93-113, 1993.
> https://doi.org/10.1016/0379-7112(93)90032-L

The old `full_lambda_decay_registers.txt` file was a notebook-export duplicate of
constants now defined in `src/building_fire_simulation/domain.py`; it is not a runtime
input.
