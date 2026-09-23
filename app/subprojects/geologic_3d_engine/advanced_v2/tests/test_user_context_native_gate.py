import unittest

from advanced_v2.run_user_context_native_gate import (
    NativeGateInteractiveUserRequired,
    current_default_environment,
    ensure_interactive_user,
    windows_process_identity,
)


class UserContextNativeGateTests(unittest.TestCase):
    def test_sandbox_identity_is_rejected(self):
        with self.assertRaises(NativeGateInteractiveUserRequired):
            ensure_interactive_user("CodexSandboxOffline")

    def test_interactive_identity_is_accepted(self):
        self.assertEqual(ensure_interactive_user("yuusuke"), "yuusuke")

    def test_current_default_environment_removes_arg_profile(self):
        env = current_default_environment({
            "GEO3D_AUTOCAD_PROFILE_ARG": "unsafe.arg",
            "UNCHANGED": "value",
        })
        self.assertEqual(env["GEO3D_AUTOCAD_USE_CURRENT_DEFAULT"], "1")
        self.assertEqual(env["GEO3D_AUTOCAD_PRODUCT"], "ACAD")
        self.assertEqual(env["GEO3D_AUTOCAD_LANGUAGE"], "ja-JP")
        self.assertNotIn("GEO3D_AUTOCAD_PROFILE_ARG", env)
        self.assertEqual(env["UNCHANGED"], "value")

    def test_windows_process_identity_is_not_empty(self):
        self.assertTrue(windows_process_identity().strip())


if __name__ == "__main__":
    unittest.main()
