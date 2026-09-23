import unittest
from geologic_3d_engine.section.coordinate_alignment import (
    align_observations,ellipsoidal_to_orthometric_height)


def record(**changes):
    value={"observationId":"P1","longitude":131.0,"latitude":32.8,"heightM":100.0,
      "heightType":"Orthometric","horizontalCrs":"JGD2011","verticalDatum":"JGD2024-height",
      "coordinateEpoch":"2026-09-04","sourceId":"OBS-1"}
    value.update(changes); return value


class CoordinateAlignmentTests(unittest.TestCase):
    def test_gsi_height_equation(self):
        self.assertEqual(ellipsoidal_to_orthometric_height(150,35,2),113)

    def test_identity_like_transform_and_roundtrip(self):
        forward=lambda lon,lat,a,b,e:(lon*1000,lat*1000)
        inverse=lambda x,y,a,b,e:(x/1000,y/1000)
        result=align_observations([record()],forward,inverse,"EPSG:6670","JGD2024-height",.001)
        self.assertTrue(result["passed"]); self.assertEqual(result["records"][0]["targetXY"],[131000,32800])
        self.assertEqual(result["records"][0]["targetAxisOrder"],"EastingNorthing")

    def test_ellipsoidal_requires_geoid_and_preserves_method(self):
        identity=lambda x,y,a,b,e:(x,y)
        missing=align_observations([record(heightType="Ellipsoidal")],identity,identity,
                                   "JGD2011","JGD2024-height",1)
        self.assertEqual(missing["errors"][0]["code"],"GeoidEvidenceRequired")
        good=record(heightType="Ellipsoidal",heightM=150,geoidHeightM=35,
                    geoidModel="JGEOID2024",referenceSurfaceCorrectionM=2)
        result=align_observations([good],identity,identity,"JGD2011","JGD2024-height",1)
        self.assertEqual(result["records"][0]["orthometricHeightM"],113)

    def test_datum_mismatch_and_bad_roundtrip_are_rejected(self):
        identity=lambda x,y,a,b,e:(x,y)
        mismatch=align_observations([record(verticalDatum="OldDatum")],identity,identity,
                                    "JGD2011","JGD2024-height",1)
        self.assertEqual(mismatch["errors"][0]["code"],"VerticalDatumTransformationRequired")
        inverse=lambda x,y,a,b,e:(x+.001,y)
        bad=align_observations([record()],identity,inverse,"JGD2011","JGD2024-height",1)
        self.assertEqual(bad["errors"][0]["code"],"HorizontalRoundtripResidualExceeded")
        with self.assertRaises(ValueError):
            align_observations([record()],identity,identity,"JGD2011","JGD2024-height",1,"XY")


if __name__=="__main__": unittest.main()
