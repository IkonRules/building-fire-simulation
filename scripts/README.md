# Optional workflows

These scripts are specialist consumers of the installed package. They are not a
numbered pipeline, no script depends on another having run first, and none is the
public demonstration.

| Script | Purpose |
| --- | --- |
| `save_sample_world.py` | Serialize a newly constructed sample building and room catalogue into `data/` for local Python workflows. |
| `run_history_workflow.py` | Configure fixed, until-extinguished, chunked, or disk-backed full-history runs. |
| `analyze_sample_simulation.py` | Open interactive plots and print analysis tables for a longer recorded run. |

For the compact reproducible showcase and committed results, use
`python demo/run_demo.py` instead. The package must first be installed as described
in the root README.
