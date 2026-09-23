# Conditional patterns from terrain to likely section geometry

## Important limitation

Terrain does not uniquely identify subsurface lithology. Similar valleys can be
produced by weak-rock erosion, fault control, buried-channel erosion, glaciation,
karst, or structural subsidence. The rules below generate ranked hypotheses,
never a single asserted geology. A generated interpretation must state which
observations discriminate among alternatives.

## Pattern record format

Each pattern stores:

```text
TerrainPatternId
ObservedTerrainFeatures
LikelyProcesses
LikelySectionGeometry
AlternativeExplanations
RequiredEvidence
SourceIds
Confidence
```

## TP-01 — alternating parallel ridges and valleys

**Observed terrain**

- repeated elongate ridges and valleys;
- broadly parallel trends;
- trellis-like drainage where visible.

**Likely section candidates**

- folded and/or faulted sedimentary strata;
- resistant sandstone, conglomerate or quartzite supporting ridges;
- more erodible shale/slate or soluble carbonate occupying valleys;
- anticline/syncline geometry may be present, but ridge does not automatically
  equal anticline and valley does not automatically equal syncline because
  differential erosion can invert structural relief.

**Required evidence**

- bedding attitudes and map-unit traces;
- ridge lithology and valley lithology;
- fold-axis/fault mapping;
- section orientation relative to strike.

**Sources:** USGS-HA730L, USGS-HA730G. Confidence: medium when only terrain is
known; high only after structural and lithological control.

## TP-02 — broad lowland with a narrow/deep asymmetric depression

**Observed terrain or subsurface control**

- broad plain or terrace;
- buried or present channel displaced toward one side;
- a terrace bench on one flank.

**Likely section candidates**

- erosional bedrock valley filled by alluvium;
- basal gravel concentrated near the deepest channel;
- terrestrial sand/mud in the lower fill and finer marine/fluvial deposits above,
  depending on sea-level and basin history;
- fill thickness changes sharply between terrace and thalweg;
- younger contacts commonly flatten or drape upward instead of copying the
  valley floor.

**Alternatives**

- fault-controlled trough;
- karst depression;
- structural basin.

**Required evidence**

- boreholes, seismic profiles or basal-depth contours;
- grain size/facies and age control;
- mapped faults and terrace levels.

**Sources:** GSJ-HINUMA-1975, GSJ-NOBI-1979, USGS-SIM3524. Confidence: medium.

## TP-03 — mountain front with fan-shaped piedmont and a flat basin floor

**Observed terrain**

- steep mountain front;
- convex fan surfaces issuing from canyon mouths;
- overlapping fan toes and flatter axial valley/floodplain.

**Likely section candidates**

- coarse proximal alluvial-fan deposits thickening toward active source canyons;
- lateral transition to finer basin/floodplain sediment;
- structural trough or fault-bounded basin may increase accommodation;
- younger fans can onlap, bury or be offset/warped by active structures.

**Alternatives**

- debris-flow apron without a major structural basin;
- glacial outwash fan;
- deltaic fan geometry.

**Required evidence**

- fan-surface ages, clast provenance and grain-size trends;
- fault traces and vertical separation;
- boreholes/geophysics across the basin.

**Sources:** USGS-SANFERNANDO-97163, USGS-OF03-410. Confidence: medium.

## TP-04 — linear scarp separating surfaces of different elevation

**Observed terrain**

- narrow, rectilinear to gently curvilinear slope;
- persistent elevation difference across it;
- possible offset drainage or cultural features.

**Likely section candidates**

- fault surface reaching or approaching the ground;
- fresh scarps are sharper; erosion rounds the upper face and deposits material
  near the foot, making the topographic break offset from or broader than the
  subsurface fault trace;
- colluvium/alluvium may conceal the actual fault at depth.

**Alternatives**

- terrace riser, shoreline, lithologic escarpment or artificial grading.

**Required evidence**

- displaced strata/geomorphic surfaces;
- damage/deformation zone, trench or geophysics;
- consistent movement sense.

**Sources:** USGS-FAULT-SCARP-FIG5, USGS-MF1136-LIMITATIONS,
USGS-CUDDEBACK-061276. Confidence: low from shape alone.

## TP-05 — sinuous floodplain bounded by valley slopes

**Observed terrain**

- low-gradient sinuous corridor;
- abandoned channels, levees or terraces;
- colluvial aprons at valley margins.

**Likely section candidates**

- channel and floodplain alluvium above an erosional bedrock or older-sediment
  surface;
- irregular basal scour and laterally migrating channel bodies;
- colluvium wedges from side slopes intertonguing with alluvium;
- terrace deposits perched above the active floodplain and separated by erosional
  risers.

**Required evidence**

- boreholes/test pits across channel and terraces;
- geomorphic surface mapping and ages;
- clast/facies changes from slope to channel.

**Sources:** USGS-SURFICIAL-B2123, USGS-CIRC54. Confidence: medium.

## Generator use

The terrain classifier may propose one or more pattern IDs. It must not create
subsurface contacts until the selected hypothesis has sufficient evidence.
Synthetic test DWGs must label the chosen hypothesis and list missing controls.

## GSI Japan evidence additions (2026-08-22)

- Use GSI DEM as the preferred Japanese ground-surface constraint, retaining DEM
  type, source survey, production date, CRS, vertical datum and stated accuracy.
- Do not interpret seams between DEM types or acquisition dates as geological
  contacts, scarps or faults.
- GSI landform classes update scenario priors but never become subsurface contact
  observations by themselves.
- Alluvial generation may be conditioned by fan, natural levee, former channel,
  backswamp and floodplain classes, then must be checked against boreholes and
  GSJ/NIED geological evidence.
- Artificial cut, fill, reclamation and former-water classes create explicit
  anthropogenic events/layers rather than being absorbed into natural strata.
- Use historical imagery to distinguish present morphology from former channels
  and pre-development terrain. Every image observation retains acquisition date.
- For surveys after 2025-04-01, record the use of Geoid 2024 Japan and its
  surroundings, plus island datum corrections where applicable. Never mix
  ellipsoidal height, orthometric elevation and drawing-local Y.
