import tempfile,unittest
import json
from pathlib import Path
from PIL import Image
from geologic_3d_engine.section.arbitrary_route_basic_section import build_arbitrary_route_basic_model,render_arbitrary_route_basic_section,audit_arbitrary_route_basic_model,preflight_arbitrary_route_render,audit_drafting_specification,audit_contact_terrain_parallelism
from geologic_3d_engine.section.synthetic_event_adapter import build_multiscale_synthetic_erosion_depth

def legend(symbol,name,color):return {"symbol":symbol,"formationAge_ja":"新生代","formationAge_en":"Cenozoic",
 "lithology_ja":name,"lithology_en":name,"title":name,"value":color,"r":int(color[:2],16),"g":int(color[2:4],16),"b":int(color[4:],16)}
def plan():
 rows=[{"stationM":i*100,"longitude":132+i*.001,"latitude":35,"elevationM":100+i*3} for i in range(6)]
 return {"schemaVersion":"PlanEvidenceBundle-1.0","routeLonLat":[[132,35],[132.005,35]],"terrainProfile":rows,
  "layers":[{"evidence_kind":"DEM","source_id":"D","canonical_url":"https://example.test/dem","content_sha256":"a"*64}],
  "surfaceGeology":{"samples":[{"stationM":0,"legend":legend("A","砂","e8d18a")},
    {"stationM":250,"legend":legend("B","泥","9bb7a5")},{"stationM":500,"legend":legend("B","泥","9bb7a5")} ]}}

