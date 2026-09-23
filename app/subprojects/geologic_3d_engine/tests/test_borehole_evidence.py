import unittest
from geologic_3d_engine.section.borehole_evidence import (
    apply_vertical_datum_interpretation, normalize_borehole, project_boreholes_to_geographic_route,
    screen_boreholes_to_geographic_route)
import hashlib,json


def hole(**changes):
    value={"boreholeId":"BH-1","longitude":131.001,"latitude":32.8,
      "collarElevationM":100.0,"totalDepthM":20.0,"horizontalCrs":"JGD2011",
      "verticalDatum":"TokyoPeil","sourceId":"KUNIJIBAN-X","sourceUrl":"https://example.invalid/x",
      "exchangeFormatVersion":"BORING-XML-3.00","intervals":[
       {"topDepthM":0.0,"bottomDepthM":5.0,"sourceLabel":"表土","normalizedLithology":"soil",
        "termStatus":"Current","evidenceStatus":"Observed"},
       {"topDepthM":5.0,"bottomDepthM":20.0,"sourceLabel":"砂礫","normalizedLithology":"gravelly sand",
        "termStatus":"Current","evidenceStatus":"Observed"}]}
    value.update(changes); return value


class BoreholeEvidenceTests(unittest.TestCase):
    def test_depth_to_elevation_and_provenance(self):
        result=normalize_borehole(hole())
        self.assertEqual(result["intervals"][0]["bottomElevationM"],95)
        self.assertEqual(result["intervals"][1]["bottomElevationM"],80)
        self.assertEqual(result["normalizationState"],"EvidenceNormalized_NoCorrelation")

    def test_gap_overlap_and_unknown_status_are_rejected(self):
        bad=hole(); bad["intervals"][1]["topDepthM"]=6
        with self.assertRaises(ValueError): normalize_borehole(bad)
        bad=hole(); bad["intervals"][0]["evidenceStatus"]="Assumed"
        with self.assertRaises(ValueError): normalize_borehole(bad)

    def test_near_and_far_projection_preserve_source_coordinates(self):
        route=[[131.0,32.8],[131.01,32.8]]
        near=hole(latitude=32.8001)
        far=hole(boreholeId="BH-2", latitude=32.82)
        result=project_boreholes_to_geographic_route([near,far],route,100)
        self.assertEqual([x["projectionState"] for x in result],["Projected","Rejected"])
        self.assertEqual(result[0]["sourceLonLat"],[131.001,32.8001])

    def test_missing_datum_and_boolean_depth_are_rejected(self):
        with self.assertRaises(ValueError): normalize_borehole(hole(verticalDatum=""))
        with self.assertRaises(ValueError): normalize_borehole(hole(totalDepthM=True))

    def test_route_projection_rejects_incompatible_horizontal_crs(self):
        with self.assertRaises(ValueError):
            project_boreholes_to_geographic_route([hole(horizontalCrs="EPSG:4326")],
                                                   [[131,32.8],[131.01,32.8]],100)

    def test_unverified_reference_metadata_blocks_section_constraint(self):
        uncertain=hole(latitude=32.8001, horizontalCrsStatus="Unverified",
                       verticalDatumStatus="Unverified")
        normalized=normalize_borehole(uncertain)
        self.assertFalse(normalized["elevationConstraintAuthorized"])
        result=project_boreholes_to_geographic_route(
            [uncertain], [[131.0,32.8],[131.01,32.8]], 100)[0]
        self.assertEqual(result["projectionState"], "Rejected")
        self.assertEqual(result["projectionRejectionReasons"],
                         ["HorizontalReferenceNotVerified","VerticalDatumNotVerified"])

    def test_authority_inference_is_preserved_but_not_authorized(self):
        inferred=normalize_borehole(hole(verticalDatumStatus="AuthorityInferred"))
        self.assertEqual(inferred["verticalDatumStatus"],"AuthorityInferred")
        self.assertFalse(inferred["elevationConstraintAuthorized"])

    def test_declared_datums_do_not_override_unverified_collar_accuracy(self):
        result=normalize_borehole(hole(horizontalCrsStatus="Declared",
            verticalDatumStatus="Declared",collarElevationAccuracyStatus="Unverified"))
        self.assertEqual(result["collarElevationAccuracyStatus"],"Unverified")
        self.assertFalse(result["elevationConstraintAuthorized"])
        with self.assertRaises(ValueError):
            normalize_borehole(hole(collarElevationAccuracyStatus="Guessed"))

    def test_reading_resolution_does_not_become_position_accuracy(self):
        result=normalize_borehole(hole(horizontalCrsStatus="Verified",
            verticalDatumStatus="Declared",horizontalPositionAccuracyStatus="DeclaredResolutionOnly"))
        self.assertFalse(result["elevationConstraintAuthorized"])
        with self.assertRaises(ValueError):
            normalize_borehole(hole(horizontalPositionAccuracyStatus="Approximate"))

    def test_unverified_geographic_candidate_can_be_screened_but_never_authorized(self):
        uncertain=hole(horizontalCrs="GeodeticDatumUnstated",
                       horizontalCrsStatus="Unverified",
                       verticalDatum="ElevationReferenceUnstated",
                       verticalDatumStatus="Unverified", latitude=32.8001)
        result=screen_boreholes_to_geographic_route(
            [uncertain], [[131.0,32.8],[131.01,32.8]],
            coordinate_assumption="Treat published degrees as locally comparable for discovery only")[0]
        self.assertEqual(result["screeningState"], "ApproximateDiscoveryScreenOnly")
        self.assertFalse(result["sectionConstraintAuthorized"])
        self.assertLess(result["projectionDistanceM"], 20.0)
        self.assertIn("ScreeningOperationIsNotCoordinateTransformationEvidence",
                      result["authorizationBlockers"])

    def test_candidate_screening_requires_an_explicit_assumption(self):
        with self.assertRaises(ValueError):
            screen_boreholes_to_geographic_route(
                [hole()], [[131.0,32.8],[131.01,32.8]], coordinate_assumption="")

    def test_national_height_definition_resolves_datum_but_not_accuracy(self):
        evidence={"schemaVersion":"VerticalDatumInterpretation-1.0",
          "boreholeSourceId":"KUNIJIBAN-X","sourceArtifactSha256":"a"*64,
          "sourceHeightTerm":"標高","applicability":"JapanMainIslands_NonExceptionalHeightDatum",
          "resolvedVerticalDatum":"TokyoBayMeanSeaLevel_JapanHeightDatum",
          "collarElevationAccuracyStatus":"Unverified"}
        evidence["recordSha256"]=hashlib.sha256(json.dumps(evidence,sort_keys=True,
          separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        result=apply_vertical_datum_interpretation(
            hole(verticalDatumStatus="AuthorityInferred"),evidence,"a"*64)
        self.assertEqual(result["verticalDatumStatus"],"Verified")
        self.assertEqual(result["collarElevationAccuracyStatus"],"Unverified")
        self.assertFalse(result["elevationConstraintAuthorized"])

    def test_vertical_interpretation_tamper_and_wrong_artifact_reject(self):
        evidence={"schemaVersion":"VerticalDatumInterpretation-1.0",
          "boreholeSourceId":"KUNIJIBAN-X","sourceArtifactSha256":"a"*64,
          "sourceHeightTerm":"標高","applicability":"JapanMainIslands_NonExceptionalHeightDatum",
          "resolvedVerticalDatum":"TokyoBayMeanSeaLevel_JapanHeightDatum"}
        evidence["recordSha256"]=hashlib.sha256(json.dumps(evidence,sort_keys=True,
          separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        with self.assertRaises(ValueError):apply_vertical_datum_interpretation(hole(),evidence,"b"*64)
        evidence["sourceHeightTerm"]="海抜"
        with self.assertRaises(ValueError):apply_vertical_datum_interpretation(hole(),evidence,"a"*64)


if __name__ == "__main__": unittest.main()
