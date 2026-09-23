import unittest

from geologic_3d_engine.section.mapped_unit_morphology import (
    apply_mapped_unit_morphology, audit_declared_geometry_roles,
)


def catalog():
    return {"units": [{"unitId": "U1", "symbol": "Ksc"},
                      {"unitId": "U2", "symbol": "a"}]}


def profile():
    return {"records": [
        {"sourceSymbol": "Ksc", "morphologyClass": "ScoriaConeAndLavaFlowApron",
         "sourceId": "S1", "locator": "p.4", "evidenceStatus": "DirectText",
         "qualitativeFlowDirections": ["North", "Northwest"],
         "numericFlowAzimuthAuthorized": False,
         "numericSubsurfaceGeometryAuthorized": False},
        {"sourceSymbol": "a", "morphologyClass": "SurficialFallDepositDrape",
         "sourceId": "S1", "locator": "p.5", "evidenceStatus": "DirectText",
         "numericSubsurfaceGeometryAuthorized": False},
    ]}


class MappedUnitMorphologyTests(unittest.TestCase):
    def test_finite_and_drape_classes_remain_qualitative(self):
        result = apply_mapped_unit_morphology(catalog(), profile())
        cone, ash = result["units"]
        self.assertTrue(cone["finiteBodyRequired"])
        self.assertFalse(cone["blanketLayerAuthorized"])
        self.assertEqual(["North", "Northwest"], cone["qualitativeFlowDirections"])
        self.assertFalse(cone["numericFlowAzimuthAuthorized"])
        self.assertFalse(result["realRegionSubsurfaceGeometryAuthorized"])
        self.assertFalse(ash["finiteBodyRequired"])

    def test_finite_body_rejects_blanket_and_drape_roles(self):
        assigned = apply_mapped_unit_morphology(catalog(), profile())
        for role in ("BlanketLayer", "SurfaceDrape"):
            result = audit_declared_geometry_roles(
                [{"unitId": "U1", "geometryRole": role}], assigned)
            self.assertFalse(result["passed"])
        self.assertTrue(audit_declared_geometry_roles(
            [{"unitId": "U1", "geometryRole": "FiniteBody"}], assigned)["passed"])

    def test_unclassified_unit_remains_unresolved(self):
        result = apply_mapped_unit_morphology(
            {"units": [{"unitId": "X", "symbol": "unknown"}]}, profile())
        self.assertEqual("NeedsSourceLinkedClassification",
                         result["units"][0]["morphologyStatus"])
        self.assertFalse(result["units"][0]["numericSubsurfaceGeometryAuthorized"])

    def test_invalid_claims_and_duplicate_symbols_fail_closed(self):
        invalid = [
            {"records": profile()["records"] * 2},
            {"records": [{**profile()["records"][0],
                           "numericSubsurfaceGeometryAuthorized": True}]},
            {"records": [{**profile()["records"][0],
                           "qualitativeFlowDirections": ["NorthNorthwest"]}]},
            {"records": [{**profile()["records"][0],
                           "numericFlowAzimuthAuthorized": True}]},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                apply_mapped_unit_morphology(catalog(), value)

    def test_unknown_unit_and_role_fail_closed(self):
        assigned = apply_mapped_unit_morphology(catalog(), profile())
        for declaration in ({"unitId": "missing", "geometryRole": "FiniteBody"},
                            {"unitId": "U1", "geometryRole": "Sheet"}, {}):
            with self.subTest(declaration=declaration), self.assertRaises(ValueError):
                audit_declared_geometry_roles([declaration], assigned)


if __name__ == "__main__":
    unittest.main()
