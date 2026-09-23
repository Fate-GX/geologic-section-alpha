# Universal evidence-to-section architecture

## Mandatory architecture

All current and future section programs use the same pipeline:

1. evidence ingestion;
2. source/version validation;
3. terminology normalization without destroying original labels;
4. regional and depositional/volcanic/structural applicability checks;
5. observation versus interpretation separation;
6. geological event and stratigraphic constraint construction;
7. geometry generation from typed constraints;
8. topology and uncertainty validation;
9. cartographic representation using the applicable standard/version;
10. native AutoCAD DWG creation and reopen validation;
11. visual and publication QA.

## Universal engine

The common engine contains no locality-specific coordinates or expected unit sequence. It owns:

- evidence and provenance schema;
- terminology/version audit;
- vocabulary and standard version registry;
- observation/inference/confidence classes;
- stratigraphic ordering and geological-event constraints;
- non-crossing, positive-thickness and permitted-exception topology;
- AutoCAD native entity and hatch rules;
- bilingual layout and validation gates.

## Regional evidence profile

Each locality is a data package containing:

- region, geological province/basin/terrane and coordinate reference system;
- line of section and terrain source;
- original map-unit codes/names and normalized terms;
- boreholes, measured sections, geophysics and field constraints;
- event history and published age constraints;
- source-linked parameter ranges, never one tuned expected answer;
- explicit unknowns and prohibited extrapolation ranges.

## Research rule scope

Every adopted finding declares one scope:

- `Global`: broadly valid representation or validation principle;
- `Domain`: e.g. volcanic, sedimentary, metamorphic, engineering geology;
- `Environment`: e.g. caldera, delta, buried valley, reclaimed coast;
- `Region`: named geological province or locality;
- `DatasetSpecific`: one survey, map edition, borehole set or transect.

The engine must reject use outside the declared scope unless a separate source supports the extension.
