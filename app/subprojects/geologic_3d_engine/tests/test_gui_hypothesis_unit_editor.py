import unittest
from geologic_3d_engine.gui_hypothesis_unit_editor import (add_or_update_unit,
    build_unit_declaration_document,remove_unit)
from geologic_3d_engine.gui_contact_orientation_editor import update_hypothesis_row
from geologic_3d_engine.section.contact_orientation_hypothesis import build_contact_orientation_hypothesis_template
from tests.test_contact_orientation_hypothesis import intersections


def value(**changes):
    base={"unitId":"U1","sourceLabel":"旧称","sourceYear":"1985","sourceAuthority":"GSJ",
        "normalizedLabel":"volcaniclastic rock","normalizationAuthority":"IUGS",
        "vocabularyVersion":"2025","termStatus":"Current","normalizationNote":"original retained",
        "evidenceStatus":"SyntheticAssumption","topBoundary":"Terrain","bottomBoundary":"CONTACT-ORIENTATION-0000"}
    base.update(changes);return base


class HypothesisUnitEditorBackendTests(unittest.TestCase):
    def setUp(self):
        template=build_contact_orientation_hypothesis_template(intersections())
        self.template=update_hypothesis_row(template,0,{"orientationBasis":"SyntheticAssumption",
            "trueDipDegrees":20,"dipDirectionDegrees":90,"angularUncertaintyDegrees":2,
            "lateralSupportM":100,"basisSourceIds":"","interpretationNote":"test"})
    def test_preserves_source_and_normalized_terminology(self):
        document=build_unit_declaration_document(self.template)
        result=add_or_update_unit(document,None,value())
        row=result["declarations"][0]
        self.assertEqual(row["sourceLabel"],"旧称");self.assertEqual(row["normalizedLabel"],"volcaniclastic rock")
        self.assertFalse(row["sectionGeometryAuthorized"])
        self.assertEqual(remove_unit(result,0)["declarations"],[])
    def test_rejects_unknown_contact_duplicate_and_incomplete_terminology(self):
        document=build_unit_declaration_document(self.template)
        with self.assertRaises(ValueError):add_or_update_unit(document,None,value(bottomBoundary="UNKNOWN"))
        first=add_or_update_unit(document,None,value())
        with self.assertRaises(ValueError):add_or_update_unit(first,None,value())
        with self.assertRaises(ValueError):add_or_update_unit(document,None,value(vocabularyVersion=""))
