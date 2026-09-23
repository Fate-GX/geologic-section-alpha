import unittest

from geologic_3d_engine.section.gsj_adaptive_transition import (
    apply_transition_refinement, refine_surface_transition)


def legend(symbol):
    return {"symbol":symbol,"formationAge_ja":"age","formationAge_en":"age",
            "lithology_ja":"lith","lithology_en":"lith","title":symbol,
            "value":"010203","r":1,"g":2,"b":3}


def plan(left="A", right="B"):
    return {"terrainProfile":[
        {"stationM":0,"longitude":130.0,"latitude":32.0,"elevationM":100},
        {"stationM":100,"longitude":131.0,"latitude":33.0,"elevationM":110}],
      "surfaceGeology":{"transitions":[{"leftSymbol":left,"rightSymbol":right,
        "lowerStationM":20,"upperStationM":80,"estimatedStationM":50,
        "uncertaintyM":30,"locatorStatus":"IntervalCensoredBetweenPointQueries"}]}}


class AdaptiveTransitionTests(unittest.TestCase):
    def test_binary_refinement_preserves_queries_and_uncertainty(self):
        calls=[]
        def query(latitude, longitude):
            calls.append((latitude,longitude))
            return legend("A" if longitude < 130.63 else "B")
        result=refine_surface_transition(plan(),0,query,target_width_m=5)
        self.assertEqual(result["refinementStatus"],"ResolvedToRequestedBracket")
        self.assertLessEqual(result["refinedBracket"]["upperStationM"]-result["refinedBracket"]["lowerStationM"],5)
        self.assertEqual(len(result["queryTrace"]),4)
        self.assertEqual(calls[0],(32.5,130.5))
        self.assertEqual(result["reviewEligibility"],"Eligible")
        self.assertIn("NotExactMapLine",result["interpretationBoundary"])

    def test_third_unit_and_no_map_stop_without_usable_bracket(self):
        for response,status in [(legend("C"),"InterruptedByThirdMappedUnit"),
                                ({},"InterruptedByNoMappedUnit")]:
            with self.subTest(status=status):
                result=refine_surface_transition(plan(),0,lambda a,b:response)
                self.assertEqual(result["refinementStatus"],status)
                self.assertIsNone(result["refinedBracket"])
                self.assertEqual(result["reviewEligibility"],"Ineligible_AmbiguousTransition")

    def test_query_limit_and_invalid_contract_inputs(self):
        result=refine_surface_transition(plan(),0,lambda a,b:legend("A"),
                                         target_width_m=0.01,maximum_queries=2)
        self.assertEqual(result["refinementStatus"],"MaximumQueriesReached")
        self.assertEqual(len(result["queryTrace"]),2)
        for args in [(plan(None,"B"),0,lambda a,b:legend("A"),1,2),
                     (plan(),-1,lambda a,b:legend("A"),1,2),
                     (plan(),0,lambda a,b:legend("A"),0,2),
                     (plan(),0,lambda a,b:legend("A"),1,31)]:
            with self.subTest(args=args),self.assertRaises(ValueError):
                refine_surface_transition(*args)

    def test_artifact_bound_application_updates_only_selected_bracket(self):
        source=plan()
        refinement=refine_surface_transition(source,0,
            lambda latitude,longitude:legend("A" if longitude < 130.63 else "B"),5)
        updated=apply_transition_refinement(source,refinement)
        self.assertEqual(source["surfaceGeology"]["transitions"][0]["uncertaintyM"],30)
        self.assertLessEqual(updated["surfaceGeology"]["transitions"][0]["uncertaintyM"],2.5)
        self.assertEqual(len(updated["surfaceGeology"]["transitions"][0]["adaptiveRefinement"]["queryTrace"]),4)
        ambiguous=refine_surface_transition(source,0,lambda a,b:legend("C"))
        with self.assertRaises(ValueError):apply_transition_refinement(source,ambiguous)
        changed=plan();changed["terrainProfile"][0]["longitude"]=-1
        with self.assertRaises(ValueError):apply_transition_refinement(changed,refinement)


if __name__ == "__main__": unittest.main()
