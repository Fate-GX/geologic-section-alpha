# User guide

[English README](../README.en.md) | [日本語](USER_GUIDE.md)

The GUI and existing example-image annotations are currently Japanese. The translations below identify the controls; they do not imply an English GUI is available.

## Requirements and setup

Use Windows, Python 3.11+ with Tkinter and the `pyw` launcher, and AutoCAD 2027. Make sure AutoCAD works under your normal interactive Windows account. The default installation path `C:/Program Files/Autodesk/AutoCAD 2027` is assumed. Administrator execution is normally unnecessary.

Extract the complete folder and double-click `Geologic_Section.vbs`. The **セットアップ (Setup)** button creates a dedicated `.venv/` and installs dependencies there, rather than installing into your existing Python environment. Initial installation and live data retrieval require internet access.

## Select a route and generate

1. Click **地図で始点A・終点Bを指定 (Select start A and end B on the map)** and choose two land points.
2. Check the distance (10–500 m) and azimuth. A is the left end of the drawing; B is the right end.
3. Expand detailed settings only if necessary. A seed selects a synthetic realization, not the true underground structure.
4. Check the output directory and click **検証してネイティブDWGを生成 (Validate and generate native DWG)**.
5. On success, use **画像を開く (Open image)**, **DWGを開く (Open DWG)** and **検査結果を開く (Open validation results)**.

The displayed circle limits distance only. A point inside it may still be unsupported. If public-data retrieval fails, also check your network connection.

## If generation is refused

| Message | Meaning / next check |
|---|---|
| `UnsupportedOrAmbiguousGeologicalDomain` | Unsupported, mixed or unresolved geological domain. Do not force acceptance by changing thresholds. |
| `AdvancedContactGeometryRejected` | Contact-geometry checks failed. Inspect the run record. |
| `AdvancedDwgContractRejected` | Area or drawing-contract checks failed. This is not a successful DWG result. |
| `native writer prerequisites are missing` | Check AutoCAD installation and the bundled drawing plugin DLL. |

Success elsewhere does not validate the refused location. Include the error name, environment and reproduction steps in an issue, but do not disclose private site coordinates or drawings.

## Inspect the result

Check endpoint coordinates, azimuth, lithology names, inference annotations, scales, legend, blank areas, crossings and unwanted lines. If human inspection finds a problem, do not accept the drawing solely because automated tests passed. Do not use these hypothetical sections for engineering decisions.

## Reproduce the synthetic example

The bundled example uses an eastward 500 m route and seed 880100. Exact endpoints and explicitly synthetic terrain/geology are in [input.json](../examples/synthetic_plain/input.json). The unchanged Advanced V2 calculation and drawing-contract pipeline runs; only external acquisition is supplied from this fixture.

From the repository root, using a Python environment with the dependencies installed:

```console
python -B tools/reproduce_sample.py
```

AutoCAD is not required for calculation, PNG and drawing-contract generation. Regenerated geometry is compared against the saved sample. File integrity remains SHA-256-based; coordinate comparisons allow an absolute 1e-6 m numerical tolerance, while non-coordinate content and structure are strict. The comparison and exact-hash status are recorded in `public_sample_check.json` under the generated run directory. This is a software reproduction test, not a claim of geological or survey accuracy.

For a new native DWG and reopen validation on Windows with AutoCAD 2027:

```console
python -B tools/reproduce_sample.py --native
```

The [sample DWG](../dwg/synthetic_plain.dwg) and [preview](../examples/synthetic_plain/section_preview.png) can also be inspected without reproducing them. Choosing the same endpoints through the normal GUI retrieves live data and will **not** reproduce this synthetic input. Do not present the example as a successful real-site reconstruction.

DWG byte-for-byte reproducibility is not required because timestamps and internal AutoCAD information may differ. Generic DEM/GSJ headings remain in the sample PNG, but its actual input is synthetic; the fixture and its synthetic-data annotation are authoritative. The sample's simple, banded plain section is not a demonstration of advanced 3D structures.

## Developer checks

```console
python -m pip install -r requirements-dev.txt
python -B tools/check_package.py
python -B tools/run_tests.py
```

These are package-integrity and selected Python regression checks, not substitutes for interactive GUI testing or testing in AutoCAD.

Drawing-plugin source is under `app/subprojects/geologic_3d_engine/advanced_v2/native/`. Rebuilding requires the .NET 10 SDK and reference DLLs from an installed AutoCAD 2027. Autodesk's DLLs are not bundled.
