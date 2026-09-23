import hashlib
import json
import unittest

from geologic_3d_engine.section.evidence_section_workflow import build_evidence_constrained_section
from geologic_3d_engine.section.qualitative_stratigraphic_constraints import (
    validate_qualitative_stratigraphic_constraints)


def payload(relations=None, **changes):
    value={"schemaVersion":"QualitativeStratigraphicConstraints-1.0",
           "geometryAuthorization":"TopologyAndRelativeOrderOnly_NoNumericGeometry",
           "units":[{"unitId":"OLD","sourceLabel":"old","termStatus":"LocalRelativeUnit"},
                    {"unitId":"YOUNG","sourceLabel":"young","termStatus":"LocalRelativeUnit"}],
           "relations":relations or [{"olderUnitId":"OLD","youngerUnitId":"YOUNG",
             "relationKind":"UnconformableAbove","sourceId":"SOURCE","locator":"Figure 2",
             "evidenceStatus":"InterpretedFromSourceFigure"}]}
    value.update(changes)
    value["recordSha256"]=hashlib.sha256(json.dumps(value,sort_keys=True,
        separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return value


class QualitativeStratigraphicConstraintTests(unittest.TestCase):
    def test_valid_relation_produces_oldest_to_youngest_order_only(self):
        result=validate_qualitative_stratigraphic_constraints(payload())
        self.assertEqual(result["topologicalOrderOldestToYoungest"],["OLD","YOUNG"])
        self.assertFalse(result["numericGeometryAuthorized"])

    def test_cycle_numeric_geometry_and_tamper_are_rejected(self):
        cyclic=[{"olderUnitId":"OLD","youngerUnitId":"YOUNG","relationKind":"Overlies",
                 "sourceId":"S","locator":"F","evidenceStatus":"Literature"},
                {"olderUnitId":"YOUNG","youngerUnitId":"OLD","relationKind":"Overlies",
                 "sourceId":"S","locator":"F","evidenceStatus":"Literature"}]
        cases=[payload(cyclic),payload(elevationM=1200.0),payload()]
        cases[-1]["relations"][0]["locator"]="altered"
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):
                validate_qualitative_stratigraphic_constraints(case)

    def test_missing_source_unknown_relation_and_duplicate_unit_fail(self):
        missing=payload(); missing["relations"][0]["sourceId"]=""
        missing["recordSha256"]=hashlib.sha256(json.dumps({k:v for k,v in missing.items() if k!="recordSha256"},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        unknown=payload(); unknown["relations"][0]["relationKind"]="LooksSimilar"
        unknown["recordSha256"]=hashlib.sha256(json.dumps({k:v for k,v in unknown.items() if k!="recordSha256"},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        duplicate=payload(units=[{"unitId":"OLD","sourceLabel":"a","termStatus":"Unverified"},
                                 {"unitId":"OLD","sourceLabel":"b","termStatus":"Unverified"}])
        for case in (missing,unknown,duplicate):
            with self.assertRaises(ValueError): validate_qualitative_stratigraphic_constraints(case)

    def test_arbitrary_section_enforces_relative_order_without_authorizing_geometry(self):
        profile=[]
        for i,(lon,lat,elev) in enumerate(((131.0,32.88,100.0),(131.001,32.881,101.0),
                                           (131.002,32.88,100.0))):
            profile.append({"stationM":float(i*100),"longitude":lon,"latitude":lat,
                            "elevationM":elev})
        plan={"schemaVersion":"PlanEvidenceBundle-1.0","terrainProfile":profile,
              "authorizationState":"SubsurfaceInterpretationInputsPresent"}
        refs=[{"longitude":row["longitude"],"latitude":row["latitude"],
               "elevationM":80.0,"sourceId":"SYN","evidenceStatus":"SyntheticAssumption"}
              for row in profile]
        def unit(unit_id,thickness):
            samples=[{"longitude":row["longitude"],"latitude":row["latitude"],
                      "trueThicknessM":thickness,"sourceId":"SYN",
                      "evidenceStatus":"SyntheticAssumption"} for row in profile]
            return {"unitId":unit_id,"normalizedLithology":unit_id,
                    "thicknessEvidence":samples}
        accepted=build_evidence_constrained_section(plan,refs,
            [unit("OLD",5),unit("YOUNG",4)],qualitative_constraints=payload())
        self.assertTrue(accepted["qualitativeStratigraphicAudit"]["passed"])
        self.assertFalse(accepted["qualitativeStratigraphicAudit"]["numericGeometryAuthorized"])
        self.assertFalse(accepted["realRegionAuthorized"])
        with self.assertRaises(ValueError):
            build_evidence_constrained_section(plan,refs,[unit("YOUNG",4),unit("OLD",5)],
                qualitative_constraints=payload())


if __name__=="__main__": unittest.main()
