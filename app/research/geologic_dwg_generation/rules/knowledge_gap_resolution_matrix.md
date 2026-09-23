# Knowledge-gap resolution matrix

## Scope and epistemic rule

The web cannot be exhaustively learned, and geological interpretation is not
uniquely determined by a drawing. This project therefore uses **controlled
evidence coverage**, not a claim of total geological knowledge.

A topic is `ResolvedForScenario` only when:

1. at least one authoritative methodological source defines the mechanism;
2. at least three attributable real sections support the selected setting;
3. the rule has explicit inputs, outputs, constraints and failure states;
4. an unseen held-out section can be reproduced within declared tolerances;
5. geology, topology and reopened-DWG validation all pass.

## Coverage matrix

| Gap | Current evidence | Solvable by research? | Required implementation | Current state |
|---|---|---|---|---|
| Geological interpretation | GSJ, USGS review checklist, USBR mapping manual | Partly; never unique without observations | event-history constraint model | In progress |
| Regional lithology sequences | GSJ ZFK/Seamless, USGS regional atlases | Yes for explicitly selected regions/settings | region-basin-age-environment catalog | In progress |
| Terrain/subsurface relation | GSJ urban geology, USGS physiography/surficial studies | Probabilistically | conditional geomorphic scenario model | In progress |
| Observed vs interpreted | GeMS, FGDC, USGS uncertainty guidance | Yes | separate scientific and locational confidence | Rule established |
| Japanese drafting practice | MLIT/MAFF standards and reference drawings | Yes per declared authority/version | standard profile and layer mapping | In progress |
| Native DWG topology/hatch | Autodesk .NET plus USGS topology | Yes | shared-boundary planar topology, then Hatch | Rule established |
| Publication quality | MLIT/MAFF, USGS illustration rules, ODOT | Yes | layouts, scales, datum, title, legend, collision QA | In progress |
| Automated validation | USGS topology/review plus AutoCAD reopen checks | Yes | three-gate automated test suite | Specification exists |

## Required geological model pipeline

```text
Declared region and depositional/tectonic setting
  -> observation/control dataset
  -> chronological geological event graph
  -> contact/fault network with confidence attributes
  -> mutually exclusive geologic-unit polygons
  -> geological QA
  -> AutoCAD-native entities and associative hatches
  -> topology QA
  -> save/reopen/publication QA
```

The geometry generator must not start from colors or independent polylines.

## Constraint classes

### Hard constraints

- the 2-D section is the intersection of geology with one declared vertical
  section plane, not a perspective projection of separated 3-D surfaces;
- stratigraphic order cannot reverse without a declared fold or fault mechanism;
- contact curves cannot cross except at a declared geological topology event;
- thickness remains positive except at a declared pinch-out or truncation;
- a fault displaces every affected contact consistently;
- an unconformity truncates older contacts before younger deposition;
- geologic unit polygons do not overlap and do not leave unexplained gaps;
- every geologic-unit polygon edge is covered by a classified contact, fault,
  terrain boundary, section frame, or declared model limit.

### Evidence constraints

- surface contact intersections;
- strike/dip converted to apparent dip in the section plane;
- borehole top/bottom intervals and non-penetration inequalities;
- mapped fold axes and fault traces;
- DEM terrain intersections;
- age order and facies correlation;
- reported thickness ranges and their measurement direction.

### Soft constraints

- smoothness appropriate to depositional/structural domain;
- thickness-change distributions from traced analogues;
- local correlation among conformable contacts;
- penalties for departure from observations and inequality constraints;
- regional priors that never override direct evidence.

## Uncertainty schema

Every interpreted feature stores these independently:

```text
ScientificConfidence
LocationalConfidence
LocationMethod
ObservationIds
InterpretationRuleId
AlternativeModelIds
SectionProjectionDistance
SourceURLs
```

Do not reduce these to a single `Observed/Estimated` flag.

## Anti-overfitting rule

No generator parameter may be chosen solely because it makes the current target
DWG look correct. Parameter ranges come from training traces; acceptance is
measured on held-out sections. Failed scenarios stay failed and become backlog
items rather than being manually patched into an expected answer.

## Remaining irreducible limitation

Learning can improve plausibility and standards compliance, but it cannot turn
synthetic data into a measured geological interpretation. The finished portfolio
DWG must continue to state that it is synthetic and not for design, construction,
hazard evaluation or scientific inference.
