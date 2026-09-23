import unittest
from geologic_3d_engine.section.borehole_mapped_unit_compatibility import audit_borehole_mapped_unit_compatibility


def unit(uid,**changes):
    value={"unitId":uid,"sourceLabel":"legacy ash","normalizedLabel":"volcanic ash",
        "normalizationAuthority":"CGI","vocabularyVersion":"2025","termStatus":"Current",
        "evidenceStatus":"Observed","geologicAgeInterval":{"youngerMa":0.01,"olderMa":0.1,
        "timeScaleAuthority":"ICS","timeScaleVersion":"2024-12"},
        "eventBoundaryAbove":"Deposition","eventBoundaryBelow":"Erosion"}
    value.update(changes);return value


class BoreholeMappedUnitCompatibilityTests(unittest.TestCase):
    def test_all_dimensions_matching_is_candidate_not_authorization(self):
        result=audit_borehole_mapped_unit_compatibility("GeometryConstraint",[unit("B")],[unit("M")],
            [{"boreholeUnitId":"B","mappedUnitId":"M"}])
        self.assertEqual(result["compatibleCandidateCount"],1);self.assertFalse(result["realRegionAuthorized"])
        self.assertFalse(result["results"][0]["geometryAuthorizationGranted"])
    def test_name_match_cannot_override_scope_age_vocabulary_or_event_conflict(self):
        mapped=unit("M",vocabularyVersion="2024",geologicAgeInterval={"youngerMa":2,"olderMa":3,
            "timeScaleAuthority":"ICS","timeScaleVersion":"2023-09"},eventBoundaryBelow="Fault")
        result=audit_borehole_mapped_unit_compatibility("RegionalContextOnly",[unit("B")],[mapped],
            [{"boreholeUnitId":"B","mappedUnitId":"M"}])
        reasons=result["results"][0]["reasons"]
        self.assertIn("BoreholeNotAuthorizedAsGeometryConstraint",reasons)
        self.assertIn("VocabularyIdentityMismatch",reasons);self.assertIn("TimeScaleIdentityMismatch",reasons)
        self.assertIn("eventBoundaryBelowConflict",reasons)
    def test_unverified_and_missing_age_reject(self):
        result=audit_borehole_mapped_unit_compatibility("GeometryConstraint",
            [unit("B",evidenceStatus="Unverified",geologicAgeInterval=None)],[unit("M")],
            [{"boreholeUnitId":"B","mappedUnitId":"M"}])
        self.assertEqual(result["compatibleCandidateCount"],0)
        self.assertIn("EvidenceStatusInsufficient",result["results"][0]["reasons"])
        self.assertIn("GeologicAgeMissingOrInvalid",result["results"][0]["reasons"])
