# Advanced nationwide section extension (v2 experimental)

This tree is deliberately separate from the frozen basic release candidate.
It may call the public 1.0 interfaces, but it must not modify their algorithms,
schemas or expected artifacts.  Its outputs use `AdvancedJapanSection-2.x` IDs
and are never silently substituted for basic-version outputs.

The extension accepts a Japanese centre coordinate, length, azimuth and seed;
derives an exact great-circle route; acquires GSI/GSJ plan evidence; selects a
supported broad geological-domain prior; runs the existing invariant gates;
then creates an integrity-bound native-DWG handoff and an optional PNG preview.
Unsupported, mixed, unresolved, offshore or missing-evidence cases fail closed.

When PNG promotion is disabled, the rendered preview is still retained as
audit evidence because rendering executes the pre-output compliance gate. DWG
remains the primary artifact.

In addition to the frozen v1 rock-domain models, this extension owns an
isolated `UnconsolidatedSedimentTerrain` prior.  It is a synthetic domain-scale
material succession only: it never infers a local buried valley, channel,
fault, or formation order from the surface map. Artificial, mixed, and
unresolved domains remain typed refusals until suitable underlying-geology or
segmentation evidence exists.

For an artificial surface route, Advanced V2 samples three equal-length
surrounding transects at 60-degree angular offsets. Artificial and unresolved
samples are excluded, and an underlying broad prior is used only when natural
coverage and dominance thresholds pass. The output records that this is a
surrounding-map inference. It is never promoted to observed local geology.

The Advanced GSJ vocabulary layer additionally recognizes broad nationwide
deposit labels such as terrace and fan deposits. It wraps, and does not modify,
the frozen v1 classifier.

All subsurface geometry remains an `Experimental` synthetic hypothesis.  A
successful DWG does not establish local geological truth.

## Advanced V2 contact and publication policy

For `ConservativeRegionalPrior_NoLocalizedEvents`, contacts are now constructed
by sequentially stacking strictly positive, layer-specific thickness fields.
The fields use a Matérn 3/2 covariance at two bounded length scales, and every
bottom is the exact next top.  This removes the former harmonic, excessively
smooth appearance without introducing independent free-form curves.  It is a
synthetic numerical prior only; mapped surface geology, modern terrain and the
choice of a visually pleasing seed do not establish buried geometry.  Any
localized fault, fold, intrusion, lens or erosion architecture is outside this
policy and must enter through its own evidence-controlled event path.

When drafting-scale rounding extends the frame slightly below the generated
model boundary, Advanced V2 continues the already selected deepest unit to the
frame. It does not invent a different basement lithology. The added polygon is
classified as `SyntheticBasalContinuation`, links back through
`continuationOfUnitId`, and remains an explicit `SyntheticAssumption`; it is
not evidence of local subsurface truth. Every coloured hatch layer name also
ends with the sanitized normalized lithology label it represents.

Each generated bottom boundary records a `bottomContactClass` and its effective
scale-relative covariance parameters.  The current broad no-local-event policy
distinguishes `WeatheringFront` from `ConformableDepositional`; the final
`ModelCutoff` receives no stochastic roughness rule.  Faults, unconformities,
intrusions and erosion surfaces are not silently emulated by these classes and
remain outside this policy until their evidence-gated event paths are used.

Native output contains separate `GEO_JP`, `GEO_EN`, `GEO_TOPOLOGY_QA` and
`GEO_MONOCHROME_QA` A3 layouts. All titles, notes, frames, legend swatches and
legend labels are native model-space entities. Each paper-space layout contains
only locked viewports onto the shared geology and its matching model-space sheet.
synthetic-use disclaimer.  The monochrome QA layout requires
`monochrome.ctb`; the topology layout hides hatch layers in its viewport.

Native-DWG structural validation is not a visual acceptance decision.  A release
candidate must copy `post_generation_visual_adjudication.template.json` into its
run directory as `post_generation_visual_adjudication.json`, bind it to the exact
DWG bytes with `reviewedDwgSha256`, and inspect both the plotted output and all
four layouts.  Every checklist value must be true before changing `decision` to
`Accepted`.  `verify_run.py` rejects a shallow acceptance, a different DWG hash,
missing layouts, mojibake, blank geology, clipping, missing ticks, an unfilled
model lower limit, hidden contacts, ineffective monochrome output, or a topology
view that still contains hatches.

AutoCAD may rewrite a DWG when it is opened.  Post-generation raster QA must
therefore use `advanced_visual_qa.render_disposable_model_preview`, which opens
a temporary copy and proves the maintained DWG hash is unchanged.  A Native
DWG run is not independently acceptable until
`post_generation_visual_adjudication.json` records an explicit `Accepted` or
`Rejected` decision; missing or pending visual review fails verification.

Every successful run can be independently checked with
`research/geologic_dwg_generation/tools/verify_advanced_japan_run.py`.  The
verifier recomputes artifact and nested contract hashes, route length, the
frozen-v1 boundary, DWG signature/reopen evidence, terrain drafting, bilateral
elevation ticks, and the requested contact-line display policy.

## Launch and command line

- GUI: `subprojects/geologic_3d_engine/Start_Advanced_V2_GUI.cmd`
- CLI example:
  `python -B research/geologic_dwg_generation/tools/run_advanced_japan_section.py --longitude 139.5 --latitude 36.1 --length-m 500 --azimuth 90 --spacing-m 10 --seed 360102 --contacts Show --drafting-density Standard --output research/geologic_dwg_generation/outputs/advanced_v2_runs`
- Verify:
  `python -B research/geologic_dwg_generation/tools/verify_advanced_japan_run.py <run-directory>`

The GUI exposes a 47-prefecture navigation selector which initializes the
editable centre-coordinate fields from an approximate prefectural-office
position. This is only a map-navigation convenience and never geological
evidence. Route length, azimuth, DEM spacing, seed, contact visibility, three
drafting-density presets and the output directory remain explicit. Geological
parameters are governed by versioned domain profiles rather than prefecture
names or ad-hoc visual tuning.

## Portfolio-quality extension (2026-09-11)

- `lithology_selector.py` expands supported broad domains to an explicitly
  gated palette (10–12 geometric bodies for unconsolidated, sedimentary and
  volcanic domains; domain-appropriate lower minima for massive/complex rocks)
  generalized material, weathering-state or display-base labels. Every added
  item is visibly inferred and remains `SyntheticAssumption`; mapped surface
  geology is never converted directly into a buried vertical sequence.
- GSJ Seamless/ZFK and GeoSciML bound terminology. Formal local formation,
  member or group names require route-applicable evidence and are not invented.
- The non-geological interval below the model boundary uses a sparse pattern
  and a separate `MODEL EXTENT`/`モデル範囲` legend group. It is excluded from
  geological legend and contact counts.
- Paper-space allocation reserves title, disclosure and dynamically sized
  legend blocks before centring the viewport. Opposing margins are recomputed
  from paper coordinates and must differ by at most 0.5% of the available
  drawable dimension.
- The already connected contact-geometry module is now protected by a runtime
  spy test and a 24-seed statistical audit. Different stored range values alone
  are insufficient; the contact classes must exhibit distinct empirical
  correlation behaviour.
