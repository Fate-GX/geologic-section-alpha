# Regional lithology and sequence rules

## Hierarchy

Do not generate a sequence from country alone. Use:

```text
country
  -> region
  -> geological province / terrane / sedimentary basin
  -> geological age interval
  -> depositional or igneous/metamorphic environment
  -> formation/member or mapped unit
  -> lithology/facies
  -> observed vertical and lateral relationships
```

A country label is metadata. The province, basin, terrane, age and event history
are the primary controls.

## Regional sequence record

```text
SequenceModelId
Country
Region
ProvinceOrBasin
Terrane
AgeFrom
AgeTo
Environment
TectonicSetting
OrderedUnits
LateralTransitions
Unconformities
Intrusions
Metamorphism
TypicalStructures
TerrainAssociations
SourceIds
EvidenceLevel
SyntheticUseConstraints
```

Each ordered unit stores source formation/member names and a generalized
lithology separately. Generalization must never erase an important unconformity,
facies transition or structural boundary.

## Initial pattern families

These are research hypotheses, not universal templates.

### RLS-JP-01 — Japanese alluvial/coastal buried valley

Candidate sequence from older substrate upward:

1. bedrock or older Pleistocene deposits truncated by an erosional valley;
2. discontinuous basal gravel concentrated near the paleochannel;
3. lower terrestrial sand to muddy sand, locally peat/plant fragments;
4. upper marine clay/silt where transgression affected the basin;
5. shallow fluvial sand and modern floodplain/channel deposits.

Geometry: strongly variable thickness, locally asymmetric thalweg, buried
terraces, lower contacts following erosional relief, upper contacts tending to
flatten or drape. Sources: GSJ-HINUMA-1975 and regional borehole sections.

Use only for a declared late-Quaternary lowland/coastal basin, not for mountainous
bedrock sections.

### RLS-JP-02 — Japanese accretionary/sedimentary complex candidate

Potential elements include sandstone, mudstone/shale, sandstone-mudstone
alternation, conglomerate, chert, limestone lenses and tuff, with folds and
fault-bounded repetition. GSJ-OZAKI-1964 documents rhythmic conglomerate-to-
mudstone successions, discontinuous limestone/chert lenses and fold repetition.

Do not turn this into a fixed nationwide order. The actual mapped formation,
terrane, age and structural position must be selected from GSJ map-sheet data.

### RLS-US-01 — Appalachian Valley and Ridge

Common components: Paleozoic conglomerate, sandstone, siltstone, shale,
limestone, dolomite, chert and locally coal. Compression produced folds and
thrust faults; resistant units can form parallel ridges while weaker/soluble
units form valleys. Fold tightness and faulting vary within the province.

The surface sequence can repeat or omit units across thrusts. Topography cannot
be mapped directly to young-over-old order without structural attitudes.
Sources: USGS-HA730L-REGIONAL, USGS-HA730G-VR.

### RLS-US-02 — Appalachian Plateau / Interior Low Plateau

Mostly gently tilted or nearly flat limestone, sandstone and shale with lesser
siltstone, conglomerate, dolomite, chert and coal. Resistant sandstone can cap
plateaus or isolated hills; shale may act as an erodible/confining interval;
exposed carbonate lowlands may develop karst and thick residuum.

Geometry: broad subhorizontal bands, erosional escarpments, caprock remnants,
valley incision and colluvial wedges—not a sinusoidal fold stack.
Sources: USGS-HA730G-PLATEAU, USGS-KENTUCKY-PHYS.

### RLS-US-03 — Atlantic Coastal Plain candidate

Semiconsolidated to unconsolidated sand, silt, clay, gravel and locally lignite,
with some consolidated limestone/sandstone, generally dipping gently seaward.
Geometry is basinward thickening and gentle dip with channel/lens facies changes,
not mountain-scale tight folds. Source: USGS-HA730L-REGIONAL.

### RLS-US-04 — Edwards-Trinity clastic-carbonate succession

Repeated marine advance/retreat produced lower sand/sandstone with some shale
and limestone and an upper limestone-dominant part. The regional aquifer dips
and thickens southeastward from tens to more than 1,000 ft.

Use only with the appropriate Early Cretaceous Texas regional context. Source:
USGS-EDWARDS-TRINITY.

## Sequence-generation requirements

- Sample only a sequence supported for the declared region and time interval.
- Preserve known superposition, unconformities and cross-cutting relations.
- Model lateral facies transitions; do not assume every unit spans the section.
- Keep formation identity distinct from lithology because one formation may
  contain several lithologies and one lithology occurs in many formations.
- Record absent units as nondeposition, erosion, fault omission or insufficient
  evidence—not silent deletion.
- Retain an explicit uncertainty state when regional data do not support a unit.
