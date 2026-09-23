# Geological terminology versioning and normalization

## Principle

No single “world standard” covers lithology, minerals, formal map units, geological time, engineering soils, structures, and drafting. Each term must be checked against the authority appropriate to its domain. Original wording is evidence and must be preserved, while current normalized wording is a separate field.

## Authority order by domain

1. Igneous rock classification and nomenclature: IUGS recommendations. The currently established published reference remains Le Maitre et al. (2002); IUGS is actively preparing revisions, so the exact edition must be recorded.
2. Interoperable geoscience concepts: IUGS CGI / GeoSciML controlled vocabularies.
3. Chronostratigraphic names and boundary ages: current International Commission on Stratigraphy chart, with version date.
4. Japanese formal/local geological units: preserve the GSJ map-unit name and map edition as a proper name; normalize only its descriptive lithology/age attributes.
5. Japanese engineering geology, soils, roads, reclamation, and drafting: current controlling Japanese public specification, JGS/JIS or agency manual, with year and document identifier.

## Required fields

- `SourceLabel`
- `SourceYear`
- `SourceAuthority`
- `SourceUnitCode`
- `NormalizedLabelJa`
- `NormalizedLabelEn`
- `NormalizationAuthority`
- `VocabularyVersion`
- `TermStatus`
- `NormalizationNote`

Allowed `TermStatus`: `Current`, `Legacy`, `LocalRelativeUnit`, `DerivedDisplayLabel`, `Unverified`, `Deprecated`.

## Publication rule

- Formal/local unit names are not translated into a different formal name. Present romanization or an explanatory translation separately.
- Relative labels such as “older”, “younger”, “new stage”, and “latest stage” are local sequencing unless tied to an ICS unit.
- Historical mineral labels such as `紫蘇輝石` must retain the source quotation but use a current normalized mineral-group term such as `斜方輝石` where justified.
- A label created by combining multiple units is a `DerivedDisplayLabel`, never an official source label.
- Unknown or unresolved equivalence is displayed as `Unverified`; guessing is prohibited.

## Sources checked 2026-08-24

- IUGS Task Group on Igneous Rocks; current work still references Le Maitre (2002) while revisions are being developed: https://www.iugs.org/_files/ugd/f1fc07_cefb1e00fc1f4a9d8d83019958867039.pdf
- IUGS CGI, GeoSciML and multilingual terminology remit: https://cgi-iugs.org/
- ICS current international chronostratigraphic chart: https://stratigraphy.org/chart/
- GSJ Aso source edition: https://www.gsj.jp/Map/JP/docs/vol_doc/volcano-04.html
