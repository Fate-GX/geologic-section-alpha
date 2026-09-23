# Failure-recovery research synthesis — 2026-08-23

Purpose: identify evidence that directly explains why the pyBadlands-derived DWG was technically valid but geologically and visually unusable, and convert that evidence into enforceable generation rules.

## Scope and limits

The public web cannot literally be searched exhaustively. This pass searched public geological surveys, national standards/guidance, peer-reviewed journals, official software documentation, professional references, and practitioner discussions. Authoritative sources control adoption; forums are used only to discover practical failure modes.

## A. Findings that directly explain the failure

### A1. A section is an interpretation constrained by observations, not a stack of polygons

USGS's digital cross-section workflow begins with DEM terrain, geological polygons, structural measurements and boreholes, then constructs a template for interpretation. The European Commission ground-model guidance likewise illustrates correlation from both the surface map and borehole logs. BGS scientific QA asks whether boreholes, faults, structural measurements, source data and map linework are honoured.

**Adopted rule:** no candidate may be called a geological cross-section unless its evidence manifest contains terrain, section trace, surface contacts and either borehole controls or an explicit synthetic-observation set. A polygon-only model is a geometry diagnostic.

Sources:

- USGS: https://pubs.usgs.gov/of/2005/1428/thoms/
- European Commission JRC: https://eurocodes.jrc.ec.europa.eu/sites/default/files/2024-12/GL2_Assembling-ground-model-deriv-val_ff.pdf
- BGS scientific QA: https://earthwise.bgs.ac.uk/index.php/OR/17/003_Appendix_1

### A2. Correlation requires stratigraphic and sedimentological reasoning

Stratigraphic correlation is not independent nearest-boundary interpolation. Professional references describe hanging data on a correlatable datum and distinguish structural from stratigraphic sections. GSJ's Tokyo Lowland material correlates reference boreholes using facies, depositional systems, N-values and an alluvium basal boundary.

**Adopted rule:** generate a reference-borehole correlation graph before surfaces. Each correlation edge must state unit identity, relative position, facies evidence, confidence and alternative hypotheses.

Sources:

- GSJ standard borehole model: https://www.gsj.jp/data/openfile/no0528/gsj_openfile_report_528.pdf
- AAPG cross-section reference: https://wiki.aapg.org/Geological_cross_sections
- RING correlation uncertainty: https://www.ring-team.org/annual-meeting-papers?id=224027&view=pub

### A3. A water-depth threshold is not a lithology model

The failed classifier used depositional elevation relative to sea level. Published facies models condition spatial architecture on well logs, seismic/model data, geological environment, facies proportions and trends. Training images must represent the geological environment; small changes can materially alter results.

**Adopted rule:** facies classification must be multivariate and temporal. Minimum features are accommodation/water depth, sediment supply or grain-size proxy, depositional rate, erosion/reworking, transport regime, distance to channel/shoreline, vertical transition state and lateral-neighbour state. Every class must output probability and evidence.

Sources:

- MPS training image and conditioning: https://hess.copernicus.org/articles/21/6069/2017/hess-21-6069-2017.html
- MPS review: https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2008WR006993
- Training-image construction review: https://geology.nju.edu.cn/EN/10.16108/j.issn1006-7493.2020049

### A4. Process models and statistical models need conditioning

pyBadlands can provide landscape evolution and stratigraphic history, but an official example is not a regional analogue. Process models can produce architecture, while multiple-point or object-based models reproduce analogue patterns, but neither should be presented as a field-constrained section without hard-data conditioning.

**Adopted rule:** use pyBadlands as a process prior, not as final lithology truth. Condition the result to a region-specific training-image catalogue and synthetic boreholes derived from the same event history.

Sources:

- Badlands examples: https://badlands.readthedocs.io/en/latest/examples.html
- Badlands model inputs/processes: https://badlands.readthedocs.io/en/latest/xml.html
- Process-based reservoir modelling context: https://www.sciencedirect.com/science/article/abs/pii/S026481721400364X

### A5. GemPy and LoopStructural cannot invent missing geology

Implicit models interpolate provided contact/orientation constraints and encode relationships. LoopStructural explicitly models time-aware faults, folds and unconformities, but fold geometries require interpretive constraints. GemPy topology research demonstrates that small structural perturbations can change topology.

**Adopted rule:** software conversion does not count as a new evidence source. Record an information-gain table at every step. A stage that only reformats points must be labelled `RepresentationOnly`. GemPy/LoopStructural must receive independent observation-like constraints and explicit event relationships before being used as realism gates.

Sources:

- LoopStructural time-aware modelling: https://gmd.copernicus.org/articles/14/3915/2021/
- GemPy topology uncertainty: https://gmd.copernicus.org/articles/14/3899/2021/
- map2loop data-knowledge limitation: https://gmd.copernicus.org/articles/14/5063/2021/index.html

### A6. One deterministic model hides the central geological problem

Published work shows interpreter variance depends on data spacing and experience; topology is highly sensitive to uncertainty, especially at faults and unconformities. BGS explicitly relates certainty to borehole and cross-section density and documents model limitations between control points.

**Adopted rule:** generate ensembles, not one answer. Withhold some synthetic boreholes, calculate recovery error, topology frequency and confidence envelopes, then expose uncertainty in the drawing using contact confidence classes.

