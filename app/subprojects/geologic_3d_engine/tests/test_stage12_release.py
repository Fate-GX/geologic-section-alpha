import unittest
from dataclasses import replace
from pathlib import Path
import json

from geologic_3d_engine.stage12 import run_stage_twelve, stage_twelve_manifest
from geologic_3d_engine.validation.release_spec import REQUIRED, ReleaseSpec, load_release_spec

ROOT=Path(__file__).resolve().parents[1]

class Stage12ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.spec=load_release_spec(ROOT/"examples/stage12_release_fixture_spec.json")
        self.audit=json.loads((ROOT/"outputs/stage11_dwg_validation.json").read_text(encoding="utf-8"))
        self.result=run_stage_twelve(self.spec,self.audit)
    def test_fixture_passes_only_declared_integration_use(self): self.assertTrue(self.result["passed"])
    def test_fixture_is_not_portfolio_release(self): self.assertFalse(self.result["releaseValidation"]["portfolioReleasePassed"])
    def test_fixture_classification_is_explicit(self):
        self.assertEqual(self.result["releaseValidation"]["artifactClassification"],"AutoCadIntegrationFixture")
    def test_missing_geological_and_sheet_checks_are_reported(self):
        failed=self.result["releaseValidation"]["failedPortfolioChecks"]
        self.assertIn("regionalProfile",failed); self.assertIn("completeLegend",failed)
    def test_native_facts_are_taken_from_reopen_audit(self):
        bad=dict(self.audit); bad["validation"]="FAILED"
        self.assertFalse(run_stage_twelve(self.spec,bad)["passed"])
    def test_false_declared_native_check_cannot_override_valid_audit(self):
        checks=dict(self.spec.checks); checks["nativeEntities"]=False
        self.assertTrue(run_stage_twelve(replace(self.spec,checks=checks),self.audit)["passed"])
    def test_complete_portfolio_can_be_accepted_for_declared_use(self):
        complete=ReleaseSpec("SyntheticPortfolioPublication",{k:True for k in REQUIRED},"reviewer","x.dwg")
        result=run_stage_twelve(complete,self.audit)
        self.assertTrue(result["passed"]); self.assertTrue(result["releaseValidation"]["portfolioReleasePassed"])
    def test_incomplete_portfolio_is_rejected(self):
        checks={k:True for k in REQUIRED}; checks["pdfVisualReview"]=False
        self.assertFalse(run_stage_twelve(ReleaseSpec("SyntheticPortfolioPublication",checks,"r","x"),self.audit)["passed"])
    def test_unknown_check_is_rejected(self):
        self.assertFalse(run_stage_twelve(replace(self.spec,checks={"invented":True}),self.audit)["passed"])
    def test_manifest_does_not_authorize_another_stage(self):
        self.assertIsNone(stage_twelve_manifest(self.result)["nextAuthorizedStage"])

if __name__=="__main__": unittest.main()
