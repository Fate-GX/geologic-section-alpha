"""Stage-12 release classification without conflating fixture and portfolio acceptance."""

from .validation.release_validation import validate_release

def run_stage_twelve(release_spec,dwg_validation):
    try: result=validate_release(release_spec,dwg_validation)
    except Exception as error:
        return {"passed":False,"decision":"Rejected","stage":"release_validation",
          "errors":[{"code":"ReleaseValidationFailed","message":str(error)}]}
    # `passed` means the declared use passed, not that portfolio publication passed.
    declared_pass=(result["portfolioReleasePassed"] if release_spec.intended_use=="SyntheticPortfolioPublication"
                   else result["integrationFixturePassed"])
    return {"passed":declared_pass,"decision":result["decision"],"stage":"release_validation",
      "errors":[],"gates":[result],"releaseValidation":result}

def stage_twelve_manifest(result):
    gate=result.get("releaseValidation",{})
    return {"stage":result["stage"],"passed":result["passed"],"decision":result["decision"],
      "errors":result.get("errors",[]),"gates":result.get("gates",[]),
      "artifactClassification":gate.get("artifactClassification"),
      "portfolioReleasePassed":gate.get("portfolioReleasePassed",False),
      "integrationFixturePassed":gate.get("integrationFixturePassed",False),
      "nextAuthorizedStage":None}
