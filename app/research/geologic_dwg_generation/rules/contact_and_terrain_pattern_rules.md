# Contact-line and terrain-profile learning rules

## Why previous output was monotonous

V07 used one shared harmonic field and added small, smooth, positive thickness
functions. This guaranteed order but also forced:

- nearly identical wavelength and phase in every contact;
- excessive correlation between distant boundaries;
- gradual thickness variation everywhere;
- no abrupt facies transition, erosion, pinch-out, channel, growth stratum, or
  mechanically localized deformation;
- an approximately symmetric fold with no observation-based asymmetry;
- similar curvature magnitude at all stratigraphic levels;
- no change in structural style across faults or unconformities.

The result was visually equivalent to offset copies of one line. Adding random
noise would only make it untidy; it would not make it geological.

## Contact lines are event histories

A contact profile must be decomposed into interpretable components:

```text
contact = depositional_geometry
        + compaction_or_drape
        + structural_deformation
        - erosional_truncation
        + fault_displacement
```

Only components supported by the declared geological setting may be applied.

## Patterns to learn from real sections

### Conformable sedimentary contacts

- Adjacent contacts are correlated but not exact offsets.
- Local thickness varies by facies, accommodation and compaction.
- Correlation should be measured separately for fold limbs, hinge zones and
  undeformed intervals.
- Thickness change must be expressed normal to bedding when scale and geometry
  permit, not only as a vertical Y difference.

### Folded contacts

- Measure limb dip, hinge position, hinge curvature, interlimb angle,
  wavelength, amplitude, asymmetry and vergence.
- Do not assume a sinusoid. Natural folds may have broad hinges and planar
  limbs, tight hinges, asymmetric limbs, or depth-dependent style.
- Compare thickness in hinge and limb domains to distinguish parallel/flexural
  behavior from similar-style or growth deformation.
- A fold inferred without bedding, map pattern, boreholes or another stated
  control must be marked as interpretive, not observed.

### Lenses, intertonguing and pinch-outs

- Measure lens length, maximum thickness, position of maximum thickness,
  endpoint taper shape and host-contact deflection.
- The two endpoints need not be symmetric.
- Several tongues may overlap laterally without allowing polygons to overlap.
- A unit described as poorly continuous must not be generated as a section-wide
  constant-thickness band.

### Erosional and buried-valley contacts

- Valley bases may be laterally offset and strongly asymmetric.
- Fill thickness follows relief on the erosional surface and varies sharply
  between buried terrace and thalweg.
- Younger internal fill contacts may drape, onlap or flatten upward; they should
  not be parallel copies of the valley floor.
- GSJ's Hinuma example reports a broad buried terrace near -15 m and a valley
  deeper than -60 m whose deepest part is displaced toward one side. This is a
  direct counterexample to symmetric synthetic troughs.

### Faulted contacts

- Split the section into structural blocks.
- Generate or project contacts inside each block, then apply a documented fault
  relationship and displacement.
- Curves on opposite sides must not be smoothly connected through the fault.

## Terrain-line learning

For a realistic technical section, terrain should normally come from measured
or published control such as survey points, contours, DEM/LiDAR, or the source
cross section. A freely invented terrain function must be labeled synthetic.

Measure and preserve:

- profile length and sampling interval;
- absolute or normalized elevation;
- slope and slope-change distribution;
- ridge/valley position, relief and asymmetry;
- convex, straight and concave slope segments;
- terrace tread and riser geometry;
- channel/valley-bottom width;
- correspondence with faults, resistant units and surficial deposits;
- smoothing scale used by the source.

Do not apply FILLET to the whole terrain profile. Survey-derived profiles may be
resampled or smoothed only with a stated tolerance that preserves control points.

## Anti-monotony is not randomness

Variation must be conditional:

- thickness variation conditioned on depositional environment;
- curvature variation conditioned on structural domain;
- discontinuity conditioned on fault, erosion or nondeposition;
- shallow geometry conditioned on terrain and geomorphology;
- uncertainty conditioned on distance from observations.

Unconditioned noise, different sine phases, and randomized control points are
not accepted substitutes for real-section learning.

## Release rule

No future output may be called near-realistic unless its run record identifies:

1. the real traced sections used for each active geological pattern;
2. measured feature ranges;
3. which sampled values were used;
4. geological constraints applied;
5. deviations from the evidence range and their justification.
