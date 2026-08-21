# Demonstration

`run_demo.py` is the repository's single public, reproducible showcase. It builds
the sample world from source, runs a fixed-parameter scenario with seed `2026`,
records all supported history fields, and applies the package's own analysis
helpers.

From an installed development checkout, run:

```bash
python demo/run_demo.py
```

The `outputs/` directory contains the intentionally committed compact result set:
four figures, a Markdown and JSON summary, occupant movement data, and
fire-department activity. Running the demonstration replaces those files.

All values are synthetic exploratory model outputs. They are not validated
fire-engineering, evacuation, or emergency-response predictions.
