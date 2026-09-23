# 海外公的データ・研究監視カタログ（2026-08-22）

| ID | Authority / project | Data or method | Planned role | URL |
|---|---|---|---|---|
| TNO-DINO | TNO Geological Survey of the Netherlands | Boreholes, DGM/DGMdeep, REGIS II, GeoTOP, synthetic boreholes and sections | Highest-priority foreign paired validation | https://www.dinoloket.nl/en/help-subsurface-models |
| BGS-UK3D | British Geological Survey | National-scale interpreted cross-section network | Structural/topological reference; record vintage | https://www.bgs.ac.uk/datasets/uk3d/ |
| USGS-GEOLOG | USGS | Public borehole geophysical logs, including LAS where available | Property-log correlation tests | https://webapps.usgs.gov/geologlocator/ |
| USGS-CVHM2 | USGS | Well-log lithology database, classifications, 3D texture framework | Paired classification/framework validation | https://www.usgs.gov/data/central-valley-hydrologic-model-version-2-cvhm2-well-log-lithology-database-and-texture-model |
| AU-NGIS | Australian governments / Bureau of Meteorology | National groundwater bores, lithology, hydrostratigraphy and aquifer geometry | Cross-region robustness testing | https://data.gov.au/data/dataset/national-groundwater-information-system |
| AU-EXPLORATION-2026 | Australian Government | Digital exploration submission guidance v5.0, March 2026 | Input schema and provenance reference | https://www.australiaminerals.gov.au/__data/assets/pdf_file/0005/189392/Australian-guidelines-for-the-submission-of-digital-exploration-data-V5.0-Mar-2026.pdf |
| CAGEO-GEO-METRICS-2026 | Elsevier / Dutch case study | Geography-, sequence- and position-aware evaluation | Adopt into validation gates | https://doi.org/10.1016/j.cageo.2025.106043 |
| EGU-SPATIAL-VALIDATION-2026 | EGU / Ghent University | Conditional subsampling of clustered legacy boreholes | Adopt spatial holdout principle | https://meetingorganizer.copernicus.org/EGU26/EGU26-20968.html |
| JRC-GROUND-MODEL | European Commission JRC | 1D-to-2D/3D uncertainty, interpolation and extrapolation | Adopt evidence-state separation | https://eurocodes.jrc.ec.europa.eu/sites/default/files/2024-12/GL2_Assembling-ground-model-deriv-val_ff.pdf |
| MATHGEO-LOG-BENCH-2026 | Mathematical Geosciences | Public FORCE/Geolink lithology benchmark | Classifier benchmark only | https://link.springer.com/article/10.1007/s11004-026-10300-1 |
| IAEG-WC-2026 | IAEG | XV World Congress, Delft | Watch proceedings and datasets | https://iaeg.info/event/xv-iaeg-world-congress/ |
| IAEG-UNCERTAINTY-COURSE-2026 | IAEG C28 / ISSMGE TC304 | Engineering geological model uncertainty course | Watch for released guidance/materials | https://eurogeologists.eu/event/56389/ |
| BGS-UK3D-OPEN | British Geological Survey | 20,000+ km interpreted section network, 3D Shapefile and GeoPackage | Structural/topological validation | https://www.bgs.ac.uk/datasets/uk3d/ |
| TNO-DGM-DATA | TNO Geological Survey of the Netherlands | Horizon top/base/thickness, standard deviation, occurrence probability, absence/non-penetration points | Uncertainty-aware paired validation | https://www.dinoloket.nl/en/search-and-request-dgm |
| GSI-IRELAND-3D | Geological Survey Ireland | Quaternary and bedrock models, virtual sections and synthetic boreholes | Separate shallow and bedrock model validation | https://www.gsi.ie/en-ie/programmes-and-projects/geological-mapping/projects/Pages/3D-Geological-Models.aspx |
| AGS-PGF-V2 | Alberta Geological Survey | 1,235,761 picks, 62 zones, grids and extents | Basin-scale sequence and thickness validation | https://ags.aer.ca/publications/all-publications/3d-pgf-model-v2 |
| BGR-TUNB | BGR and German state surveys | North German Basin model: horizons, faults, salt structures and arbitrary sections | Deep-basin structural scenario | https://www.bgr.bund.de/DE/Themen/Nutzung_tieferer_Untergrund_CO2Speicherung/Projekte/Nutzungspotenziale/Abgeschlossen/TUNB.html |
| SWISSTOPO-3D | Swiss Geological Survey | swissBEDROCK3D and swissJURA3D | Alpine/Jura bedrock and fold-thrust scenarios | https://www.swisstopo.admin.ch/en/3d-geology |
| GNS-MAP-3D | Earth Sciences New Zealand / GNS | GIS geology, structural measurements, fault-displaced stacked 3D units | Fault and regional vocabulary reference | https://www.gns.cri.nz/our-science/land-and-marine-geoscience/geology-of-new-zealand/geological-maps/using-our-geological-maps/ |

## Acceptance rules

- Downloaded data must retain dataset version, license, CRS, vertical datum and retrieval date.
- A regional model is a model output, not a borehole observation and not local ground truth.
- Training and validation are separated by borehole and spatial block.
- A foreign stratigraphic succession is never copied into a Japanese synthetic section solely because it looks realistic.
- Conference announcements remain `Watch` until methods or materials are public.
