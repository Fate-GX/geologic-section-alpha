# Lithology-property knowledge for generation

## Purpose and caution

Rock properties can influence landform, contact preservation, weathering,
fracturing, groundwater and surficial cover. They do not determine one unique
shape. Values vary with cementation, porosity, mineralogy, alteration, joints,
weathering, scale and stress history.

The generator therefore uses properties as conditional weights and constraints,
not fixed stereotypes.

## Property record

```text
LithologyPropertyId
Lithology
FormationOrUnit
Region
Age
WeatheringGrade
Cementation
FractureIntensity
PorosityRange
PermeabilityClass
RelativeErosionResistance
StrengthOrHardnessEvidence
SolubilityOrAlteration
ExpectedRegolith
LikelyLandformEffects
LikelyContactStyle
SourceIds
EvidenceLevel
```

Never store “sandstone = hard” or “limestone = ridge” without qualifiers.

## Conditional knowledge currently supported

### Well-cemented sandstone, conglomerate and quartzite

- Often more erosion-resistant than adjacent shale and can support ridges,
  cliffs, caprock, hogbacks or plateau rims.
- Strong fracturing can reverse that relation locally and promote erosion.
- In sections, a resistant cap may preserve remnants above weaker units and
  produce steep breaks rather than smoothly parallel terrain.

Sources: USGS-HA730L-REGIONAL, USGS-KENTUCKY-PHYS.

### Shale, mudstone and siltstone

- Commonly weather/erode more readily than well-cemented sandstone and may form
  valleys or gentler covered slopes.
- Can behave as a low-permeability or mechanically weak interval.
- Slope deposits may conceal the bedrock contact; visible terrain breaks should
  not be forced to coincide exactly with the contact.

Sources: USGS-HA730G-PLATEAU, USGS-KENTUCKY-PHYS.

### Limestone and dolomite

- Resistance is context-dependent; massive competent beds can form cliffs or
  ledges, while dissolution can produce lowlands, sinkholes and irregular karst
  surfaces.
- Solution openings and residuum can make the bedrock surface extremely uneven.
- A limestone contact should not automatically be drawn as a smooth lens or a
  ridge-forming band.

Sources: USGS-HA730G-VR, USGS-HA730G-PLATEAU.

### Unconsolidated sand, gravel, silt and clay

- Geometry is controlled strongly by depositional landforms and accommodation:
  channels, floodplains, fans, terraces, coastal plains and buried valleys.
- Gravel commonly occupies channel bases or proximal fans; fines may drape or
  fill broader low-energy areas, but the actual sequence must be region-specific.
- These units may onlap and thicken rapidly rather than follow constant bands.

Sources: GSJ-HINUMA-1975, USGS-SANFERNANDO-97163,
USGS-HA730L-REGIONAL.

### Volcanic and intrusive rocks

- Geometry depends on eruption/intrusion style: flow, tuff sheet, dike, sill,
  plug or pluton.
- Hardness alone cannot choose geometry. A basalt flow follows paleotopography;
  a dike crosscuts; a sill is broadly concordant; a pluton truncates hosts.
- Weathering and jointing may control cliffs, blocky slopes or subdued terrain.

More authoritative regional examples are required before parameterization.

## Candidate uses in the generator

Property knowledge may influence:

- relative terrain erosion rate by unit and weathering state;
- preservation probability of caprock;
- slope angle distribution and likelihood of cliffs/benches;
- regolith/colluvium thickness and contact concealment;
- likelihood of karst irregularity in exposed carbonate;
- expected fracture/groundwater annotations;
- confidence that a terrain break coincides with a lithologic contact.

It must not directly alter stratigraphic order. Order comes from regional
stratigraphy and geological history.

## Validation experiment

For each property-informed generation, create paired models:

1. geometry without property conditioning;
2. geometry with evidence-based property conditioning.

Compare both with held-out real sections using terrain/contact alignment,
slope-curvature distributions, unit exposure width and qualitative geological
review. Retain the property rule only if it improves held-out agreement without
introducing contradictions.
