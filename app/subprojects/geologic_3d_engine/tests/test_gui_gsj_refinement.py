import json
import tempfile
import unittest
from pathlib import Path

from geologic_3d_engine.gui_gsj_refinement import execute_gsj_refinement


def legend(symbol):
    return {"symbol":symbol,"formationAge_ja":"age","formationAge_en":"age",
      "lithology_ja":"lith","lithology_en":"lith","title":symbol,
      "value":"010203","r":1,"g":2,"b":3}


class GuiGsjRefinementTests(unittest.TestCase):
    def test_persists_refined_plan_and_ready_review_template(self):
        plan={"terrainProfile":[
          {"stationM":0,"longitude":130,"latitude":32,"elevationM":100},
          {"stationM":100,"longitude":131,"latitude":33,"elevationM":110}],
          "surfaceGeology":{"transitions":[{"leftSymbol":"A","rightSymbol":"B",
          "lowerStationM":20,"upperStationM":80,"estimatedStationM":50,
          "uncertaintyM":30,"locatorStatus":"IntervalCensoredBetweenPointQueries"}]}}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/"plan.json"
            source.write_text(json.dumps(plan),encoding="utf-8")
            result,artifact,refined,template=execute_gsj_refinement(source,0,5,root,
                lambda latitude,longitude:legend("A" if longitude<130.63 else "B"))
            self.assertTrue(artifact.is_file() and refined.is_file() and template.is_file())
            candidate=json.loads(template.read_text(encoding="utf-8"))["candidates"][0]
            self.assertLessEqual(candidate["uncertaintyM"],2.5)
            self.assertEqual(result["refinementStatus"],"ResolvedToRequestedBracket")

    def test_ambiguous_result_persists_audit_but_not_usable_outputs(self):
        plan={"terrainProfile":[
          {"stationM":0,"longitude":130,"latitude":32,"elevationM":100},
          {"stationM":100,"longitude":131,"latitude":33,"elevationM":110}],
          "surfaceGeology":{"transitions":[{"leftSymbol":"A","rightSymbol":"B",
          "lowerStationM":20,"upperStationM":80}]}}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/"plan.json"
            source.write_text(json.dumps(plan),encoding="utf-8")
            result,artifact,refined,template=execute_gsj_refinement(source,0,5,root,
                lambda latitude,longitude:legend("C"))
            self.assertTrue(artifact.is_file());self.assertIsNone(refined);self.assertIsNone(template)
            self.assertEqual(result["reviewEligibility"],"Ineligible_AmbiguousTransition")


if __name__=="__main__":unittest.main()
