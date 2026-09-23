import hashlib
import json
import unittest

from geologic_3d_engine.section.borehole_evidence import apply_geographic_transform_record


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def hole():
    return {"boreholeId":"BH","longitude":131.00925,"latitude":32.88161111111111,
        "collarElevationM":513.83,"totalDepthM":4.0,"horizontalCrs":"EPSG:4612",
        "verticalDatum":"TokyoPeil","sourceId":"SOURCE","sourceUrl":"https://example.invalid",
        "exchangeFormatVersion":"BED0300-DTD-3.00","intervals":[{"topDepthM":0.0,
        "bottomDepthM":4.0,"sourceLabel":"ローム","normalizedLithology":"ローム",
        "termStatus":"Unverified","evidenceStatus":"Unverified"}]}


def transform():
    value={"schemaVersion":"GeographicEvidenceTransform-1.0","sourceId":"SOURCE",
        "sourceCrs":"EPSG:4612","targetCrs":"EPSG:6668",
        "sourceLonLat":[131.00925,32.88161111111111],
        "targetLonLat":[131.00925,32.88161111111111],
        "roundTripResidualDegrees":[0.0,0.0],"operationDescription":"test",
        "operationAccuracyM":1.0,"pyprojVersion":"3.7.2","projVersion":"9.8.1",
        "boundary":"CoordinateTransformationOnly_NoVerticalDatumOrCorrelationAuthorization"}
    return value|{"recordSha256":digest(value)}


class BoreholeCoordinateTransformTests(unittest.TestCase):
    def test_hash_bound_transform_preserves_both_coordinates(self):
        result=apply_geographic_transform_record(hole(),transform())
        self.assertEqual(result["horizontalCrs"],"EPSG:6668")
        self.assertEqual(result["sourceCoordinatePreserved"],[131.00925,32.88161111111111])
        self.assertEqual(result["transformedCoordinatePreserved"],[131.00925,32.88161111111111])
        self.assertEqual(result["coordinateTransformState"],
                         "EvidenceBoundTransformation_NoVerticalDatumChange")

    def test_horizontal_transform_does_not_upgrade_unverified_vertical_datum(self):
        source=hole() | {"verticalDatum":"NotStated",
                         "verticalDatumStatus":"Unverified"}
        result=apply_geographic_transform_record(source,transform())
        self.assertEqual(result["horizontalCrsStatus"],"Verified")
        self.assertEqual(result["verticalDatumStatus"],"Unverified")
        self.assertFalse(result["elevationConstraintAuthorized"])

    def test_horizontal_transform_does_not_override_unverified_collar_accuracy(self):
        source=hole() | {"horizontalCrsStatus":"Declared",
                         "verticalDatumStatus":"Declared",
                         "collarElevationAccuracyStatus":"Unverified",
                         "horizontalPositionAccuracyStatus":"DeclaredResolutionOnly"}
        result=apply_geographic_transform_record(source,transform())
        self.assertEqual(result["horizontalCrsStatus"],"Verified")
        self.assertEqual(result["collarElevationAccuracyStatus"],"Unverified")
        self.assertEqual(result["horizontalPositionAccuracyStatus"],"DeclaredResolutionOnly")
        self.assertFalse(result["elevationConstraintAuthorized"])

    def test_tamper_binding_target_residual_and_accuracy_are_rejected(self):
        cases=[]
        for key,value in (("sourceId","OTHER"),("sourceCrs","EPSG:4301"),
                          ("targetCrs","EPSG:4326"),("operationAccuracyM",3.0)):
            item=transform();item[key]=value;item["recordSha256"]=digest({k:v for k,v in item.items() if k!="recordSha256"});cases.append(item)
        item=transform();item["sourceLonLat"][0]+=0.01;item["recordSha256"]=digest({k:v for k,v in item.items() if k!="recordSha256"});cases.append(item)
        item=transform();item["roundTripResidualDegrees"]=[1e-5,0];item["recordSha256"]=digest({k:v for k,v in item.items() if k!="recordSha256"});cases.append(item)
        item=transform();item["targetLonLat"][0]+=0.01;cases.append(item)
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):
                apply_geographic_transform_record(hole(),case)


if __name__=="__main__":unittest.main()
