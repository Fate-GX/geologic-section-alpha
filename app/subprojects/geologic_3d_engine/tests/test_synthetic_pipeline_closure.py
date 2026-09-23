"""Real canonical pipeline lifecycle; no mock return values or threshold relaxation."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from geologic_3d_engine import gui_backend as backend
from geologic_3d_engine.export.contract_integrity import verify_integrity_envelope

ROOT = Path(__file__).resolve().parents[1]


def snapshot(folder):
    return {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}


def all_error_codes(value):
    codes = set()
    if isinstance(value, dict):
        if isinstance(value.get("code"), str):
            codes.add(value["code"])
        for nested in value.values():
            codes.update(all_error_codes(nested))
    elif isinstance(value, list):
        for nested in value:
            codes.update(all_error_codes(nested))
    return codes


class SyntheticPipelineClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.root = Path(temp.name)
        inputs = cls.root / "inputs"
        inputs.mkdir()
        bundle_source = ROOT / "examples/stage11_gui_run_bundle.json"
        bundle = json.loads(bundle_source.read_text(encoding="utf-8"))
        cls.bundle = inputs / bundle_source.name
        shutil.copyfile(bundle_source, cls.bundle)
        for relative in bundle["inputs"].values():
            shutil.copyfile(ROOT / "examples" / relative, inputs / relative)
        cls.original_inputs = snapshot(inputs)
        output = cls.root / "outputs"
        cls.calls = set()

        def profiler(frame, event, arg):
            if event == "call" and "geologic_3d_engine" in frame.f_code.co_filename:
                cls.calls.add(frame.f_code.co_name)

        previous = sys.getprofile()
        try:
            sys.setprofile(profiler)
            cls.first = backend.execute_run_bundle(cls.bundle, output)
        finally:
            sys.setprofile(previous)
        cls.first_files = snapshot(output)
        # Direct Stage11 entry with explicitly loaded inputs, independent of GUI dispatch.
        _, paths = backend.load_run_bundle(cls.bundle)
        keys_loaders = (
            ("config", backend.load_config), ("stackSpec", backend.load_stack_spec),
            ("eventSpec", backend.load_event_spec), ("compactionSpec", backend.load_compaction_spec),
            ("structuralSpec", backend.load_structural_spec), ("intrusionSpec", backend.load_intrusion_spec),
            ("meshSpec", backend.load_mesh_spec), ("refinementSpec", backend.load_refinement_spec),
            ("ensembleSpec", backend.load_ensemble_spec), ("sectionSpec", backend.load_section_spec),
            ("exportSpec", backend.load_export_spec),
        )
        cls.direct = backend.run_stage_eleven(*(loader(paths[key]) for key, loader in keys_loaders))
        cls.inputs_after_success = snapshot(inputs)
        bad_path = paths["refinementSpec"]
        original = bad_path.read_bytes()
        bad = json.loads(original)
        bad["refinementFactor"] = 3
        bad_path.write_text(json.dumps(bad), encoding="utf-8")
        cls.rejected = backend.execute_run_bundle(cls.bundle, output)
        cls.rejected_files = snapshot(output)
        bad_path.write_bytes(original)
        cls.restored = backend.execute_run_bundle(cls.bundle, output)
        cls.restored_files = snapshot(output)
        cls.final_inputs = snapshot(inputs)

    def test_real_pipeline_calls_not_just_declared_stage_path(self):
        self.assertTrue(self.first["passed"])
        names = {"run_stage_" + n for n in
                 ("two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven")}
        self.assertTrue(names <= self.calls, sorted(names - self.calls))
        self.assertIn("load_config", self.calls)
        self.assertIn("validate_stage_one", self.calls)

    def test_success_files_and_direct_entry_agree(self):
        self.assertEqual(set(self.first_files), {"run_summary.json", "stage11_manifest.json",
                                               "neutral_contract.json", "contract_envelope.json"})
        self.assertTrue(self.direct["passed"])
        self.assertEqual(self.first["contract"], self.direct["contract"])
        self.assertEqual(self.first["contractEnvelope"], self.direct["contractEnvelope"])
        payload, validation = verify_integrity_envelope(json.loads(self.first_files["contract_envelope.json"]))
        self.assertTrue(validation["passed"])
        self.assertIn("uncertaintyVisualization", payload)

    def test_real_refinement_rejection_removes_prior_success(self):
        self.assertFalse(self.rejected["passed"])
        self.assertIn("AdaptiveRefinementFailed", all_error_codes(self.rejected))
        self.assertEqual(set(self.rejected_files), {"run_summary.json", "stage11_manifest.json"})
        self.assertFalse(json.loads(self.rejected_files["run_summary.json"])["contractWritten"])

    def test_restored_rerun_is_byte_identical_and_inputs_unchanged(self):
        self.assertTrue(self.restored["passed"])
        self.assertEqual(self.first_files, self.restored_files)
        self.assertEqual(self.original_inputs, self.inputs_after_success)
        self.assertEqual(self.original_inputs, self.final_inputs)

    def test_success_is_experimental_not_real_region_or_native_dwg(self):
        self.assertEqual(self.first["decision"], "Experimental")
        self.assertTrue(self.first["contract"]["notForDesign"])
        self.assertIn("Synthetic", self.first["contract"]["syntheticDisclosure"])
        self.assertFalse(self.first["gates"][0]["nativeDwgWritten"])
        self.assertFalse(self.first["gates"][0]["nativeDwgReopenValidated"])
        self.assertEqual(self.first["contract"]["uncertaintyVisualization"]["cadEntityAuthorization"],
                         "None_DiagnosticDataOnly")


if __name__ == "__main__":
    unittest.main()
