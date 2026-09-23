import hashlib, json, math, unittest
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ADVANCED = Path(__file__).resolve().parents[1]
if str(ADVANCED) not in sys.path: sys.path.insert(0, str(ADVANCED))
ENGINE = ADVANCED.parent
if str(ENGINE) not in sys.path: sys.path.insert(0, str(ENGINE))
from route_request import AdvancedJapanSectionRequest, EARTH_RADIUS_M
from frozen_guard import verify_frozen_basic_v1
from verify_run import (verify_advanced_run, _visual_adjudication_errors,
                        _reopen_report_errors, REQUIRED_VISUAL_LAYOUTS,
                        COMMON_VISUAL_CHECKS)
from domain_profiles import profile_for_domain, broad_profile_for_domain
from nationwide_pipeline import run_advanced_japan_section, _apply_drafting_density, _artifact_record
from advanced_dwg_contract import (_enclosing_ticks, _pinchout_closure_runs,
                                   _lithology_hatch_layer, _audit_unit_area_balance,
                                   _verified_basal_continuation_ids)
from advanced_contact_geometry import (_matern32_sample, apply_advanced_contact_geometry,
                                       audit_advanced_contact_geometry, POLICY_ID,
                                       CONTACT_CLASS_RANGES, audit_contact_range_ensemble,
                                       _contact_class,
                                       audit_plutonic_depth_dependent_parallelism)
from layout_allocator import allocate_a3_landscape_layout, audit_layout_allocation
from lithology_selector import select_evidence_bounded_lithologies, DOMAIN_FACIES
from current_lithology_terminology import (audit_publication_terminology,
                                           normalize_model_added_lithologies,
                                           require_current_publication_terminology,
                                           REQUIRED_FIELDS)
from regional_major_lithology import (MAJOR_LITHOLOGIES,
                                      resolve_major_lithology_evidence,
                                      burial_conditioning_metadata,
                                      audit_effective_lithology_diversity)
from facies_architecture import audit_facies_portrayal, plan_facies_architecture
from advanced_visual_qa import render_disposable_model_preview
from advanced_native_dwg_runner import _core_console_startup
from terrain_morphology import classify_terrain_morphology
from terrain_conditioning import condition_profile_for_terrain
from synthetic_terrain_qa import multiscale_mountain_profile, audit_natural_terrain_texture
from gsi_landform_evidence import class_for_code, _inside_geometry, _tile
from context_inference import infer_natural_domain, context_evidence_from_plan
from advanced_domain_classifier import advanced_legend_domain
from geologic_3d_engine.section.geological_domain_classifier import _domain_for_legend
from geologic_3d_engine.export.contract_integrity import verify_integrity_envelope
from run_terrain_matrix import _case_seed


