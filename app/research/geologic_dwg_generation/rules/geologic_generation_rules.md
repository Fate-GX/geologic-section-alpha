# Geological generation rules

## 1. Model classification comes first

Each run must declare one or more geological event classes:

- conformable deposition;
- lateral facies change, lens, intertonguing, or pinch-out;
- erosion and unconformity;
- folding;
- normal, reverse, thrust, or strike-slip fault projection;
- igneous intrusion;
- surficial or valley-fill deposition.

Lithology name does not determine geometry by itself. Geometry is controlled by
depositional and structural history.

## 2. Conformable stack

### Section trace is an intersection, not a perspective projection

A geological cross section is a two-dimensional representation obtained by
intersecting three-dimensional geological surfaces with a declared vertical
section plane. It is not a camera projection of several surfaces located at
different depths in front of or behind one another.

Consequently, two ordinary bedding/contact traces must not cross merely because
their parent surfaces occupy different positions perpendicular to the section.
That apparent crossing may occur in a perspective view of a 3-D model, but it is
not valid in the 2-D section-plane model used by this project.

Every plotted contact point must belong to the same declared section plane, or
be an explicitly projected observation whose projection distance is retained as
evidence. Projecting observations onto the section constrains interpretation; it
does not permit bedding traces to pass through one another.

For adjacent boundaries sampled at the same section coordinate `s`:

`upper_i(s) = lower_i(s) + thickness_i(s)`

with `thickness_i(s) > minimum_resolvable_thickness` except at a declared
pinch-out. Adjacent contacts share a structural component, while thickness may
vary smoothly within evidence-derived bounds.

Independent arbitrary contact functions are prohibited because they allow
unexplained crossings, negative thickness, and sequence reversal.

## 3. Lens and pinch-out

- A lens replaces part of its host; it must not overlap the host polygon.
- Its upper and lower contacts converge smoothly at declared endpoints.
- A pinch-out is a topology event where thickness reaches zero, not an accidental
  crossing of two independent curves.
- Length/thickness ratios must come from traced examples for the applicable
  depositional setting.

## 4. Unconformity

- Construct older units first.
- Apply an erosional truncation surface.
- Generate younger units above that surface.
- Older contacts cannot continue through the unconformity unless shown as
  concealed interpretation on a separate confidence layer.

## 5. Fault

- Apply displacement consistently to every affected contact.
- Record fault type, dip, throw/apparent separation, affected units, and evidence.
- Repetition or omission of units must agree with fault sense.
- Contact crossing is not a substitute for a fault.

## 6. Terrain and near-surface units

Terrain is not another stratigraphic contact. It truncates geological units.
Surficial deposits occupy explicit closed regions tied to geomorphology such as
valleys, terraces, colluvial aprons, or weathered cover.

## 7. Prohibited shortcuts

- repeated sine waves used as finished geology;
- applying one FILLET radius to every contact;
- coloring first and inventing contacts afterward;
- independent hatch polygons with approximately matching edges;
- unexplained same-unit internal contacts;
- claiming realism without source traces and validation evidence.
## Random synthetic-section generation additions (2026-08-22)

- Random generation is scenario- and event-first, never independent polygon-first.
- Choose one regionally supported lithology/stratigraphy family per generated
  section. Do not combine unrelated units merely for color variety.
- Build an undeformed stratigraphic package, then apply typed geological events
  in recorded chronological order.
- Related contacts use a shared structural field and correlated positive
  thickness. Independent full-amplitude noise per contact is prohibited.
- Noise may add bounded small-scale character only after the large-scale geology
  is valid. Faults and unconformity truncations remain explicit discontinuities.
- Maintain four separate artifacts: hidden ground truth, sampled observations,
  interpreted section, and published DWG.
- Store generator version, deterministic seed, region profile, scenario, event
  history, distributions, rejected attempts, and final validation results.
- Publish only candidates that pass geometry, stratigraphy, structure, evidence,
  and persisted-DWG gates.

### Raster-generative-AI boundary

- AI-rendered geological cutaways are never ground truth or positive geometry
  templates unless their semantic model, sources, vector topology, and validation
  are independently available.
- Treat attractive AI images as presentation references or adversarial negative
  cases only.
- Validate global and local consistency separately: contact adjacency, complete
  line continuation, legend/entity agreement, fault kinematics, section scale,
  and source scope.
- Generate labels and symbols from semantic event/unit records. Never allow an
  independently generated label to contradict its geometry.
- A local reference section cannot be presented as a generalized regional model.

## Public-section-corpus additions (2026-08-22)

- Select a `GeologicalSetting` before sampling geometry. At minimum keep separate
  corpora for alluvial lowland, glaciofluvial sediment, stable sedimentary basin,
  fault basin, fold-thrust belt, and salt-related deep structure.
- Prefer paired public data containing boreholes or stratigraphic picks plus
  interpreted horizons/sections. A section image alone is not a training pair.
- Every value has an evidence class: `Observation`, `Interpretation`, or
  `ModelPrediction`. Synthetic boreholes and arbitrary model sections are model
  predictions, not new observations.
- Preserve `NotPenetrated`, `Absent`, `Unknown`, and `Present` as distinct states.
  Neither non-penetration nor unknown may be converted to zero thickness.
- Sample contact elevation, positive thickness, dip, curvature and topology
  jointly. Include observation distance, standard deviation and occurrence
  probability where the source model provides them.
- A section-network model must pass intersection consistency: at every crossing
  of two section traces, corresponding contacts have the same elevation, unit
  order and event state within the declared numerical tolerance.
- Increased distance from control data increases uncertainty; it does not grant
  permission to add higher-frequency random detail.
- Foreign formation names and successions remain within their regional corpus.
  Only transferable process rules may be reused in a Japanese synthetic section.
