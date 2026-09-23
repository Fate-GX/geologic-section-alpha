# Universal standards gate implementation

## Applied standards

- JIS A 0204:2019 is the current Japanese authority for geologic-map symbols, colors, patterns, terms, and legend display. Exact pattern/color conformance is not claimed without checking the controlling standard text.
- USGS GeMS TM 11-B10 (2020) is used as the digital representation model: cross-section map-unit polygons and their bounding contacts/faults are distinct, topologically related classes.
- FGDC geologic symbol standard controls observed/inferred/approximate/concealed graphical distinctions where an applicable Japanese rule has not been established.
- IUGS CGI/GeoSciML provides interoperable concept vocabulary; IUGS published igneous nomenclature and its edition are recorded.
- ICS 2026/06 controls international chronostratigraphic terminology.

## Program integration

`tools/AuthoritativeGeoDwg/GeologicStandardsGate.cs` is called before transaction commit by every current generator:

| Generator | Scope | Terminology | Evidence | Maximum current decision |
|---|---|---|---|---|
| BASIC_TEST | DatasetSpecific | LegacyUnverified | SyntheticPriorOnly | Experimental |
| V09 | Buried valley | LegacyUnverified | SyntheticPriorOnly | Experimental |
| V11 | Synthetic sedimentary | LegacyUnverified | SyntheticPriorOnly | Experimental |
| V15 | Coastal lowland | LegacyUnverified | SourceLinked | Experimental |
| V16 | Coastal lowland | LegacyUnverified | SourceLinked | Experimental |
| BADLANDS_PIPELINE | Landscape evolution | UnverifiedProxyTerms | ModelOutputOnly | Rejected |
| ASO_V17 | Aso volcanic region | CurrentNormalized | SourceLinked | Experimental |

The gate writes `GEODWG_UNIVERSAL_STANDARDS` into the DWG Named Objects Dictionary. It records the generator, research scope, terminology/evidence status, standards and effective decision. It also rejects invalid or non-SOLID hatch structures.

## Mandatory behavior for future generators

No future generator may omit the gate. `Accepted` is automatically downgraded when terminology is not `CurrentNormalized` or evidence is not `SourceLinked`. Additional geology, topology, reopen, visual, and publication gates still apply; this gate alone never grants acceptance.

## Remaining migration work

Legacy generators retain their original labels for reproducibility and are not silently rewritten. Each must receive a term-by-term source/normalization manifest and regional evidence profile before its terminology status can change to `CurrentNormalized`.