def distance(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return EARTH_RADIUS_M * 2 * math.asin(min(1, math.sqrt(value)))


class AdvancedRouteTests(unittest.TestCase):
    def test_terrain_matrix_case_seed_is_independent_of_execution_subset(self):
        names = ("plain", "hills", "mountain", "gorge", "piedmont", "coastal", "artificial")
        expected = {name: 880100 + index for index, name in enumerate(names)}
        self.assertEqual({name: _case_seed(name) for name in names}, expected)
        self.assertEqual(_case_seed("piedmont"), 880104)
        with self.assertRaisesRegex(ValueError, "unknown terrain-matrix case"):
            _case_seed("not-a-case")

    def test_plutonic_contacts_are_not_misclassified_as_depositional(self):
        classes = [_contact_class("PlutonicWeatheringMass", index, 8)
                   for index in range(8)]
        self.assertEqual(classes[0], "WeatheringFront")
        self.assertEqual(classes[1:7], ["RockMassStateTransition"] * 6)
        self.assertEqual(classes[7], "ModelCutoff")
        self.assertNotIn("ConformableDepositional", classes)

    def test_plutonic_depth_gate_rejects_deep_translated_copies(self):
        terrain = [10.0, 14.0, 11.0, 16.0, 12.0]
        layers = []
        for index in range(4):
            layers.append({"unitId": f"P{index}",
                           "bottomElevationM": [value - (index + 1) * 2.0 for value in terrain],
                           "bottomContactClass": ("WeatheringFront" if index == 0 else
                                                  "RockMassStateTransition")})
        layers.append({"unitId": "BASE", "bottomElevationM": [0.0] * 5,
                       "bottomContactClass": "ModelCutoff"})
        model = {"terrainElevationM": terrain,
                 "composition": {"layersTopDown": layers},
                 "regionalPriorProfile": {"backgroundArchitecture": {
                     "architectureType": "PlutonicWeatheringMass"}}}
        result = audit_plutonic_depth_dependent_parallelism(model)
        self.assertFalse(result["passed"])
        self.assertTrue(any(code.startswith("PlutonicFrontTooTerrainParallel")
                            for code in result["errors"]))

    def test_contract_rejection_is_persisted_as_typed_refusal(self):
        root = ENGINE.parents[1]
        request = AdvancedJapanSectionRequest(138.0, 36.0, 500.0, 90.0, 10.0,
                                               9321, "Show", True, "Standard")
        def acquisition(_root, route, _spacing, output, _method, _cache):
            rows = [{"stationM":i*100.0, "longitude":route[0][0], "latitude":route[0][1],
                     "elevationM":20.0+i*.4} for i in range(6)]
            legend = {"symbol":"Q-TEST", "title":"terrace deposits",
                      "formationAge_ja":"第四紀", "formationAge_en":"Quaternary",
                      "lithology_ja":"段丘堆積物", "lithology_en":"terrace deposits",
                      "value":"c8ff7a", "r":200, "g":255, "b":122}
            plan = {"schemaVersion":"PlanEvidenceBundle-1.0", "routeLonLat":route,
                    "terrainProfile":rows,
                    "layers":[{"evidence_kind":"DEM", "source_id":"GSI-ELEVATION-TILE",
                               "canonical_url":"https://example.test/dem", "content_sha256":"a"*64}],
                    "surfaceGeology":{"sourceId":"GSJ-SEAMLESS-V2-API", "sourceEdition":"test",
                        "samples":[{"stationM":i*100.0, "legend":legend} for i in range(6)]}}
            Path(output, "plan_evidence_bundle.json").write_text(json.dumps(plan), encoding="utf-8")
        with tempfile.TemporaryDirectory() as folder, \
                patch("nationwide_pipeline.write_advanced_dwg_handoff",
                      side_effect=ValueError("MY-CONTRACT-REJECTION")):
            result = run_advanced_japan_section(
                root, request, folder, acquire_plan=acquisition,
                native_dwg=False)
            self.assertFalse(result["passed"])
            self.assertEqual(result["reason"], "AdvancedDwgContractRejected")
            self.assertIn("MY-CONTRACT-REJECTION", result["errorMessage"])
            refusal = json.loads(Path(result["refusalPath"]).read_text(encoding="utf-8"))
            self.assertFalse(refusal["dwgCreated"])

    def test_coloured_hatch_layer_identifies_sanitized_lithology(self):
        layer = _lithology_hatch_layer(3, '砂岩／泥岩:互層 * 推定')
        self.assertEqual(layer, '30_岩相カラー_03_砂岩_泥岩_互層_推定')
        self.assertNotRegex(layer, r'[<>/\\\";:?*|,=]')

    def test_core_console_startup_detects_vertical_and_language_with_overrides(self):
        with tempfile.TemporaryDirectory() as folder:
            install = Path(folder)
            console = install / "accoreconsole.exe"
            (install / "ja-JP").mkdir(parents=True)
            detected = _core_console_startup(console)
            self.assertEqual(detected[:5],
                             [str(console), "/product", "ACAD", "/l", "ja-JP"])
            self.assertEqual(detected[5:7], ["/isolate", "Geo3DAdvancedV2"])
            self.assertTrue(detected[7].endswith("geo3d_accore_isolate_2027"))
            with patch.dict("os.environ", {
                    "GEO3D_AUTOCAD_PRODUCT":"ACAD",
                    "GEO3D_AUTOCAD_LANGUAGE":"en-US"}):
                overridden = _core_console_startup(console)
            self.assertEqual(overridden[:5],
                             [str(console), "/product", "ACAD", "/l", "en-US"])
            profile = install / "review.arg"
            profile.write_text("profile fixture", encoding="ascii")
            with patch.dict("os.environ", {
                    "GEO3D_AUTOCAD_PROFILE_ARG":str(profile)}):
                profiled = _core_console_startup(console)
            self.assertEqual(profiled[-2:], ["/p", str(profile.resolve())])
            with patch.dict("os.environ", {
                    "GEO3D_AUTOCAD_PROFILE_ARG":str(install / "missing.arg")}):
                with self.assertRaisesRegex(RuntimeError, "existing .arg"):
                    _core_console_startup(console)
            with patch.dict("os.environ", {
                    "GEO3D_AUTOCAD_USE_CURRENT_DEFAULT":"1",
                    "GEO3D_AUTOCAD_PROFILE_ARG":str(install / "missing.arg")}):
                self.assertEqual(_core_console_startup(console),
                                 [str(console), "/product", "ACAD", "/l", "ja-JP"])

    def test_layout_allocator_balances_remaining_drawable_area(self):
        record = allocate_a3_landscape_layout(legend_count=8, auxiliary_legend_count=1)
        self.assertTrue(record["passed"])
        self.assertEqual(record["horizontalImbalanceRatio"], 0.0)
        self.assertEqual(record["verticalImbalanceRatio"], 0.0)
        self.assertEqual(record["legendColumnCount"], 1)
        self.assertGreater(record["legendBlockLeft"], record["viewportRect"]["right"])
        self.assertTrue(audit_layout_allocation(record)["passed"])
        shifted = json.loads(json.dumps(record))
        shifted["viewportRect"]["left"] += 4.0
        self.assertIn("HorizontalLayoutImbalance", audit_layout_allocation(shifted)["errors"])

    def test_evidence_bounded_selector_adds_broad_types_without_local_claim(self):
        original = {"profileId":"TEST", "substrateFacies":[["OLD","old",1,"#000000"]],
                    "englishUnitLabels":{}}
        for domain, rows in DOMAIN_FACIES.items():
            selected = select_evidence_bounded_lithologies(original, domain, {})
            selected_rows = [row for row in rows if row[0] not in {
                r["unitId"] for r in selected["lithologySelection"].get("excludedUnsupportedCandidates", [])}]
            architecture = plan_facies_architecture(domain, selected_rows)
            self.assertTrue(architecture["passed"], architecture)
            self.assertEqual(len(selected["substrateFacies"]), architecture["geometricBodyCount"])
            self.assertEqual(selected["lithologySelection"]["selectedCount"], architecture["geometricBodyCount"])
            self.assertGreaterEqual(selected["lithologySelection"]["candidateLithologyCount"], 8)
            self.assertTrue(all(row["basisType"] == "SyntheticAssumption"
                                and not row["localObservationClaim"]
                                for row in selected["faciesMetadata"]))
            self.assertTrue(all("推定" in row[1] for row in rows))
            self.assertTrue(all(selected["englishUnitLabels"][row[0]].endswith("(inferred)")
                                for row in selected_rows))
            self.assertTrue(selected["terminologyCurrencyAudit"]["passed"])
            self.assertTrue(all(all(field in metadata["terminology"] for field in REQUIRED_FIELDS)
                                for metadata in selected["faciesMetadata"]))
        self.assertEqual(original["substrateFacies"][0][0], "OLD")
        self.assertEqual(len(DOMAIN_FACIES["VolcanicTerrain"]), 17)
        self.assertEqual(len(DOMAIN_FACIES["SedimentaryRockTerrain"]), 15)
        self.assertEqual(len(DOMAIN_FACIES["UnconsolidatedSedimentTerrain"]), 14)

    def test_current_terminology_gate_rejects_legacy_and_time_unit_labels(self):
        original = {"profileId":"TEST", "substrateFacies":[], "englishUnitLabels":{}}
        selected = select_evidence_bounded_lithologies(
            original, "UnconsolidatedSedimentTerrain", {})
        self.assertTrue(selected["terminologyCurrencyAudit"]["passed"])
        labels = [row[1] for row in DOMAIN_FACIES["UnconsolidatedSedimentTerrain"]]
        self.assertFalse(any("旧期" in label or "更新世以前" in label for label in labels))
        self.assertTrue(any("更新統" in label for label in labels))
        forged = json.loads(json.dumps(selected["faciesMetadata"], ensure_ascii=False))
        forged[0]["terminology"]["NormalizedLabelJa"] = "更新世以前の旧期砂礫質堆積物"
        audit = audit_publication_terminology(forged)
        self.assertFalse(audit["passed"])
        with self.assertRaisesRegex(ValueError, "current geological terminology gate rejected"):
            require_current_publication_terminology({"faciesMetadata": forged})

    def test_model_added_valley_fill_is_normalized_and_audited(self):
        model = {
            "faciesMetadata": [],
            "advancedEnglishUnitLabels": {},
            "renderingLithologies": [
                {"unitId":"SYN-VALLEY-BASAL", "label":"礫質谷底堆積物（合成）"},
                {"unitId":"SYN-VALLEY-MIXED", "label":"砂泥質谷埋め堆積物（合成）"},
                {"unitId":"SYN-VALLEY-FINE", "label":"細粒谷埋め堆積物（合成）"},
            ],
        }
        normalize_model_added_lithologies(model)
        self.assertEqual(model["renderingLithologies"][0]["label"],
                         "れき質谷底堆積物（合成）")
        self.assertEqual(len(model["faciesMetadata"]), 3)
        self.assertTrue(require_current_publication_terminology(model)["passed"])
        model["renderingLithologies"][0]["label"] = "礫質谷底堆積物（合成）"
        with self.assertRaisesRegex(ValueError, "current geological terminology gate rejected"):
            require_current_publication_terminology(model)

    def test_major_japanese_lithology_catalog_and_evidence_specialization(self):
        required = {"basalt","andesite","dacite","rhyolite","tuff","welded_tuff",
                    "tuff_breccia","volcanic_breccia","granite","granodiorite",
                    "diorite","gabbro","sandstone","mudstone","siltstone",
                    "conglomerate","limestone","chert","crystalline_schist",
                    "gneiss","hornfels","greenstone","mixed_rock","gravel","sand",
                    "silt","clay","organic_soil","volcanic_ash_soil"}
        self.assertTrue(required.issubset(MAJOR_LITHOLOGIES))
        plan = {"surfaceGeology":{"samples":[
            {"legend":{"lithology_ja":"安山岩溶岩", "lithology_en":"andesite lava"}}
            for _ in range(5)]}}
        evidence = resolve_major_lithology_evidence(plan, "VolcanicTerrain")
        self.assertEqual(evidence["selectedKey"], "andesite")
        selected = select_evidence_bounded_lithologies(
            {"profileId":"VOLC", "substrateFacies":[], "englishUnitLabels":{}},
            "VolcanicTerrain", plan)
        labels = [row[1] for row in selected["substrateFacies"]]
        self.assertTrue(any("安山岩" in label for label in labels))
        self.assertIn("andesite", selected["englishUnitLabels"]["SYN-INTERMEDIATE-LAVA"])
        self.assertFalse(selected["lithologySelection"]["rockTypeSelectedFromDepth"])

    def test_burial_conditioning_does_not_turn_depth_into_hardness_or_rock_type(self):
        rows = [("A","砂（推定）",2.0,"#fff","FineSediment"),
                ("B","粘土（推定）",20.0,"#000","FineSediment")]
        result = burial_conditioning_metadata(rows, "UnconsolidatedSedimentTerrain")
        self.assertEqual(result[0]["conditioningState"], "ShallowUnconsolidatedPrior")
        self.assertEqual(result[1]["conditioningState"], "BurialCompactionTendencyPrior")
        self.assertTrue(all(row["hardnessDerivedFromDepth"] is False and
                            row["numericalCompactionApplied"] is False for row in result))

    def test_plutonic_weathering_states_do_not_fake_lithology_diversity(self):
        evidence = {"rankedCandidates":[{"key":"granite", "count":11}]}
        rows = DOMAIN_FACIES["PlutonicTerrain"]
        audit = audit_effective_lithology_diversity("PlutonicTerrain", evidence, rows)
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["parentLithologyCount"], 1)
        self.assertGreater(audit["weatheringOrStateUnitCount"], 1)
        self.assertFalse(audit["weatheringStatesCountAsDistinctLithologies"])
        self.assertFalse(audit["lithologyDiversityClaimAllowed"])

    def test_smooth_single_mountain_is_rejected_by_local_landform_gate(self):
        stations = [float(value) for value in range(0, 501, 5)]
        smooth = [400.0 + 150.0*math.exp(-((x/500.0-0.5)/0.25)**2)
                  for x in stations]
        audit = audit_natural_terrain_texture(stations, smooth)
        self.assertFalse(audit["passed"])
        self.assertTrue(any(code in audit["errors"] for code in
                            ("TerrainHasTooFewSlopeReversals",
                             "TerrainLacksDrainageScaleRelief",
                             "TerrainLacksDistinctLocalLandforms")))

    def test_layered_section_rejects_one_visually_dominant_lithology(self):
        def rectangle(unit_id, bottom, top):
            return {"unitId":unit_id, "legendGroup":"Geology",
                    "vertices":[[0,bottom],[100,bottom],[100,top],[0,top]]}
        rejected = _audit_unit_area_balance({"polygons":[
            rectangle("THIN",90,100), rectangle("GIANT",0,90)]}, "VolcanicTerrain")
        self.assertFalse(rejected["passed"])
        self.assertEqual(rejected["largestUnitId"], "GIANT")
        self.assertEqual(rejected["errors"], ["SingleLithologyAreaDominanceExceeded"])
        accepted = _audit_unit_area_balance({"polygons":[
            rectangle("A",60,100), rectangle("B",30,60), rectangle("C",0,30)]},
            "VolcanicTerrain")
        self.assertTrue(accepted["passed"], accepted)

    def test_area_balance_excludes_only_declared_basal_drafting_continuation(self):
        def rectangle(unit_id, bottom, top, **extra):
            return {"unitId":unit_id, "legendGroup":"Geology",
                    "vertices":[[0,bottom],[100,bottom],[100,top],[0,top]], **extra}
        contract = {"polygons":[
            rectangle("A",60,100), rectangle("B",30,60), rectangle("C",0,30),
            rectangle("C",-300,0,
                      polygonId="CONTINUATION",
                      materialClassification="SyntheticBasalContinuation") ]}
        modeled = _audit_unit_area_balance(
            contract, "PlutonicTerrain", {"CONTINUATION"})
        framed = _audit_unit_area_balance(
            contract, "PlutonicTerrain", {"CONTINUATION"},
            include_synthetic_basal_continuation=True)
        self.assertTrue(modeled["passed"], modeled)
        self.assertEqual(modeled["auditScope"], "CalculatedGeologicalModelInterval")
        self.assertAlmostEqual(modeled["unitAreaFractions"]["A"], 0.4)
        self.assertGreater(modeled["excludedSyntheticBasalContinuationArea"], 0.0)
        self.assertFalse(framed["passed"], framed)
        self.assertEqual(framed["largestUnitId"], "C")

    def test_forged_continuation_label_does_not_escape_area_gate(self):
        forged = {"polygonId":"FORGED", "unitId":"PLUTON", "legendGroup":"Geology",
                  "materialClassification":"SyntheticBasalContinuation",
                  "vertices":[[0,0],[100,0],[100,95],[0,95]]}
        other = {"polygonId":"OTHER", "unitId":"OTHER", "legendGroup":"Geology",
                 "vertices":[[0,95],[100,95],[100,100],[0,100]]}
        result = _audit_unit_area_balance(
            {"polygons":[forged, other]}, "PlutonicTerrain", {"VERIFIED-ID"})
        self.assertFalse(result["passed"], result)
        self.assertEqual(result["largestUnitId"], "PLUTON")
        self.assertEqual(result["excludedSyntheticBasalContinuationArea"], 0.0)

    def test_continuation_geometry_binding_rejects_spoofed_coordinates(self):
        model = {"stationsM":[0.0, 100.0], "modelDomain":{
            "displayBaseUnitId":"BASE", "lowerBoundaryElevationM":[-10.0, -20.0]}}
        valid = {"polygonId":"ADV2-BASAL-CONTINUATION-0", "unitId":"BASE",
                 "continuationOfUnitId":"BASE", "legendGroup":"Geology",
                 "materialClassification":"SyntheticBasalContinuation",
                 "basisType":"SyntheticAssumption",
                 "displayCategory":"GeologicalPriorContinuation",
                 "vertices":[[0.0,-10.0],[100.0,-20.0],[100.0,-50.0],[0.0,-50.0]]}
        ids = _verified_basal_continuation_ids({"polygons":[valid]}, model, -50.0)
        self.assertEqual(ids, {"ADV2-BASAL-CONTINUATION-0"})
        forged = json.loads(json.dumps(valid))
        forged["vertices"][0][1] = -9.5
        with self.assertRaisesRegex(ValueError, "geometry binding rejected"):
            _verified_basal_continuation_ids({"polygons":[forged]}, model, -50.0)

    def test_true_modeled_dominance_still_fails_at_plutonic_boundary(self):
        def rectangle(unit_id, bottom, top):
            return {"unitId":unit_id, "legendGroup":"Geology",
                    "vertices":[[0,bottom],[100,bottom],[100,top],[0,top]]}
        boundary = _audit_unit_area_balance({"polygons":[
            rectangle("PLUTON",28,100), rectangle("OTHER",0,28)]}, "PlutonicTerrain")
        over = _audit_unit_area_balance({"polygons":[
            rectangle("PLUTON",27.999,100), rectangle("OTHER",0,27.999)]}, "PlutonicTerrain")
        self.assertTrue(boundary["passed"], boundary)
        self.assertFalse(over["passed"], over)

    def test_multiscale_mountain_fixture_is_not_an_analytic_two_hill_profile(self):
        stations = [float(value) for value in range(0, 501, 5)]
        first = multiscale_mountain_profile(stations, seed=101)
        second = multiscale_mountain_profile(stations, seed=101)
        changed = multiscale_mountain_profile(stations, seed=102)
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)
        audit = audit_natural_terrain_texture(stations, first)
        self.assertTrue(audit["passed"], audit)
        smooth = [420.0 + 150.0*math.exp(-((x/500.0-.38)/.19)**2) for x in stations]
        smooth_errors = audit_natural_terrain_texture(stations, smooth)["errors"]
        self.assertTrue({"TerrainIsExcessivelySmooth", "TerrainHasTooFewSlopeReversals"}
                        & set(smooth_errors))

    def test_complex_domains_do_not_turn_composition_parts_into_layer_cake(self):
        for domain in ("AccretionaryComplex", "MetamorphicBelt"):
            selected = select_evidence_bounded_lithologies({"englishUnitLabels": {}}, domain, {})
            architecture = selected["faciesArchitecture"]
            self.assertGreater(architecture["compositionPartCount"], 0)
            self.assertFalse(architecture["localizedGeometryInvented"])
            geometric_ids = {row[0] for row in selected["substrateFacies"]}
            for part in architecture["compositionParts"]:
                self.assertNotIn(part["unitId"], geometric_ids)
                self.assertFalse(part["geometryAuthorized"])

    def test_portrayal_audit_rejects_unlocated_part_rendered_as_body(self):
        model = {"faciesArchitecture": {"candidateLithologyCount": 2,
            "geometricBodyCount": 1, "compositionParts": [
                {"unitId":"BLOCK", "geometryAuthorized":False}]},
            "syntheticEventArchitecture": {"renderBodies": [{"unitId":"MATRIX"}]}}
        self.assertTrue(audit_facies_portrayal(model)["passed"])
        model["syntheticEventArchitecture"]["renderBodies"].append({"unitId":"BLOCK"})
        audit = audit_facies_portrayal(model)
        self.assertFalse(audit["passed"])
        self.assertEqual(audit["unauthorizedRenderedPartCount"], 1)

    def test_contact_range_multiseed_audit_distinguishes_classes(self):
        audit = audit_contact_range_ensemble([i * 10.0 for i in range(51)], seed_count=24)
        self.assertTrue(audit["passed"], audit)
        self.assertGreater(
            audit["results"]["ConformableDepositional"]["empiricalMeanCorrelation"],
            audit["results"]["WeatheringFront"]["empiricalMeanCorrelation"] + 0.04)

    def test_advanced_pinchout_closure_includes_zero_thickness_apices(self):
        self.assertEqual(list(_pinchout_closure_runs([False, True, True, False])), [(0, 4)])
        self.assertEqual(list(_pinchout_closure_runs([True, True, False, False])), [(0, 3)])
        self.assertEqual(list(_pinchout_closure_runs([False, False, True, True])), [(1, 4)])
        self.assertEqual(list(_pinchout_closure_runs([False, True, False])), [(0, 3)])

    def test_terrain_morphology_distinguishes_representative_shapes(self):
        stations = [float(value) for value in range(0, 501, 50)]
        plain = classify_terrain_morphology(stations, [10,10.2,10.1,10.3,10.2,10.1,10.2,10.3,10.1,10.2,10])
        mountain = classify_terrain_morphology(stations, [0,30,75,130,190,240,205,150,95,40,5])
        valley = classify_terrain_morphology(stations, [100,98,90,65,30,5,25,60,88,97,101])
        self.assertEqual(plain["primaryClass"], "BroadLowland")
        self.assertEqual(mountain["primaryClass"], "MountainousRelief")
        self.assertEqual(valley["primaryClass"], "NarrowValleyOrGorge")
        self.assertFalse(valley["terrainDeterminesSubsurface"])
        self.assertEqual(valley["localizedEventAuthorization"], [])

    def test_artificial_and_coastal_classes_require_typed_evidence(self):
        stations = [0.0, 100.0, 200.0, 300.0]
        heights = [3.0, 3.1, 3.0, 3.1]
        shape_only = classify_terrain_morphology(stations, heights)
        artificial = classify_terrain_morphology(
            stations, heights, landform_evidence=[{"label":"盛土・埋立地"}])
        coastal = classify_terrain_morphology(
            stations, heights, landform_evidence=[{"class":"coastal lowland"}])
        self.assertEqual(shape_only["primaryClass"], "BroadLowland")
        self.assertEqual(artificial["primaryClass"], "ArtificiallyModifiedOrUnresolved")
        self.assertEqual(coastal["primaryClass"], "CoastalLowland")
        self.assertEqual(artificial["confidenceClass"], "EvidenceSupported")

    def test_minor_landform_evidence_does_not_override_route_majority(self):
        stations = [0.0,100.0,200.0,300.0]
        heights = [2.0,2.1,2.0,2.1]
        evidence = [{"stationM":0,"class":"ArtificiallyModifiedOrUnresolved"},
                    {"stationM":100,"class":"BroadLowland"},
                    {"stationM":200,"class":"BroadLowland"},
                    {"stationM":300,"class":"BroadLowland"}]
        result = classify_terrain_morphology(stations, heights, landform_evidence=evidence)
        self.assertEqual(result["primaryClass"], "BroadLowland")
        self.assertEqual(result["confidenceClass"], "EvidenceSupported")

    def test_terrain_morphology_rejects_invalid_profiles(self):
        with self.assertRaises(ValueError):
            classify_terrain_morphology([0, 1], [2, 3])
        with self.assertRaises(ValueError):
            classify_terrain_morphology([0, 2, 1], [2, 3, 4])
        with self.assertRaises(ValueError):
            classify_terrain_morphology([0, 1, 2], [2, float("nan"), 4])

    def test_terrain_conditioning_changes_texture_not_geological_content(self):
        source = profile_for_domain("UnconsolidatedSedimentTerrain")
        mountain = condition_profile_for_terrain(
            source, {"primaryClass":"MountainousRelief", "confidenceClass":"ShapeSupported"}, 500)
        plain = condition_profile_for_terrain(
            source, {"primaryClass":"BroadLowland", "confidenceClass":"ShapeSupported"}, 500)
        self.assertLess(mountain["backgroundArchitecture"]["defaultCorrelationRangeM"],
                        plain["backgroundArchitecture"]["defaultCorrelationRangeM"])
        self.assertEqual(mountain["substrateFacies"], plain["substrateFacies"])
        self.assertEqual(mountain["eventAuthorization"], plain["eventAuthorization"])
        self.assertEqual(mountain["terrainConditioning"]["localizedEventAuthorization"], [])
        self.assertFalse(mountain["terrainConditioning"]["terrainDeterminesUnitSequence"])
        self.assertEqual(source["backgroundArchitecture"]["defaultCorrelationRangeM"], 180.0)

    def test_gsi_landform_code_mapping_and_polygon_membership(self):
        self.assertEqual(class_for_code(10101), "MountainousRelief")
        self.assertEqual(class_for_code("10702"), "CoastalLowland")
        self.assertEqual(class_for_code(11007), "ArtificiallyModifiedOrUnresolved")
        self.assertEqual(class_for_code("bad"), "Unresolved")
        polygon = {"type":"Polygon", "coordinates":[
            [[139,35],[140,35],[140,36],[139,36],[139,35]],
            [[139.4,35.4],[139.6,35.4],[139.6,35.6],[139.4,35.6],[139.4,35.4]]]}
        self.assertTrue(_inside_geometry(139.2,35.2,polygon))
        self.assertFalse(_inside_geometry(139.5,35.5,polygon))
        self.assertFalse(_inside_geometry(141,35.5,polygon))
        x, y = _tile(139.75, 35.68)
        self.assertGreater(x, 0); self.assertGreater(y, 0)

    def test_matern32_contact_field_is_deterministic_and_not_terrain_driven(self):
        stations = [0.0, 17.0, 53.0, 104.0, 181.0, 279.0, 401.0, 500.0]
        first = _matern32_sample(stations, seed=9713, range_m=91.0)
        second = _matern32_sample(stations, seed=9713, range_m=91.0)
        changed = _matern32_sample(stations, seed=9714, range_m=91.0)
        self.assertEqual(first.tolist(), second.tolist())
        self.assertNotEqual(first.tolist(), changed.tolist())
        self.assertAlmostEqual(float(first.mean()), 0.0, places=12)
        self.assertAlmostEqual(float(first.std()), 1.0, places=12)

    def test_advanced_contact_geometry_closes_explicit_lower_model_limit(self):
        stations = [float(v) for v in range(0, 501, 50)]
        terrain = [20.0 + 0.002 * v for v in stations]
        unit_ids = ["COVER", "A", "B", "DISPLAY-BASE"]
        means = [2.0, 8.0, 13.0, 50.0]
        layers = []
        bodies = []
        top = terrain[:]
        for unit, mean in zip(unit_ids, means):
            bottom = [value - mean for value in top]
            common = {"unitId": unit, "topElevationM": top, "bottomElevationM": bottom,
                      "thicknessM": [mean] * len(stations), "activeMask": [True] * len(stations),
                      "allowPinchout": False}
            layers.append(dict(common))
            bodies.append({**common, "bodyRole": "PrimaryBody"})
            top = bottom
        model = {"seed": 44, "stationsM": stations, "terrainElevationM": terrain,
                 "draftingSpecification": {"verticalTickM": 25.0},
                 "composition": {"layersTopDown": layers},
                 "syntheticEventArchitecture": {
                     "architectureMode": "ConservativeRegionalPrior_NoLocalizedEvents",
                     "renderBodies": bodies}}
        apply_advanced_contact_geometry(model)
        audit = audit_advanced_contact_geometry(model)
        self.assertTrue(audit["passed"], audit)
        self.assertEqual(audit["findings"][0]["contactClass"], "WeatheringFront")
        self.assertEqual(model["advancedContactGeometry"]["policyId"], POLICY_ID)
        lower = model["modelDomain"]["lowerBoundaryElevationM"]
        self.assertEqual(lower,
                         model["composition"]["layersTopDown"][-1]["bottomElevationM"])
        self.assertGreater(len(set(round(v, 8) for v in lower)), 1)
        self.assertEqual(model["composition"]["layersTopDown"][0]["bottomContactClass"],
                         "WeatheringFront")
        self.assertEqual(model["composition"]["layersTopDown"][1]["bottomContactClass"],
                         "ConformableDepositional")
        self.assertEqual(model["composition"]["layersTopDown"][-1]["bottomContactClass"],
                         "ModelCutoff")
        self.assertEqual(model["composition"]["layersTopDown"][1]["bottomContactRange"]["longFraction"],
                         CONTACT_CLASS_RANGES["ConformableDepositional"]["longFraction"])
        for upper, lower_layer in zip(model["composition"]["layersTopDown"],
                                      model["composition"]["layersTopDown"][1:]):
            self.assertEqual(upper["bottomElevationM"], lower_layer["topElevationM"])

    def test_mountain_contact_mode_truncates_independent_surfaces_without_gaps(self):
        stations = [float(v) for v in range(0, 501, 25)]
        terrain = [400.0 + 130.0*math.exp(-((v-210.0)/105.0)**2) for v in stations]
        layers=[]; bodies=[]; top=terrain[:]
        for unit, mean in (("COVER",2.0),("A",12.0),("B",18.0),("BASE",60.0)):
            bottom=[value-mean for value in top]
            common={"unitId":unit,"topElevationM":top,"bottomElevationM":bottom,
                    "thicknessM":[mean]*len(top),"activeMask":[True]*len(top),
                    "allowPinchout":False}
            layers.append(dict(common));bodies.append({**common,"bodyRole":"PrimaryBody"});top=bottom
        model={"seed":812,"stationsM":stations,"terrainElevationM":terrain,
               "regionalPriorProfile":{"backgroundArchitecture":{"architectureType":"DeformedSedimentaryStack",
                    "regionalDipDegrees":4.0,"defaultLogStd":0.5},
                    "terrainConditioning":{"terrainClass":"MountainousRelief"}},
               "draftingSpecification":{"verticalTickM":25.0},
               "composition":{"layersTopDown":layers},
               "syntheticEventArchitecture":{"architectureMode":"ConservativeRegionalPrior_NoLocalizedEvents",
                                                "renderBodies":bodies}}
        apply_advanced_contact_geometry(model)
        self.assertEqual(model["advancedContactGeometry"]["geometryMode"],
                         "ErosionalTruncationOfIndependentStructuralContacts")
        rebuilt=model["composition"]["layersTopDown"]
        self.assertTrue(any(not all(row["activeMask"]) for row in rebuilt[1:-1]))
        for upper, lower in zip(rebuilt,rebuilt[1:]):
            self.assertEqual(upper["bottomElevationM"],lower["topElevationM"])
        self.assertTrue(audit_advanced_contact_geometry(model)["passed"])

    def test_volcanic_mountain_keeps_thin_cover_out_of_relief_absorption(self):
        stations = [float(v) for v in range(0, 501, 25)]
        terrain = [400.0 + 150.0*math.exp(-((v-210.0)/90.0)**2) for v in stations]
        layers=[]; bodies=[]; top=terrain[:]
        for unit, mean in (("COVER",2.0),("TEPHRA",5.0),("EDIFICE",20.0),("BASE",70.0)):
            bottom=[value-mean for value in top]
            common={"unitId":unit,"topElevationM":top,"bottomElevationM":bottom,
                    "thicknessM":[mean]*len(top),"activeMask":[True]*len(top),
                    "allowPinchout":False}
            layers.append(dict(common));bodies.append({**common,"bodyRole":"PrimaryBody"});top=bottom
        model={"seed":913,"stationsM":stations,"terrainElevationM":terrain,
               "lithologySelection":{"domain":"VolcanicTerrain"},
               "regionalPriorProfile":{"backgroundArchitecture":{"architectureType":"VolcanicPaleosurfaceStack",
                    "regionalDipDegrees":2.0,"defaultLogStd":0.3},
                    "terrainConditioning":{"terrainClass":"MountainousRelief"}},
               "composition":{"layersTopDown":layers},
               "syntheticEventArchitecture":{"architectureMode":"ConservativeRegionalPrior_NoLocalizedEvents",
                                                "renderBodies":bodies}}
        apply_advanced_contact_geometry(model)
        rebuilt=model["composition"]["layersTopDown"]
        self.assertEqual(model["advancedContactGeometry"]["protectedTerrainFollowingCoverCount"],2)
        self.assertLessEqual(max(rebuilt[1]["thicknessM"]),12.0)
        self.assertTrue(any(not flag for flag in rebuilt[2]["activeMask"]))
        self.assertTrue(audit_advanced_contact_geometry(model)["passed"])

    def test_artificial_benches_do_not_propagate_through_subsurface_stack(self):
        stations = [float(v) for v in range(0, 501, 25)]
        terrain = [50.0 if v < 175 else 42.0 if v < 350 else 46.0 for v in stations]
        layers=[]; bodies=[]; top=terrain[:]
        for unit, mean in (("COVER",2.0),("A",12.0),("B",18.0),("BASE",70.0)):
            bottom=[value-mean for value in top]
            common={"unitId":unit,"topElevationM":top,"bottomElevationM":bottom,
                    "thicknessM":[mean]*len(top),"activeMask":[True]*len(top),"allowPinchout":False}
            layers.append(dict(common));bodies.append({**common,"bodyRole":"PrimaryBody"});top=bottom
        model={"seed":1002,"stationsM":stations,"terrainElevationM":terrain,
               "lithologySelection":{"domain":"SedimentaryRockTerrain"},
               "regionalPriorProfile":{"backgroundArchitecture":{"architectureType":"DeformedSedimentaryStack",
                    "regionalDipDegrees":1.0,"defaultLogStd":0.3},
                    "terrainConditioning":{"terrainClass":"ArtificiallyModifiedOrUnresolved"}},
               "composition":{"layersTopDown":layers},
               "syntheticEventArchitecture":{"architectureMode":"ConservativeRegionalPrior_NoLocalizedEvents",
                                                "renderBodies":bodies}}
        apply_advanced_contact_geometry(model)
        first_subsurface=model["composition"]["layersTopDown"][1]["bottomElevationM"]
        terrain_step_indexes=[i for i in range(1,len(terrain)) if terrain[i] != terrain[i-1]]
        self.assertTrue(terrain_step_indexes)
        self.assertTrue(all(abs((first_subsurface[i]-first_subsurface[i-1]) -
                                (terrain[i]-terrain[i-1])) > 1e-6
                            for i in terrain_step_indexes))
        self.assertTrue(audit_advanced_contact_geometry(model)["passed"])

    def test_contact_geometry_rejects_localized_event_scope(self):
        with self.assertRaises(ValueError):
            apply_advanced_contact_geometry({
                "syntheticEventArchitecture": {"architectureMode": "LocalizedEvents"}})

    def test_exact_500m_route_at_arbitrary_azimuth(self):
        request = AdvancedJapanSectionRequest(137.2, 36.4, 500.0, 37.0, 10.0, 9182)
        route = request.route()
        self.assertAlmostEqual(distance(*route), 500.0, places=6)

    def test_seeded_contract_and_bounds(self):
        self.assertEqual(AdvancedJapanSectionRequest(130, 33, seed=99).to_dict()["seed"], 99)
        with self.assertRaises(ValueError): AdvancedJapanSectionRequest(0, 0).validate()
        with self.assertRaises(ValueError): AdvancedJapanSectionRequest(135, 35, azimuth_degrees=360).validate()
        with self.assertRaises(ValueError): AdvancedJapanSectionRequest(135, 35, drafting_density="Extreme").validate()

    def test_basic_v1_is_still_frozen(self):
        root = Path(__file__).resolve().parents[4]
        result = verify_frozen_basic_v1(root)
        self.assertTrue(result["passed"], result["mismatches"])

    def test_run_verifier_rejects_unsafe_claim(self):
        root = Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "run_manifest.json").write_text(json.dumps({
                "schemaVersion":"AdvancedJapanSectionRun-2.0", "decision":"Accepted",
                "realRegionAuthorized":True, "request":{}, "artifacts":[]}), encoding="utf-8")
            result = verify_advanced_run(root, path)
            self.assertFalse(result["passed"])
            self.assertIn("UnsafeAuthorizationClaim", result["errors"])

    def test_run_verifier_requires_source_reuse_boundary_in_2_1(self):
        root = Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "run_manifest.json").write_text(json.dumps({
                "schemaVersion":"AdvancedJapanSectionRun-2.1", "decision":"Experimental",
                "realRegionAuthorized":False, "request":{}, "artifacts":[]}), encoding="utf-8")
            result = verify_advanced_run(root, path)
            self.assertIn("SourceReuseBoundaryIncomplete", result["errors"])

    def test_run_verifier_accepts_safe_typed_refusal(self):
        root = Path(__file__).resolve().parents[4]
        request = AdvancedJapanSectionRequest(140.0, 35.5, length_m=500, seed=9)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "typed_refusal.json").write_text(json.dumps({
                "schemaVersion":"AdvancedJapanSectionRefusal-2.0", "passed":False,
                "reason":"UnderlyingNaturalDomainUnavailable", "request":request.to_dict(),
                "dwgCreated":False, "fabricatedFallbackUsed":False}), encoding="utf-8")
            result = verify_advanced_run(root, path)
            self.assertTrue(result["passed"], result["errors"])
            self.assertEqual(result["outcome"], "TypedRefusal")

    def test_unconsolidated_profile_is_conservative_and_isolated(self):
        first = profile_for_domain("UnconsolidatedSedimentTerrain")
        second = profile_for_domain("UnconsolidatedSedimentTerrain")
        self.assertEqual(len(first["substrateFacies"]), 6)
        self.assertEqual(first["eventAuthorization"]["requestedLocalizedEventTypes"], [])
        self.assertEqual(first["basisType"], "SyntheticAssumption")
        first["substrateFacies"][0][1] = "mutated"
        self.assertNotEqual(first, second)
        self.assertIsNone(profile_for_domain("MixedOrAmbiguous"))

    def test_broad_profiles_cover_non_lowland_domains_without_local_events(self):
        selected = {"architectureType":"VolcanicPaleosurfaceStack",
                    "facies":[["A", "火山岩類（推定）", 10.0, "#777777"]]}
        result = broad_profile_for_domain("VolcanicTerrain", selected)
        self.assertEqual(result["substrateFacies"], selected["facies"])
        self.assertEqual(result["environment"], "MappedDomainBroadPrior")
        self.assertEqual(result["eventAuthorization"]["requestedLocalizedEventTypes"], [])
        self.assertNotIn("contextInference", result)

    def test_acquisition_failure_becomes_typed_refusal(self):
        root = Path(__file__).resolve().parents[4]
        def failed(*_args): raise ValueError("no valid DEM samples")
        with tempfile.TemporaryDirectory() as folder:
            result = run_advanced_japan_section(root,
                AdvancedJapanSectionRequest(140.0, 35.5, seed=8), folder,
                acquire_plan=failed, native_dwg=False)
            self.assertEqual(result["reason"], "PlanEvidenceAcquisitionFailed")
            self.assertEqual(result["errorType"], "ValueError")
            self.assertFalse(result["fabricatedFallbackUsed"])
            self.assertTrue(Path(result["refusalPath"]).is_file())

    def test_offline_full_pipeline_to_integrity_bound_contract(self):
        root = Path(__file__).resolve().parents[4]
        def acquisition(_root, route, _spacing, output, _method, _cache):
            rows = [{"stationM":i*100.0, "longitude":route[0][0], "latitude":route[0][1],
                     "elevationM":20.0+i*.4} for i in range(6)]
            legend = {"symbol":"Q-TEST", "title":"terrace deposits",
                      "formationAge_ja":"第四紀", "formationAge_en":"Quaternary",
                      "lithology_ja":"段丘堆積物", "lithology_en":"terrace deposits",
                      "value":"c8ff7a", "r":200, "g":255, "b":122}
            plan = {"schemaVersion":"PlanEvidenceBundle-1.0", "routeLonLat":route,
                    "terrainProfile":rows,
                    "layers":[{"evidence_kind":"DEM", "source_id":"GSI-ELEVATION-TILE",
                               "canonical_url":"https://example.test/dem", "content_sha256":"a"*64}],
                    "surfaceGeology":{"sourceId":"GSJ-SEAMLESS-V2-API", "sourceEdition":"test",
                        "samples":[{"stationM":i*100.0, "legend":legend} for i in range(6)]}}
            Path(output, "plan_evidence_bundle.json").write_text(json.dumps(plan), encoding="utf-8")
        with tempfile.TemporaryDirectory() as folder:
            with patch("nationwide_pipeline.apply_advanced_contact_geometry",
                       wraps=apply_advanced_contact_geometry) as production_spy:
                result = run_advanced_japan_section(root,
                    AdvancedJapanSectionRequest(139.5,36.1,500,90,10,321,"Hide",False,"Detailed"),
                    folder, acquire_plan=acquisition, native_dwg=False)
            self.assertEqual(production_spy.call_count, 1)
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["schemaVersion"], "AdvancedJapanSectionRun-2.1")
            self.assertEqual(result["domainClassification"]["geologicalDomain"],
                             "UnconsolidatedSedimentTerrain")
            self.assertEqual(result["pngRole"], "RetainedAuditEvidence")
            contract_path = next(Path(row["path"]) for row in result["artifacts"]
                                 if row["path"].endswith("native_dwg_contract_envelope.json"))
            envelope = json.loads(contract_path.read_text(encoding="utf-8"))["geologicContractEnvelope"]
            payload, _validation = verify_integrity_envelope(envelope)
            self.assertEqual(payload["contactLines"], [])
            self.assertFalse(payload["validation"]["contactLineForemost"])
            self.assertEqual(payload["drafting"]["modelLowerLimitClass"],
                             "VariableSyntheticModelBoundary")
            self.assertEqual(payload["drafting"]["belowModelLimitStatus"], "SyntheticBasalContinuation")
            self.assertEqual(min(payload["drafting"]["elevationTicksM"]),
                             payload["drafting"]["drawingFrameLowerM"])
            unknown = [row for row in payload["polygons"]
                       if row.get("materialClassification") == "SyntheticBasalContinuation"]
            self.assertEqual(len(unknown), 1)
            self.assertTrue(unknown[0]["geologicalInterpretation"])
            self.assertEqual(unknown[0]["basisType"], "SyntheticAssumption")
            self.assertEqual(unknown[0]["continuationOfUnitId"], unknown[0]["unitId"])
            self.assertEqual(unknown[0]["legendGroup"], "Geology")
            self.assertEqual(unknown[0]["displayCategory"], "GeologicalPriorContinuation")
            self.assertTrue(payload["drafting"]["layoutAllocation"]["passed"])
            self.assertEqual(payload["validation"]["basalContinuationPolygonCount"], 1)
            self.assertTrue(all(row["displayName"].replace(" ", "_") in row["hatchLayer"]
                                for row in payload["polygons"]))
            stations = payload["terrainLine"]["vertices"]
            count = len(stations)
            self.assertEqual(unknown[0]["vertices"][:count], [
                [float(x), float(y)] for (x, _), y in zip(
                    stations, payload["drafting"]["modelLowerBoundaryElevationM"])
            ])
            self.assertTrue(all(
                float(vertex[1]) == payload["drafting"]["drawingFrameLowerM"]
                for vertex in unknown[0]["vertices"][count:]
            ))
            self.assertTrue(all(row["displayNameEn"] for row in payload["polygons"]))
            checked = verify_advanced_run(root, Path(result["manifestPath"]).parent)
            self.assertTrue(checked["passed"], checked["errors"])

    def test_context_inference_excludes_artificial_surface(self):
        result = infer_natural_domain({"sampleEvidence":[
            {"classifiedDomain":"ArtificiallyModifiedTerrain","weightM":40},
            {"classifiedDomain":"UnconsolidatedSedimentTerrain","weightM":45},
            {"classifiedDomain":"SedimentaryRockTerrain","weightM":15}]})
        self.assertTrue(result["passed"])
        self.assertEqual(result["inferredNaturalDomain"], "UnconsolidatedSedimentTerrain")
        self.assertAlmostEqual(result["naturalDominance"], .75)
        rejected = infer_natural_domain({"sampleEvidence":[
            {"classifiedDomain":"ArtificiallyModifiedTerrain","weightM":90},
            {"classifiedDomain":"UnconsolidatedSedimentTerrain","weightM":10}]})
        self.assertFalse(rejected["passed"])

    def test_context_classification_does_not_need_dem_elevation(self):
        plan = {"terrainProfile":[{"stationM":0,"elevationM":None},
                                  {"stationM":100,"elevationM":None}],
                "surfaceGeology":{"samples":[
                    {"stationM":0,"legend":{"kind":"natural"}},
                    {"stationM":100,"legend":None}]}}
        evidence = context_evidence_from_plan(
            plan, lambda legend: "UnconsolidatedSedimentTerrain")
        self.assertEqual(evidence["routeLengthM"], 100)
        self.assertFalse(evidence["terrainElevationUsedForInference"])
        self.assertEqual(evidence["sampleEvidence"][1]["classifiedDomain"], "Unresolved")

    def test_advanced_vocabulary_classifies_terrace_deposits(self):
        frozen = lambda _legend: "Unresolved"
        self.assertEqual(advanced_legend_domain({"lithology_en":"terrace deposits"}, frozen),
                         "UnconsolidatedSedimentTerrain")
        self.assertEqual(advanced_legend_domain({"lithology_en":"unknown unit"}, frozen), "Unresolved")
        self.assertEqual(advanced_legend_domain({"formationAge_en":"Quaternary Late Pleistocene",
                         "lithology_en":"brackish sediments or marine sediments"}, frozen),
                         "UnconsolidatedSedimentTerrain")
        self.assertEqual(advanced_legend_domain({"formationAge_en":"Cretaceous",
                         "lithology_en":"marine sediments"}, frozen), "Unresolved")
        self.assertEqual(advanced_legend_domain({"formationAge_en":"Quaternary",
                         "lithology_en":"fan, talus or glacial deposits"}, frozen),
                         "UnconsolidatedSedimentTerrain")

    def test_nationwide_broad_domain_vocabulary_matrix(self):
        cases = {"andesite lava":"VolcanicTerrain", "granite":"PlutonicTerrain",
                 "schist":"MetamorphicBelt", "accretionary chert":"AccretionaryComplex",
                 "sandstone and mudstone":"SedimentaryRockTerrain",
                 "terrace deposits":"UnconsolidatedSedimentTerrain"}
        for label, expected in cases.items():
            with self.subTest(label=label):
                self.assertEqual(advanced_legend_domain({"lithology_en":label}, _domain_for_legend), expected)

    def test_drafting_density_changes_both_axes_together(self):
        compact = {"draftingSpecification":{"horizontalTickM":100.0,"verticalTickM":25.0}}
        detailed = {"draftingSpecification":{"horizontalTickM":100.0,"verticalTickM":25.0}}
        _apply_drafting_density(compact, "Compact")
        _apply_drafting_density(detailed, "Detailed")
        self.assertEqual((compact["draftingSpecification"]["horizontalTickM"],
                          compact["draftingSpecification"]["verticalTickM"]), (200.0, 50.0))
        self.assertEqual((detailed["draftingSpecification"]["horizontalTickM"],
                          detailed["draftingSpecification"]["verticalTickM"]), (50.0, 12.5))

    def test_enclosing_ticks_include_float_endpoint_and_geometry_extents(self):
        self.assertEqual(_enclosing_ticks(0.0, 499.999999999629, 100.0),
                         [0.0, 100.0, 200.0, 300.0, 400.0, 500.0])
        self.assertEqual(_enclosing_ticks(0.0, 500.00000000001, 100.0),
                         [0.0, 100.0, 200.0, 300.0, 400.0, 500.0])
        self.assertEqual(_enclosing_ticks(-107.73, 17.19, 25.0),
                         [-125.0, -100.0, -75.0, -50.0, -25.0, 0.0, 25.0])

    def test_enclosing_ticks_do_not_hide_real_overrun(self):
        self.assertEqual(_enclosing_ticks(0.0, 500.001, 100.0)[-1], 600.0)
        self.assertEqual(_enclosing_ticks(-100.001, 0.0, 25.0)[0], -125.0)
        with self.assertRaises(ValueError):
            _enclosing_ticks(1.0, 0.0, 10.0)
        with self.assertRaises(ValueError):
            _enclosing_ticks(0.0, 1.0, 0.0)

    def test_artifact_record_has_portable_project_path(self):
        root = Path(__file__).resolve().parents[4]
        record = _artifact_record(root, root / "subprojects/geologic_3d_engine/advanced_v2/README.md")
        self.assertEqual(record["projectRelativePath"],
                         "subprojects/geologic_3d_engine/advanced_v2/README.md")
        self.assertEqual(len(record["sha256"]), 64)

    def test_visual_rejection_supersedes_structural_success(self):
        root = Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "run_manifest.json").write_text(json.dumps({
                "schemaVersion":"AdvancedJapanSectionRun-2.1", "decision":"Experimental",
                "realRegionAuthorized":False, "request":{}, "artifacts":[],
                "sourceReuseBoundary":[]}), encoding="utf-8")
            (path / "post_generation_visual_adjudication.json").write_text(json.dumps({
                "decision":"Rejected", "defects":["Mojibake"]}), encoding="utf-8")
            result = verify_advanced_run(root, path)
            self.assertIn("PostGenerationVisualReviewRejected", result["errors"])

    def test_native_release_requires_explicit_visual_adjudication(self):
        root = Path(__file__).resolve().parents[4]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "run_manifest.json").write_text(json.dumps({
                "schemaVersion":"AdvancedJapanSectionRun-2.1", "decision":"Experimental",
                "realRegionAuthorized":False, "request":{}, "artifacts":[],
                "sourceReuseBoundary":[], "primaryArtifact":"NativeDwg"}), encoding="utf-8")
            result = verify_advanced_run(root, path)
            self.assertIn("PostGenerationVisualReviewMissing", result["errors"])

    def test_visual_acceptance_requires_hash_bound_per_layout_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            dwg = Path(folder, "candidate.dwg")
            dwg.write_bytes(b"AC1032" + b"candidate")
            shallow = {"decision":"Accepted"}
            self.assertIn("VisualAdjudicationSchemaInvalid",
                          _visual_adjudication_errors(shallow, dwg))
            checks = {key:True for key in COMMON_VISUAL_CHECKS}
            layouts = {name:dict(checks) for name in REQUIRED_VISUAL_LAYOUTS}
            layouts["GEO_MONOCHROME_QA"]["monochromeEffective"] = True
            layouts["GEO_TOPOLOGY_QA"]["hatchesHidden"] = True
            complete = {
                "schemaVersion":"AdvancedV2PostGenerationVisualAdjudication-1.0",
                "decision":"Accepted", "plotOutputReviewed":True,
                "reviewedDwgSha256":hashlib.sha256(dwg.read_bytes()).hexdigest(),
                "layouts":layouts,
            }
            self.assertEqual(_visual_adjudication_errors(complete, dwg), [])
            complete["layouts"]["GEO_JP"]["noMojibake"] = False
            self.assertIn("VisualLayoutCheckFailed:GEO_JP",
                          _visual_adjudication_errors(complete, dwg))

    def test_reopen_report_requires_enabled_locked_viewport_per_layout(self):
        entries = "|".join(
            f"{name}:N=2,ON=True,LOCKED=True,VC=(250,-50),VH=200,SIZE=(386,204)"
            for name in REQUIRED_VISUAL_LAYOUTS)
        complete = "ADVANCED_V2_REOPEN_VALIDATION=OK\nLAYOUTS_OK=true;BASAL_CONTINUATION_HATCHES=1\nVIEWPORTS=" + entries
        self.assertEqual(_reopen_report_errors(complete), [])
        self.assertIn("DwgViewportValidationMissing:GEO_EN",
                      _reopen_report_errors(complete.replace("GEO_EN:N=2,ON=True,LOCKED=True", "GEO_EN:N=2,ON=False,LOCKED=False")))
        self.assertIn("DwgViewportValidationMissing:GEO_JP",
                      _reopen_report_errors("ADVANCED_V2_REOPEN_VALIDATION=OK\nLAYOUTS_OK=true"))

    def test_visual_qa_rejects_non_native_input_before_running_autocad(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder, "invalid.dwg")
            source.write_bytes(b"not-dwg")
            with self.assertRaisesRegex(ValueError, "AC1032"):
                render_disposable_model_preview(source, Path(folder, "preview.png"),
                                                Path(folder, "qa.json"))


if __name__ == "__main__": unittest.main()
