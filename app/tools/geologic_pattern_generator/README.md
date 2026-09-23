# Geologic Pattern Generator

Evidence-gated local generator for canonical synthetic 2D geological bodies.
It separates universal process rules from replaceable regional profiles and
does not write DWG directly. AutoCAD consumes the validated canonical outputs.

## Run

Double-click `run_example.cmd`, or run:

```powershell
python cli.py --config example_config.json --terrain terrain.csv --output output_folder
```

Terrain CSV requires `distance_m` and `elevation_m`. Output consists of:

- `canonical_model.json`
- `canonical_boundaries.csv`
- `validation_report.json`

Every unit requires a `processId`, bounded parameters, evidence tags and source
IDs. Cross-cutting intrusions, folds and faults are rejected by this stack
engine because they require a dedicated event/topology model.
