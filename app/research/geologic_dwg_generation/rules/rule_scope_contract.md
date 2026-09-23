# Rule scope contract

Reusable geological rules use a closed five-value base vocabulary:

- `Global`
- `Domain`
- `Environment`
- `Region`
- `DatasetSpecific`

A narrower subtype may be appended as `Base:Sub`, for example
`Global:EventOntology` or `Domain:SedimentaryFaciesArchitecture`.
Concatenated undeclared values such as `GlobalArchitecture` are invalid.

The base describes applicability breadth. The subtype describes the governed
concept, process or evidence family; it does not expand the base scope.
Schema and runtime validation must reject values outside
`^(Global|Domain|Environment|Region|DatasetSpecific)(:[A-Za-z][A-Za-z0-9_-]*)?$`.
