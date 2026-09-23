import base64
import json
import unittest

from geologic_3d_engine.export.contract_integrity import (
    build_integrity_envelope, canonical_json_bytes, verify_integrity_envelope)


class ContractIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.payload={"name":"A\u030Aso","vertices":[[-0.0,1.0],[2.0,3.0]]}
        self.validation={"passed":True,"polygonCount":1}
        self.envelope=build_integrity_envelope(self.payload,self.validation,"test-1")

    def test_round_trip_and_normalization(self):
        payload,validation=verify_integrity_envelope(self.envelope)
        self.assertEqual(payload["name"],"Åso")
        self.assertEqual(payload["vertices"][0][0],0.0)
        self.assertEqual(validation["payloadSha256"],self.envelope["payloadSha256"])

    def test_key_order_does_not_change_producer_bytes(self):
        self.assertEqual(canonical_json_bytes({"b":1,"a":2}),canonical_json_bytes({"a":2,"b":1}))

    def test_payload_mutation_is_rejected(self):
        bad=dict(self.envelope)
        raw=bytearray(base64.b64decode(bad["payloadBase64"])); raw[-2]^=1
        bad["payloadBase64"]=base64.b64encode(raw).decode("ascii")
        with self.assertRaisesRegex(ValueError,"payload digest mismatch"):
            verify_integrity_envelope(bad)

    def test_validation_mutation_is_rejected(self):
        bad=dict(self.envelope)
        raw=json.loads(base64.b64decode(bad["validationBase64"]).decode("utf-8"))
        raw["passed"]=False
        bad["validationBase64"]=base64.b64encode(canonical_json_bytes(raw)).decode("ascii")
        with self.assertRaisesRegex(ValueError,"validation digest mismatch"):
            verify_integrity_envelope(bad)

    def test_truncation_and_missing_fields_are_rejected(self):
        bad=dict(self.envelope); bad["payloadBase64"]=bad["payloadBase64"][:-2]
        with self.assertRaisesRegex(ValueError,"invalid envelope base64"):
            verify_integrity_envelope(bad)
        bad=dict(self.envelope); del bad["validationBase64"]
        with self.assertRaisesRegex(ValueError,"invalid envelope base64"):
            verify_integrity_envelope(bad)

    def test_nonfinite_rejected(self):
        for value in (float("nan"),float("inf"),float("-inf")):
            with self.assertRaisesRegex(ValueError,"non-finite"):
                build_integrity_envelope({"x":value},self.validation,"test-1")


if __name__=="__main__": unittest.main()
