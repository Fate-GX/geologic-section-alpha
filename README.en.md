# Geologic Section — Alpha 0.1.0

[日本語](README.md) | English

**An experimental tool that takes two map points and exports a synthetic lithological cross-section to native AutoCAD DWG, using regional reference data.**

This is **not a reconstruction of measured subsurface geology or a model for engineering design**. Information obtained from public elevation and surface-geology data is distinguished from inferred underground conditions. Generation may be refused for some locations.

## Input and example output

| Two-point input diagram (illustrative; no map tiles) | Output from the actual engine |
|---|---|
| ![Synthetic example endpoints](docs/images/route_input.png) | ![Synthetic plain cross-section](examples/synthetic_plain/section_preview.png) |

**Both the terrain and geological inputs in this example are synthetic test data, not field observations.** These images illustrate the input/output relationship, not a live map session. Image annotations and the current GUI are in Japanese; English documentation does not change the application language.

See the [sample DWG](dwg/synthetic_plain.dwg), [reopen validation record](dwg/synthetic_plain_reopen_validation.txt), and [English reproduction instructions](docs/USER_GUIDE.en.md#reproduce-the-synthetic-example).

| Supported | Not provided or guaranteed |
|---|---|
| Two-point map selection and section/DWG generation | Successful generation everywhere inside the selection circle |
| Synthetic interpretation informed by public regional data | Correct real-world subsurface structure or layer thickness |
| GUI workflow with optional advanced settings | Automatic use of the later Next research engine |
| Automated checks and recorded refusal reasons | A replacement for expert assessment or human visual review |

## Quick start

1. Extract the **entire repository** on Windows.
2. Install Python 3.11 or later, including Tkinter and the Windows Python launcher, and AutoCAD 2027. Development tests use Python 3.12; other AutoCAD versions are unverified.
3. Double-click `Geologic_Section.vbs`. On first use, select **セットアップ (Setup)** in the GUI to create a Python environment dedicated to this folder and install dependencies.
4. Select start point A and end point B on the map. The permitted distance is **10–500 m**.
5. Check the output directory and click **検証してネイティブDWGを生成 (Validate and generate native DWG)**. Open the results from the GUI.

Python is not bundled. Internet access is needed for initial dependency installation and for map/regional-data retrieval. Downloading individual source files is insufficient.

## Features

- Computes section length and azimuth from A/B; annotates coordinates and available place names.
- References terrain and surface geology to select a supported geological domain and generate a synthetic section.
- Provides optional seed, DEM sampling interval, contact-line and tick-density settings.
- Saves/loads settings; produces PNG previews and native DWG files with reopen validation.
- Records unsupported conditions, insufficient evidence and drawing-validation failures separately from success.

## Scope of this release

This alpha packages the earlier two-point workflow that the user confirmed was operational. Research-only GUI controls and disconnected Next research modules were removed. Geological generation code and its acceptance thresholds were retained.

**The normal GUI uses the Advanced V2 regional synthetic-section pipeline. It is not the later research version that extracts arbitrary sections from a persisted 3D volume.** Reusable 3D-engine code in the repository does not mean the GUI invokes every feature. Complex fault/fold modeling, automatic interpretation of borehole-log images and expert-grade regional models are not advertised as features of this release.

## Limitations and safety

- The map circle is a **distance limit**, not a guarantee of geological support. Mixed geology, missing data or quality gates may still cause refusal.
- Surface geology does not directly establish underground thickness or contact positions. The output contains hypotheses.
- No survey accuracy beyond the resolution of the input data is claimed.
- The GUI does not import or switch existing AutoCAD profiles. Generation uses a separate Core Console process.
- Frozen calculation components and drawing gates are retained. A successfully saved DWG does not prove geological validity.
- **Do not use the output to make site-investigation, design or construction decisions. Human drawing review is required.**

## Why this project was built

The project grew out of automating *keba* drafting in AutoCAD/Dynamo. That earlier work addressed correspondence between hatch intervals and lithological intersections even when their coordinates did not coincide. The next question was whether regional reference data could be connected to section generation and DWG output. This history does **not** mean keba creation is integrated into this alpha.

Usability was a priority: select two map points, expand detailed settings only when needed, and open images, drawings and checks from one GUI. Routine use should not require editing JSON or running multiple batch files.

Development also exposed two distinct problems: a sampler regression test incorrectly rejecting short routes, and overlapping endpoint/tick labels. The former was separated from route-specific checks using a fixed reference test; thresholds were not simply lowered. The latter was addressed by retaining exact endpoint labels while omitting nearby intermediate labels. More ambitious 3D research remains separate from this smaller alpha.

## Validation status

- The source version was reported operational by the user; this is not nationwide validation.
- The public synthetic sample was generated as a new native DWG and reopened for automated entity/drawing checks.
- The repaired publication CI passed: [Alpha portable checks](https://github.com/Fate-GX/geologic-section-alpha/actions/runs/35857079479). Local tests reported 148 passed and 28 subtests passed.
- Python CI does not exercise AutoCAD or certify geological correctness.
- Fresh live-map acquisition and final human visual inspection of the public-copy DWG remain unverified. Synthetic-input success does not replace them.

Distribution files are checked with SHA-256. Regenerated coordinates are compared with an absolute tolerance of **1e-6 m**, with no relative tolerance; identities, counts and ordering remain strict. This handles tiny numerical differences between CPU computation paths, **not geological uncertainty or surveying accuracy**.

## Documentation and files

- [User guide, refusal reasons and sample reproduction — English](docs/USER_GUIDE.en.md)
- [Development story — Japanese](docs/DEVELOPMENT_STORY.md)
- [Packaging scope — Japanese](docs/ALPHA_SCOPE.md)
- [Validation details — Japanese](docs/VALIDATION.md)
- [Packaging evidence](evidence/packaging_checks.json)
- [Preserved-source provenance](docs/packaging_provenance.json)

`app/` contains implementation, `tools/` launch and verification utilities, `results/` run records, and `app/dwg/` generated DWGs. Normally, users interact only with the GUI. The maintained public sample is in `dwg/`.

## License and external dependencies

MIT License — Copyright (c) 2026 **Hirotou Yuusuek**.

AutoCAD is a separately required commercial product. Autodesk libraries and licenses are not redistributed; the bundled `AdvancedV2GeoDwg.dll` is this project's drawing plugin. Python, NumPy, Pillow, Shapely and development dependency pytest have their own licenses.

The application references public information from the Geospatial Information Authority of Japan (GSI), the Geological Survey of Japan (GSJ/AIST) and related providers at runtime. Attribution is retained in run records and source/rule records. This project's MIT license does not cover third-party data. Check provider terms and attribution requirements before redistributing generated drawings. Previously retrieved map images, raw borehole data and individual users' outputs are not bundled.

Report problems through **Issues → New issue → 不具合報告 / Bug report**. Include only information you can disclose publicly; do not upload confidential site coordinates, client drawings or credentials.
