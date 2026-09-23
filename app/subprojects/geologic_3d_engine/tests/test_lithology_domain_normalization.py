import unittest
from geologic_3d_engine.section.lithology_domain_normalization import (compare_cross_domain_material_terms,
    normalize_borehole_field_terms,normalize_mapped_unit_terms)


class LithologyDomainNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.bp={"schemaVersion":"BoreholeLithologyTerminologyProfile-1.0","profileId":"BP","terms":[{
            "sourceLabel":"火山灰質粘性土","normalizedLabelJa":"火山灰質粘性土","normalizedLabelEn":"volcanic-ash cohesive soil",
            "broadMaterialClass":"VolcanicAshSoil","fieldSymbol":"V","termStatus":"Current",
            "formalEngineeringClassificationAuthorized":False,"normalizationNote":"field description"}]}
        self.mp={"profileId":"ASO_VOLCANO_MAP_1985_TERMINOLOGY_V1","terms":[{
            "SourceCode":"a","NormalizedUnitLabelJa":"降下火山灰堆積物","NormalizedUnitLabelEn":"air-fall volcanic-ash deposit",
            "NormalizedLithologies":["volcanic ash"],"VocabularyUris":[],"TermStatus":"DerivedDisplayLabel","NormalizationNote":"map unit"}]}
    def test_domains_remain_separate_and_association_is_not_identity(self):
        bore=normalize_borehole_field_terms({"boreholes":[{"intervals":[{"sourceLabel":"火山灰質粘性土"}]}]},self.bp)
        mapped=normalize_mapped_unit_terms({"units":[{"unitId":"M","symbol":"a"}]},self.mp)
        result=compare_cross_domain_material_terms(bore["boreholes"][0]["intervals"][0],mapped["units"][0])
        self.assertEqual(result["status"],"GeneticMaterialAssociationOnly_NotUnitIdentity")
        self.assertFalse(result["geologicalUnitIdentityEstablished"]);self.assertFalse(result["geometryAuthorizationGranted"])
    def test_unknown_terms_remain_unmapped(self):
        bore=normalize_borehole_field_terms({"boreholes":[{"intervals":[{"sourceLabel":"unknown"}]}]},self.bp)
        mapped=normalize_mapped_unit_terms({"units":[{"unitId":"M","symbol":"x"}]},self.mp)
        self.assertEqual(bore["boreholes"][0]["intervals"][0]["domainNormalizationStatus"],"UnmappedSourceLabel")
        self.assertEqual(mapped["units"][0]["domainNormalizationStatus"],"UnmappedSourceCode")
