import hashlib,json,unittest
from geologic_3d_engine.section.mapped_unit_catalog import build_mapped_unit_catalog


def signed():
    unit=lambda fid,label,en:{"sourcePolygonFeatureId":fid,"majorCode":1.0,"symbol":str(fid),
        "legends":[{"level":3,"sourceLabel":"完新世","sourceLabelEnglish":"Holocene"},
                   {"level":7,"sourceLabel":label,"sourceLabelEnglish":en}]}
    value={"schemaVersion":"GsjRouteCrossingSideClassification-1.0","sourceId":"MAP",
        "crossings":[{"featureId":"C1","stationM":10,"sideClassificationStatus":"MappedUnitTransition","unitPair":[unit(2,"火山灰","Volcanic ash"),unit(3,"軽石","Pumice")]},
                     {"featureId":"C2","stationM":20,"sideClassificationStatus":"MappedUnitTransition","unitPair":[unit(3,"軽石","Pumice"),unit(2,"火山灰","Volcanic ash")]}]}
    value["recordSha256"]=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest();return value


class MappedUnitCatalogTests(unittest.TestCase):
    def test_deduplicates_source_features_and_preserves_route_order(self):
        result=build_mapped_unit_catalog(signed(),source_year="1985",source_authority="GSJ",vocabulary_version="1985 source translation")
        self.assertEqual(result["unitCount"],2);self.assertEqual(result["transitionCount"],2)
        self.assertEqual(result["units"][0]["sourceLabel"],"火山灰")
        self.assertEqual(result["units"][0]["termStatus"],"Unverified")
        self.assertEqual(result["units"][0]["numericAgeStatus"],"NotResolvedFromNamedSourceInterval")
        self.assertFalse(result["realRegionSubsurfaceAuthorized"])
        self.assertNotEqual(result["transitions"][0]["mappedUnitIdsInRouteOrder"],result["transitions"][1]["mappedUnitIdsInRouteOrder"])
    def test_hash_and_inconsistent_repeated_feature_reject(self):
        bad=signed();bad["recordSha256"]="0"*64
        with self.assertRaises(ValueError):build_mapped_unit_catalog(bad,source_year="1985",source_authority="GSJ",vocabulary_version="v")
        bad=signed();bad["crossings"][1]["unitPair"][0]["legends"][-1]["sourceLabelEnglish"]="Other"
        unsigned={k:v for k,v in bad.items() if k!="recordSha256"};bad["recordSha256"]=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        with self.assertRaises(ValueError):build_mapped_unit_catalog(bad,source_year="1985",source_authority="GSJ",vocabulary_version="v")
