"""Normalize borehole and map terms while preserving classification domains."""
from __future__ import annotations

import copy
from collections.abc import Mapping


def normalize_borehole_field_terms(collection:Mapping,profile:Mapping):
    if profile.get("schemaVersion")!="BoreholeLithologyTerminologyProfile-1.0":raise ValueError("borehole terminology profile is invalid")
    terms={x.get("sourceLabel"):x for x in profile.get("terms",[]) if isinstance(x,Mapping)}
    if None in terms or len(terms)!=len(profile.get("terms",[])):raise ValueError("borehole terminology keys must be unique")
    result=copy.deepcopy(collection);matched=0
    for hole in result.get("boreholes",[]):
        for interval in hole.get("intervals",[]):
            term=terms.get(interval.get("sourceLabel"))
            interval["terminologyDomain"]="EngineeringGeotechnicalFieldDescription"
            interval["terminologyProfileId"]=profile.get("profileId")
            if term is None:
                interval["domainNormalizationStatus"]="UnmappedSourceLabel";continue
            interval.update({"normalizedLithology":term["normalizedLabelEn"],
                "normalizedLabelJa":term["normalizedLabelJa"],"broadMaterialClass":term["broadMaterialClass"],
                "fieldSymbol":term["fieldSymbol"],"termStatus":term["termStatus"],
                "formalEngineeringClassificationAuthorized":term["formalEngineeringClassificationAuthorized"],
                "normalizationNote":term["normalizationNote"],"domainNormalizationStatus":"ExactSourceLabelMatch"})
            matched+=1
    result["terminologyDomain"]="EngineeringGeotechnicalFieldDescription"
    result["domainNormalizedIntervalCount"]=matched
    result["authorizationBoundary"]="FieldDescriptionNormalizationOnly_NoGeologicalUnitCorrelation"
    return result


def normalize_mapped_unit_terms(catalog:Mapping,profile:Mapping):
    if profile.get("profileId")!="ASO_VOLCANO_MAP_1985_TERMINOLOGY_V1":raise ValueError("mapped-unit terminology profile is invalid")
    terms={x.get("SourceCode"):x for x in profile.get("terms",[]) if isinstance(x,Mapping)}
    if None in terms or len(terms)!=len(profile.get("terms",[])):raise ValueError("mapped terminology source codes must be unique")
    result=copy.deepcopy(catalog);matched=0
    for unit in result.get("units",[]):
        unit["terminologyDomain"]="GeologicalMapUnitAndPetrologicLithology"
        unit["terminologyProfileId"]=profile.get("profileId")
        term=terms.get(unit.get("symbol"))
        if term is None:
            unit["domainNormalizationStatus"]="UnmappedSourceCode";continue
        unit.update({"normalizedUnitLabelJa":term["NormalizedUnitLabelJa"],
            "normalizedUnitLabelEn":term["NormalizedUnitLabelEn"],
            "normalizedLithologies":term["NormalizedLithologies"],"vocabularyUris":term["VocabularyUris"],
            "termStatus":term["TermStatus"],"normalizationNote":term["NormalizationNote"],
            "domainNormalizationStatus":"ExactSourceCodeMatch"})
        matched+=1
    result["terminologyDomain"]="GeologicalMapUnitAndPetrologicLithology"
    result["domainNormalizedUnitCount"]=matched
    result["authorizationBoundary"]="DomainSeparatedTerminologyOnly_NoBoreholeCorrelation"
    return result


def compare_cross_domain_material_terms(borehole_interval:Mapping,mapped_unit:Mapping):
    if borehole_interval.get("terminologyDomain")!="EngineeringGeotechnicalFieldDescription" or mapped_unit.get("terminologyDomain")!="GeologicalMapUnitAndPetrologicLithology":
        raise ValueError("cross-domain comparison requires normalized engineering and map terms")
    broad=borehole_interval.get("broadMaterialClass");lithologies=set(mapped_unit.get("normalizedLithologies",[]))
    if broad=="VolcanicAshSoil" and "volcanic ash" in lithologies:
        status="GeneticMaterialAssociationOnly_NotUnitIdentity"
    elif broad=="VolcanicRock" and lithologies:
        status="BroadRockAssociationNeedsPetrologicEvidence"
    else:status="DifferentClassificationDomains_NotComparable"
    return {"status":status,"boreholeSourceLabel":borehole_interval.get("sourceLabel"),
        "mappedUnitId":mapped_unit.get("unitId"),"geologicalUnitIdentityEstablished":False,
        "geometryAuthorizationGranted":False,
        "reason":"Engineering field descriptions and geological map-unit/petrologic concepts answer different classification questions."}
