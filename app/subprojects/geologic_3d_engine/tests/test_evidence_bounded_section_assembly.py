import unittest

from geologic_3d_engine.section.evidence_bounded_section_assembly import assemble_evidence_bounded_section


def projection(contact_id, stations, values):
    return {"contactId": contact_id, "routeProjection": {"samples": [
        {"stationM": station, "contactElevationM": value}
        for station, value in zip(stations, values)]}}


class EvidenceBoundedSectionAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.stations = [0, 10, 20, 30]
        self.terrain = [{"stationM": s, "elevationM": 100} for s in self.stations]
        self.units = [{"unitId": "LOWER", "normalizedLithology": "mudstone",
                       "basalContactId": "BASE", "topBoundary": "MIDDLE"},
                      {"unitId": "UPPER", "normalizedLithology": "sandstone",
                       "basalContactId": "MIDDLE", "topBoundary": "Terrain"}]

    def test_only_locally_double_bounded_samples_become_units(self):
        contacts = [projection("BASE", self.stations, [None, 70, 71, None]),
                    projection("MIDDLE", self.stations, [80, 82, None, None])]
        result = assemble_evidence_bounded_section(
            self.terrain, contacts, self.units, ordering_tolerance_m=1e-9)
        lower = result["unitsBottomUp"][0]["samples"]
        upper = result["unitsBottomUp"][1]["samples"]
        self.assertEqual([x["coverageStatus"] for x in lower],
                         ["UnknownMissingBoundary", "BoundedByEvidence",
                          "UnknownMissingBoundary", "UnknownMissingBoundary"])
        self.assertEqual([x["coverageStatus"] for x in upper],
                         ["BoundedByEvidence", "BoundedByEvidence",
                          "UnknownMissingBoundary", "UnknownMissingBoundary"])
        self.assertFalse(result["contactClippingUsed"])

    def test_crossing_and_above_terrain_are_rejected_not_clipped(self):
        crossing = [projection("BASE", self.stations, [70, 90, 70, 70]),
                    projection("TOP", self.stations, [80, 89, 80, 80])]
        with self.assertRaises(ValueError):
            assemble_evidence_bounded_section(
                self.terrain, crossing, self.units, ordering_tolerance_m=0)
        above = [projection("BASE", self.stations, [70] * 4),
                 projection("TOP", self.stations, [101] * 4)]
        with self.assertRaises(ValueError):
            assemble_evidence_bounded_section(
                self.terrain, above, self.units, ordering_tolerance_m=0)

    def test_misaligned_stations_and_duplicate_contacts_reject(self):
        contacts = [projection("C", self.stations, [70] * 4),
                    projection("C", self.stations, [80] * 4)]
        with self.assertRaises(ValueError):
            assemble_evidence_bounded_section(
                self.terrain, contacts, self.units, ordering_tolerance_m=0)

    def test_implicit_or_wrong_unit_boundaries_reject(self):
        contacts = [projection("BASE", self.stations, [70] * 4),
                    projection("MIDDLE", self.stations, [80] * 4)]
        missing = [dict(item) for item in self.units]
        missing[-1].pop("topBoundary")
        with self.assertRaises(ValueError):
            assemble_evidence_bounded_section(
                self.terrain, contacts, missing, ordering_tolerance_m=0)
        wrong = [dict(item) for item in self.units]
        wrong[0]["topBoundary"] = "Terrain"
        with self.assertRaises(ValueError):
            assemble_evidence_bounded_section(
                self.terrain, contacts, wrong, ordering_tolerance_m=0)
        contacts[1] = projection("D", [0, 10, 21, 30], [80] * 4)
        with self.assertRaises(ValueError):
            assemble_evidence_bounded_section(
                self.terrain, contacts, self.units, ordering_tolerance_m=0)


if __name__ == "__main__":
    unittest.main()
