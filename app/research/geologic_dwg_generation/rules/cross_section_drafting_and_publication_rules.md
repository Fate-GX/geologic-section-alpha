# Geological cross-section drafting and publication rules

## Scope

These rules govern a synthetic portfolio DWG intended to resemble a carefully
prepared professional geological cross section without misrepresenting itself as
measured project data.

The drawing must pass two independent questions:

1. Is the geological interpretation internally credible?
2. Is the sheet drawn, annotated and published according to professional
   cartographic/CAD practice?

Passing one does not imply the other.

## Required sheet components

### Identification

- definitive title containing “地質断面図” / “Geologic Cross Section”;
- section identifier such as A–A′, using a real prime mark or consistent CAD
  equivalent;
- direction labels at both ends, derived from declared section azimuth;
- project/portfolio title and sheet identifier;
- revision, generation date and generator/version ID.

### Scale and coordinates

- horizontal representative fraction and graphical bar scale;
- vertical representative fraction and vertical tick scale;
- explicit vertical exaggeration, including `1×` when none is used;
- elevation datum, normally mean sea level unless another datum is justified;
- units next to axes/scales;
- section length and stationing consistent with the source profile;
- elevation ticks on both ends when the layout permits, not just one side.

USGS guidance requires the vertical scale and any exaggeration to appear on the
section and treats mean sea level as the usual datum. Excessive exaggeration can
misrepresent structure and must be avoided or justified.

### Geological content

- terrain/profile line;
- map-unit polygons/hatches;
- contacts and faults with confidence-specific symbols;
- unit labels or codes where readable;
- bedding/structure observations and projected controls when the interpretation
  uses them;
- boreholes, test holes, wells or other controls when present;
- concealed/inferred geometry visually distinguishable from observed geometry;
- notes for truncation, projection or uncertainty that cannot be encoded by line
  style alone.

### Explanation/legend

- ordered youngest-to-oldest or otherwise explicitly stated unit order;
- unit code, formal/generalized name, age and brief lithologic description;
- swatches that reproduce the actual fill/pattern/color;
- explanation of contact, fault, fold and confidence symbols;
- source/control note and geological credits;
- synthetic-data disclosure.

## Synthetic portfolio disclosure

The following statement, or an equivalent Japanese/English pair, must be visible
in the sheet notes and stored in DWG metadata:

```text
疑似データ：公開地質資料を参考に作成したポートフォリオ用の合成地質断面図。
実在地点の調査・設計・施工には使用できません。

SYNTHETIC DATA: Portfolio geologic cross section derived from published
geological references. Not for site investigation, design, or construction.
```

Do not invent a real company, client, borehole owner, survey certification,
official seal, approval signature or exact real-world project claim.

## Line hierarchy

Exact plotted lineweights are output-scale dependent and must be tested on the
target sheet, but relative hierarchy is required:

1. section frame and principal fault/contact emphasis;
2. terrain and observed contacts;
3. inferred/concealed contacts and secondary structures;
4. grid and construction/reference lines;
5. hatches behind all linework.

The grid must not compete visually with geology. Use a screened/gray plot style
or light lineweight. Contact confidence must not depend on color alone.

## Contact and structure symbolization

- observed/accurately located contact: solid line;
- approximate/inferred/concealed contacts: distinct approved dash/dot patterns;
- faults use type-appropriate symbols and movement sense only when supported;
- fold axes, bedding, cleavage and lineation follow JIS/FGDC conventions selected
  for the declared publication style;
- a custom symbol is permitted only when it conflicts with no standard symbol
  and is explained in the legend.

Use one declared symbol regime per sheet: `JIS-oriented Japanese` or
`FGDC-oriented international`. Do not silently mix conventions.

## Color and pattern

- color/pattern conveys unit identity or age according to the chosen standard;
- adjacent units remain distinguishable in color, grayscale and common
  color-vision-deficiency simulations;
- SOLID fills may be used for the requested processing test, but the legend must
  match exactly;
- patterns must be clipped to the correct polygon and remain behind linework;
- avoid saturated colors that overpower contacts, labels and controls;
- create a monochrome/print verification even if the portfolio image is color.

## Typography and language layers

- use `MS_GOTHIC`/MS Gothic only where the user's requirement applies and verify
  font persistence after reopen and PDF output;
- Japanese and English versions use separate, independently switchable layers or
  layouts;
- corresponding titles/labels share intended anchors but may require separately
  sized text boxes to avoid collision;
- do not display both language layers simultaneously in the publication layout;
- no text crosses the frame, scale, legend swatches, control lines or other text;
- use consistent text-height classes for title, headings, labels and notes.

## Layout and plotting

- model space contains full-size geology in drawing units;
- paper space contains sheet frame, title block, notes and controlled viewport(s);
- lock viewport scale;
- use a named page setup and declared paper size/orientation;
- store and test the selected CTB or STB plot style;
- plot lineweights and verify them in PDF/raster output;
- keep a publication layout for Japanese and a separate publication layout for
  English where text length differs materially;
- do not solve English/Japanese layout conflicts by moving model geometry.

Autodesk's native `Layout`, paper-space `BlockTableRecord`, `Viewport`, page
setup and plot-style APIs are the preferred implementation.

## Credits and source note

At minimum include:

- “Geological model and CAD: [portfolio author]”;
- source institutions and cited publications;
- generation date/version;
- declared coordinate/datum status;
- synthetic-data disclaimer;
- link or document reference to the portfolio methodology.

Every source used to infer sequence, geometry, color or symbolization must also
exist in the project source catalog with its canonical URL.