Sources:

- Borehole cross-section interpretation uncertainty: https://nora.nerc.ac.uk/id/eprint/509008/
- Topological uncertainty: https://www.sciencedirect.com/science/article/pii/S0191814116301122
- BGS uncertainty: https://earthwise.bgs.ac.uk/index.php/OR/14/013_Model_uncertainty
- BGS assumptions/limitations: https://earthwise.bgs.ac.uk/index.php/OR/15/013_Model_assumptions%2C_limitations_and_uncertainty

### A7. Vertical exaggeration is part of geology, not merely graphics

Large vertical exaggeration changes apparent dip, fold shape and perceived thickness. Professional guidance recommends little or no exaggeration for structural sections and requires the amount to be stated. The failed DWG used 100x vertical exaggeration after compressing X, making small numerical differences visually dominant.

**Adopted rule:** structural QA always runs at 1:1. Publication may use a justified second view, normally with much smaller exaggeration, and must display horizontal/vertical scales and datum. A 100x view is prohibited as the sole deliverable.

Sources:

- AAPG cross-section scaling discussion: https://wiki.aapg.org/Geological_cross_sections
- USGS section drafting guidance: https://pubs.usgs.gov/of/1995/ofr95415/pdf/ofr_95-415_c.pdf
- Czech Geological Survey mapping principles: https://cgs.gov.cz/system/files/2024-10/Basic%20principles%20of%20geological%20and%20thematic%20mapping.pdf

### A8. Contact confidence and provenance must be visible

FGDC standards distinguish contacts/faults and their confidence/location states. GeoSciML separates units, structures, observations, measurements, vocabularies and investigation artefacts. A realistic-looking solid line must not imply observed certainty where geometry is inferred.

**Adopted rule:** contacts are separate entities from fill polygons and carry `Observed/Accurate`, `Approximate`, `Inferred` or `Concealed` state plus provenance. AutoCAD line type and metadata derive from this state.

Sources:

- FGDC/USGS symbol standard: https://ngmdb.usgs.gov/fgdc_gds/geolsymstd.php
- GeoSciML: https://onegeology.org/technical_progress/geosciml.html
- GeoSciML portrayal vocabularies: https://onegeology.org/archive/WMScookbook/7_1.html

### A9. Japanese lowland sections require sequence-stratigraphic and geomorphic context

GSJ's Kanto/Tokyo material does not reduce the succession to repeated mud sheets. It includes buried wave-cut platforms, buried fluvial terraces, valley axes, basal gravel, lower/upper sand and mud, N-values, reference boreholes, DEM terrain and basal-surface modelling.

**Adopted rule:** the next Japanese test scenario will use a documented buried-valley/alluvial-lowland architecture. Required elements include basal topography, basal gravel, transgressive valley fill, mud-dominated central fill, sand bodies, upper deposits and Pleistocene substrate; the exact sequence must follow the selected GSJ case rather than a generic fixed template.

Sources:

- GSJ Tokyo/Nakagawa standard columns: https://www.gsj.jp/data/openfile/no0528/gsj_openfile_report_528.pdf
- GSJ Kanto subsurface database: https://gbank.gsj.jp/kantosubsurfacegeoDB/CNV/searchMenu.html
- GSJ central Kanto 3-D modelling: https://www.gsj.jp/data/coastal-geology/GSJ_MMS_40_2014_03_a_sim.pdf

## B. New architecture

```text
regional scenario + event history
              |
              v
 process prior (terrain/erosion/deposition)
              |
              v
 multivariate facies engine + analogue/training image
              |
              v
 synthetic boreholes + surface observations + orientations
              |
              v
 correlation graph + alternatives + confidence
              |
              v
 GemPy / LoopStructural ensemble
              |
              v
 withheld-borehole + topology + geological QA
              |
              v
 AutoCAD native model + publication layouts
```

## C. Metrics required before the next DWG

1. At least 3 control boreholes and 1 withheld borehole.
2. At least 3 lithology/facies classes, unless the selected real analogue is demonstrably monofacies.
3. A named event history and ordered event graph.
4. Facies transition matrix and lateral body-size distributions from the selected analogue corpus.
5. Contact confidence per segment.
6. Borehole recovery: unit order, contact elevation error and facies accuracy.
7. Ensemble topology frequency, not only one non-crossing model.
8. 1:1 structural view plus any explicitly justified exaggerated view.
9. Native DWG reopen validation.
10. Side-by-side visual comparison with the cited reference sections.

## D. Sources rejected or restricted

- Wikipedia: discovery only; not adopted where public agencies or papers exist.
- Reddit/forums: practical warnings only; no geological generation rule adopted without authoritative corroboration.
- Paywalled abstracts: used only for high-level research leads; implementation rules require accessible methods or independent corroboration.
- AI/GAN facies papers: not adopted as the next primary method. A generative network can reproduce training bias and does not solve absent geological conditioning.

## E. Immediate next research task

Build one coherent paired corpus for the Tokyo–Nakagawa lowland from GSJ reference boreholes, interpreted sections, basal-surface data and sequence-stratigraphic descriptions. Extract numeric distributions only after each traced unit/contact is linked to source page/figure and geological meaning. Do not generate another DWG until this corpus and its withheld-borehole test are complete.
