import unittest

from advanced_v2.native_environment_probe import classify_readiness


class NativeEnvironmentProbeTests(unittest.TestCase):
    def test_absent_hkcu_root_is_indeterminate_not_uninitialized_user_claim(self):
        result = classify_readiness(
            prerequisites={"coreConsole": True, "writerDll": True, "seedDxf": True},
            product_roots=[],
            inspection_identity="sandbox-user",
        )
        self.assertEqual(result["status"], "IndeterminateAcrossUserBoundary")
        self.assertEqual(result["interactiveAutoCadProfileState"],
                         "NotInferredFromDifferentProcessIdentity")

    def test_product_root_in_same_identity_is_ready(self):
        result = classify_readiness(
            prerequisites={"coreConsole": True, "writerDll": True, "seedDxf": True},
            product_roots=["ACAD-A101:411"],
            inspection_identity="interactive-user",
        )
        self.assertEqual(result["status"], "ReadyInInspectionUserContext")
        self.assertEqual(result["blockingReasons"], [])

    def test_missing_binary_remains_a_real_blocker(self):
        result = classify_readiness(
            prerequisites={"coreConsole": True, "writerDll": False, "seedDxf": True},
            product_roots=[],
            inspection_identity="sandbox-user",
        )
        self.assertEqual(result["status"], "BlockedBeforeNativeGate")
        self.assertEqual(result["blockingReasons"], ["writerDll"])


if __name__ == "__main__":
    unittest.main()