class ArbitraryBasicSectionTests(unittest.TestCase):
 def test_regional_profile_uses_real_reincision_event_sequence(self):
  profile={"profileId":"TEST-MULTIEVENT","basalTaper":True,
   "eventAuthorization":{"status":"EvidenceBound","requestedLocalizedEventTypes":["IncisedValley"],
    "routeApplicableSubsurfaceSourceIds":["TEST-ROUTE-SOURCE"]},
   "substrateFacies":[["A","砂",12,"#ddc070"],["B","泥",15,"#91a49d"],
     ["C","砂礫",20,"#b58e67"],["D","泥",30,"#7f9091"],["E","表示基底",60,"#716b68"]],
   "fillFacies":[
    {"unitId":"F1","label":"基底礫","meanWeight":.6,"color":"#907152"},
    {"unitId":"F2","label":"初期流路","meanWeight":1.1,"color":"#c6a468"},
    {"unitId":"F3","label":"後期泥","meanWeight":1.4,"color":"#829d99"},
    {"unitId":"F4","label":"上部砂泥","meanWeight":1.0,"color":"#d3bd83"},
    {"unitId":"CAP","label":"表層盛土","meanWeight":.2,"color":"#b69a78"}],
   "surfaceCap":{"unitId":"CAP","thicknessM":2.0}}
  model=build_arbitrary_route_basic_model(plan(),seed=81,regional_profile=profile)
  events=model["syntheticEventArchitecture"]["eventLog"]
  self.assertEqual(sum(v["eventType"]=="Erosion" for v in events),2)
  self.assertEqual(events[3]["eventId"],"SYN-REINCISION-2")
  architecture=model["syntheticEventArchitecture"]["fillArchitecture"]
  self.assertEqual(architecture["stackingPolicy"],"EarlyFill_OffCenterReincision_LateFill")
  self.assertTrue(architecture["multiEventArchitecture"]["enabled"])
  self.assertNotEqual(architecture["multiEventArchitecture"]["channelCenterFraction"],.5)

 def test_multiscale_erosion_depth_has_finite_asymmetric_support(self):
  stations=[i*25.0 for i in range(81)]
  a=build_multiscale_synthetic_erosion_depth(stations,seed=901)
  b=build_multiscale_synthetic_erosion_depth(stations,seed=901)
  self.assertEqual(a,b)
  self.assertEqual(a["audit"]["activeTransitionCount"],2)
  self.assertGreater(a["audit"]["inactiveStationCount"],0)
  self.assertTrue(a["audit"]["asymmetricWidths"])
  self.assertFalse(a["audit"]["terrainInputAccepted"])
  self.assertEqual(a["depthM"][0],0.0);self.assertEqual(a["depthM"][-1],0.0)
 def test_multiscale_erosion_depth_rejects_irregular_stations(self):
  with self.assertRaisesRegex(ValueError,"regular stations"):
   build_multiscale_synthetic_erosion_depth([0,10,25,40,55],seed=1)
 def test_surface_identity_changes_output_but_not_terrain_or_lithology_hash(self):
  a=build_arbitrary_route_basic_model(plan(),seed=7);changed=plan();changed["surfaceGeology"]["samples"][0]["legend"]=legend("C","礫","c09070")
  b=build_arbitrary_route_basic_model(changed,seed=7)
  self.assertEqual(a["terrainModel"]["artifactSha256"],b["terrainModel"]["artifactSha256"])
  self.assertEqual(a["lithologyModel"]["artifactSha256"],b["lithologyModel"]["artifactSha256"])
  self.assertNotEqual(a["mappedSurfaceAtStations"],b["mappedSurfaceAtStations"])
  self.assertFalse(a["realRegionAuthorized"])
 def test_png_and_evidence_synthetic_distinction(self):
  model=build_arbitrary_route_basic_model(plan(),seed=8)
  with tempfile.TemporaryDirectory() as folder:
   image=render_arbitrary_route_basic_section(model,Path(folder)/"section.png")
   self.assertEqual(image.read_bytes()[:8],b"\x89PNG\r\n\x1a\n")
   self.assertEqual(model["surfaceEvidenceRole"],"MappedSurfaceConstraintOnly")
   self.assertIn("Synthetic",model["shallowBodyRole"])
   self.assertGreaterEqual(model["renderAudit"]["renderedLithologyCount"],5)
   self.assertEqual(model["renderAudit"]["subsurfaceVerticalBoundaryCount"],0)
   self.assertEqual(model["renderAudit"]["bottomCoverageFraction"],1.0)
   self.assertTrue(model["renderAudit"]["basementFilledToFrame"])
   self.assertTrue(model["renderAudit"]["eventEngineConnected"])
   self.assertTrue(model["renderAudit"]["nonConformableGeometryPresent"])
   self.assertTrue(model["renderAudit"]["preOutputCompliancePassed"])
   self.assertGreater(model["renderAudit"]["verticalExaggeration"],0)
   self.assertEqual(model["renderAudit"]["legendLayout"],"DynamicFromVisibleLithologyCount")
   self.assertEqual(model["renderAudit"]["lithologyContactDrawOrder"],
                    "Foremost_AfterTerrainAndMappedSurface")
   self.assertTrue(model["renderAudit"]["draftingStandardGatePassed"])
   self.assertTrue(model["renderAudit"]["bilateralElevationTicksRendered"])
   self.assertAlmostEqual(model["renderAudit"]["actualSectionLengthM"],500.0)
   self.assertGreaterEqual(model["renderAudit"]["lithologyBoundaryLineCount"],6)
   self.assertEqual({v["eventType"] for v in model["syntheticEventArchitecture"]["eventLog"]},
                    {"Erosion","StratifiedErosionFill"})
   fill=model["syntheticEventArchitecture"]["fillArchitecture"]
   self.assertEqual(fill["stackingPolicy"],"ErosionSurfaceThenExactPredecessorTop")
   self.assertFalse(fill["universalSequenceClaimed"])
   bodies={v["unitId"]:v for v in model["syntheticEventArchitecture"]["renderBodies"]}
   self.assertEqual(bodies["SYN-VALLEY-MIXED"]["bottomElevationM"],
                    bodies["SYN-VALLEY-BASAL"]["topElevationM"])
   self.assertEqual(bodies["SYN-VALLEY-FINE"]["bottomElevationM"],
                    bodies["SYN-VALLEY-MIXED"]["topElevationM"])
   self.assertEqual(model["syntheticEventArchitecture"]["genericLensPolicy"],
                    "ProhibitedWithoutScopedGeometryEvidence")
   self.assertTrue(model["terrainLithologyIndependenceAudit"]["passed"])
   self.assertFalse(model["terrainLithologyIndependenceAudit"]["singleRealizationPValuesUsed"])
   bodies=model["syntheticEventArchitecture"]["renderBodies"]
   expected_visible=sum(v["unitId"]=="SYN-BASEMENT" or any(v["activeMask"]) for v in bodies)
   self.assertEqual(model["renderAudit"]["renderedLithologyCount"],expected_visible)
   with Image.open(image) as rendered:
    basement=(116,108,102)
    for x in range(140,1701,40):
     self.assertEqual(rendered.convert("RGB").getpixel((x,740)),basement)
 def test_renderer_does_not_bridge_inactive_fill_intervals(self):
  model=build_arbitrary_route_basic_model(plan(),seed=8)
  with tempfile.TemporaryDirectory() as folder:
   render_arbitrary_route_basic_section(model,Path(folder)/"section.png")
   bodies={v["unitId"]:v for v in model["syntheticEventArchitecture"]["renderBodies"]}
   for unit in ("SYN-VALLEY-BASAL","SYN-VALLEY-MIXED","SYN-VALLEY-FINE"):
    active=bodies[unit]["activeMask"]
    transitions=sum(a!=b for a,b in zip(active,active[1:]))
    self.assertLessEqual(transitions,2)
 def test_missing_surface_geology_rejected(self):
  value=plan();value.pop("surfaceGeology")
  with self.assertRaises(ValueError):build_arbitrary_route_basic_model(value,seed=1)
 def test_audit_detects_broken_shared_contact(self):
  model=build_arbitrary_route_basic_model(plan(),seed=2)
  model["composition"]["layersTopDown"][1]["topElevationM"][0]+=1
  result=audit_arbitrary_route_basic_model(model)
  self.assertFalse(result["passed"]);self.assertIn("UnsharedContact:0",result["errors"])
 def test_audit_rejects_bypassing_the_event_engine(self):
  model=build_arbitrary_route_basic_model(plan(),seed=3)
  model.pop("syntheticEventArchitecture")
  result=audit_arbitrary_route_basic_model(model)
  self.assertFalse(result["passed"]);self.assertIn("EventEngineNotConnected",result["errors"])
 def test_preflight_runs_before_output_and_enumerates_boundaries(self):
  model=build_arbitrary_route_basic_model(plan(),seed=4)
  result=preflight_arbitrary_route_render(model,"Show")
  self.assertTrue(result["passed"]);self.assertTrue(result["checkedBeforeOutput"])
  self.assertGreaterEqual(result["lithologyBoundaryLineCount"],6)
  model["syntheticEventArchitecture"]["eventLog"]=[]
  self.assertFalse(preflight_arbitrary_route_render(model,"Show")["passed"])
 def test_drafting_gate_rejects_missing_bilateral_elevation_ticks(self):
  model=build_arbitrary_route_basic_model(plan(),seed=9)
  model["draftingSpecification"]["bilateralElevationTicks"]=False
  audit=preflight_arbitrary_route_render(model,"Show")
  self.assertFalse(audit["passed"])
  self.assertIn("RequiredDrawingFeatureDisabled:bilateralElevationTicks",audit["errors"])
 def test_neighbor_inference_is_preserved_for_drawing_disclosure(self):
  evidence=[{"sourceId":"N1","distanceM":2400,"lithologies":["砂","泥"],
    "geologicalProvince":"BASIN","ageInterval":"Q","environment":"Alluvial",
    "evidenceStatus":"Mapped"}]
  model=build_arbitrary_route_basic_model(plan(),seed=12,neighboring_evidence=evidence)
  self.assertTrue(model["neighborEvidenceInference"]["passed"])
  self.assertIn("周辺地域",model["neighborEvidenceInference"]["drawingDisclosureJa"])
  self.assertFalse(model["neighborEvidenceInference"]["realRegionAuthorized"])
 def test_parallel_terrain_copy_contacts_are_rejected(self):
  model=build_arbitrary_route_basic_model(plan(),seed=15)
  terrain=model["terrainElevationM"]
  for index,body in enumerate(v for v in model["syntheticEventArchitecture"]["renderBodies"]
                              if v["bodyRole"]=="PrimaryBody"):
   body["bottomElevationM"]=[z-10.0*(index+1) for z in terrain]
  result=audit_contact_terrain_parallelism(model)
  self.assertFalse(result["passed"])
  self.assertGreater(result["terrainCopyLikeContactCount"],result["maximumAllowedCopyLikeContacts"])
 def test_incompatible_domain_architecture_is_rejected(self):
  profile={"profileId":"BAD","eventAuthorization":{"status":"None",
   "requestedLocalizedEventTypes":[],"routeApplicableSubsurfaceSourceIds":[]},
   "backgroundArchitecture":{"architectureType":"VolcanicPaleosurfaceStack"}}
  with self.assertRaisesRegex(ValueError,"incompatible with mapped geological domain"):
   build_arbitrary_route_basic_model(plan(),seed=18,regional_profile=profile)
 def test_mapped_sedimentary_domain_selects_prior_without_inventing_valley(self):
  value=plan()
  for row in value["surfaceGeology"]["samples"]:row["legend"]=legend("S","砂岩・泥岩","c8b090")
  model=build_arbitrary_route_basic_model(value,seed=21)
  self.assertEqual(model["planGeologicalDomainClassification"]["geologicalDomain"],"SedimentaryRockTerrain")
  self.assertEqual(model["domainModelSelection"]["selectedArchitecture"],"DeformedSedimentaryStack")
  self.assertEqual({row["eventType"] for row in model["syntheticEventArchitecture"]["eventLog"]},
                   {"RegionalPriorNoLocalizedEvent"})
  self.assertTrue(model["modelAudit"]["passed"])
 def test_mapped_plutonic_domain_uses_weathering_mass_not_beds(self):
  value=plan()
  for row in value["surfaceGeology"]["samples"]:row["legend"]=legend("P","花崗岩","c0b8aa")
  model=build_arbitrary_route_basic_model(value,seed=23)
  self.assertEqual(model["domainModelSelection"]["selectedArchitecture"],"PlutonicWeatheringMass")
  self.assertEqual(model["composition"]["backgroundArchitecture"]["weatheringRepresentation"],
                   "GradedParentRockState_NotStratigraphicBeds")
  self.assertEqual({row["boundaryClass"] for row in preflight_arbitrary_route_render(model,"Show")["boundaries"]},
                   {"WeatheringStateFront"})
  self.assertTrue(model["modelAudit"]["passed"])
