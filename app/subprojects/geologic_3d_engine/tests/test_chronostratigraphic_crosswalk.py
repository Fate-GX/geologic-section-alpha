import hashlib,json,unittest
from geologic_3d_engine.section.chronostratigraphic_crosswalk import apply_named_age_crosswalk


def signed(value):
    value["recordSha256"]=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest();return value
def catalog():return signed({"schemaVersion":"MappedGeologicUnitCatalog-1.0","units":[{"unitId":"U","sourceAgeLabel":"更新世最後期−完新世","sourceAgeLabelEnglish":"Latest Pleistocene to Holocene"}],"realRegionSubsurfaceAuthorized":False})
def crosswalk():return signed({"schemaVersion":"ChronostratigraphicNamedAgeCrosswalk-1.0","targetTimeScaleAuthority":"ICS","targetTimeScaleVersion":"2026/06","mappings":[{
    "sourceLabel":"更新世最後期−完新世","sourceLabelEnglish":"Latest Pleistocene to Holocene",
    "youngerMa":0.0,"olderMa":0.129,"mappingStatus":"ConservativeEnvelope_NotExactUnitEquivalence",
    "targetUnits":["Upper Pleistocene","Holocene"],"sourceIds":["ICS-CHART-2026-06"]}]})


class ChronostratigraphicCrosswalkTests(unittest.TestCase):
    def test_applies_version_bound_conservative_envelope(self):
        result=apply_named_age_crosswalk(catalog(),crosswalk());age=result["units"][0]["geologicAgeInterval"]
        self.assertEqual(age["olderMa"],.129);self.assertEqual(age["youngerMa"],0)
        self.assertEqual(age["mappingStatus"],"ConservativeEnvelope_NotExactUnitEquivalence")
        self.assertFalse(result["realRegionSubsurfaceAuthorized"])
    def test_unmatched_label_remains_unmapped_and_tampering_rejects(self):
        source=catalog();source["units"][0]["sourceAgeLabel"]="別年代"
        unsigned={k:v for k,v in source.items() if k!="recordSha256"};source["recordSha256"]=hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(apply_named_age_crosswalk(source,crosswalk())["ageMappedUnitCount"],0)
        bad=crosswalk();bad["mappings"][0]["olderMa"]=1
        with self.assertRaises(ValueError):apply_named_age_crosswalk(catalog(),bad)
