import unittest
from gui_progressive_disclosure import DisclosureState,audit_information_architecture
class AdvancedGuiDisclosureTests(unittest.TestCase):
    def test_default_is_simple_and_toggle_reversible(self):
        state=DisclosureState();self.assertFalse(state.expanded);self.assertIn("表示",state.button_text);self.assertEqual(state,state.toggled().toggled())
    def test_primary_workflow_contract_passes(self):self.assertTrue(audit_information_architecture()["passed"])
    def test_overlap_or_missing_primary_fails(self):
        result=audit_information_architecture(("Location","Output"),("Location","Diagnostics"));self.assertFalse(result["passed"]);self.assertEqual(["Location"],result["duplicates"])
if __name__=="__main__":unittest.main()
