"""Truthful classification of integration fixtures versus publishable sections."""

from .release_spec import REQUIRED

FIXTURE_REQUIRED=("nativeEntities","associativeSolidHatches","dwgReopenValidation")

def validate_release(spec,dwg_validation):
    spec.validate(); checks={name:spec.checks.get(name,False) for name in REQUIRED}
    # Native facts come from the reopen audit, never from an unchecked declaration.
    checks["nativeEntities"]=bool(dwg_validation.get("boundaries",0)>0 and dwg_validation.get("hatches",0)>0)
    checks["associativeSolidHatches"]=bool(dwg_validation.get("hatches",0)>0 and
      dwg_validation.get("solidHatches")==dwg_validation.get("hatches") and
      dwg_validation.get("associativeHatches")==dwg_validation.get("hatches"))
    checks["dwgReopenValidation"]=dwg_validation.get("validation")=="OK"
    failed=[name for name,value in checks.items() if not value]
    portfolio_passed=not failed and spec.intended_use=="SyntheticPortfolioPublication"
    fixture_failed=[name for name in FIXTURE_REQUIRED if not checks[name]]
    fixture_passed=not fixture_failed
    classification="SyntheticPortfolioPublication" if portfolio_passed else (
      "AutoCadIntegrationFixture" if fixture_passed else "RejectedArtifact")
    return {"validationCompleted":True,"artifactClassification":classification,
      "intendedUse":spec.intended_use,"portfolioReleasePassed":portfolio_passed,
      "integrationFixturePassed":fixture_passed,"failedPortfolioChecks":failed,
      "failedFixtureChecks":fixture_failed,"checkResults":checks,
      "decision":"Accepted" if portfolio_passed else ("Experimental" if fixture_passed else "Rejected"),
      "message":"Native integration fixture only; it is not a geological portfolio section."
        if classification=="AutoCadIntegrationFixture" else None}
