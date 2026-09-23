"""Versioned, source-bound multi-lithology inputs for the regional generator.

Vocabulary presence is not occurrence evidence. Map-unit member lists are not
observed vertical sequences. Every run reloads its serialized input before
selection and binds it to the exact plan evidence and vocabulary used.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

DATA_DIRECTORY = Path(__file__).resolve().parent / "data"
SCHEMA = "RegionalLithologyInput-1.0"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:raise ValueError("DuplicateJsonKey:" + key)
        result[key] = value
    return result


def read_json(path):
    path = Path(path)
    if path.is_symlink() or getattr(path, "is_junction", lambda:False)():
        raise ValueError("LinkedRegionalDataRejected")
    if not path.is_file() or path.stat().st_size > 20_000_000:
        raise ValueError("MissingOrOversizedRegionalData")
    def reject(value):raise ValueError("NonFiniteJson:" + value)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=reject)


def load_vocabulary(path=None):
    data = read_json(path or DATA_DIRECTORY / "japan_lithology_vocabulary.json")
    if data.get("schemaVersion") != "JapanLithologyVocabulary-1.0":
        raise ValueError("UnsupportedLithologyVocabulary")
    keys = []
    for row in data.get("lithologies", []):
        for field in ("key", "ja", "en", "aliases", "domains"):
            if not row.get(field):raise ValueError("IncompleteLithologyVocabulary:" + field)
        keys.append(row["key"])
        for field in ("aliases", "domains"):
            if not isinstance(row[field], list) or not all(isinstance(v,str) and v.strip() for v in row[field]):
                raise ValueError("InvalidVocabularyList:" + field)
    if (not keys or len(set(keys)) != len(keys) or
            len(data.get("specificityOrder", [])) != len(keys) or
            set(data.get("specificityOrder", [])) != set(keys)):
        raise ValueError("DuplicateOrUnorderedLithologyVocabulary")
    for domain, groups in data.get("specializationGroups", {}).items():
        for group in groups:
            if not group.get("targets") or not set(group["keys"]) <= set(keys):
                raise ValueError("InvalidSpecializationGroup:" + domain)
    return data


def matching_keys(legend, vocabulary):
    if not isinstance(legend, dict):return []
    rows = {r["key"]:r for r in vocabulary["lithologies"]}
    # Ages, symbol letters and place names never create rock identities.
    text = " ".join(str(legend.get(k, "")) for k in ("lithology_ja", "lithology_en")).casefold()
    spans = {key:[m.span() for alias in row["aliases"]
                  for m in re.finditer(re.escape(alias.casefold()), text)]
             for key, row in rows.items()}
    # Suppress substring matches, not separate named occurrences (e.g.
    # granodiorite AND diorite must retain both).
    for specific, general in vocabulary.get("aliasShadowing", []):
        spans[general] = [(a,b) for a,b in spans[general]
                          if not any(c <= a and b <= d for c,d in spans[specific])]
    return [key for key in vocabulary["specificityOrder"] if spans[key]]


def plan_evidence(plan):
    # Exclude render paths and derived classifications. Preserve source bytes'
    # digests, coordinates, dates and the complete original legend labels.
    return {"routeLonLat":plan.get("routeLonLat", []),
            "surfaceGeology":plan.get("surfaceGeology", {}),
            "regionalBedrockNeighborhood":plan.get("regionalBedrockNeighborhood", {}),
            "layers":[r for r in plan.get("layers", []) if r.get("evidence_kind") == "SurfaceGeology"]}


def build_regional_dataset(plan, vocabulary=None):
    vocabulary = vocabulary or load_vocabulary()
    raw = plan_evidence(plan)
    rows = {r["key"]:r for r in vocabulary["lithologies"]}
    records = []; candidates = {}
    route = plan.get("routeLonLat", [])
    bbox = None
    if route:
        if any(not isinstance(p,(list,tuple)) or len(p) != 2 for p in route):
            raise ValueError("InvalidRegionalRoute")
        coords = [float(v) for p in route for v in p]
        if (not all(math.isfinite(v) for v in coords) or
                any(not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90) for p in route)):
            raise ValueError("InvalidRegionalRoute")
        bbox = [min(p[0] for p in route),min(p[1] for p in route),
                max(p[0] for p in route),max(p[1] for p in route)]
    for origin, samples in (("OnRoute", raw["surfaceGeology"].get("samples", [])),
                            ("Nearby", raw["regionalBedrockNeighborhood"].get("samples", []))):
        for index, sample in enumerate(samples):
            keys = matching_keys(sample.get("legend"), vocabulary)
            record_id = f"{origin}-{index:04d}"
            record = {"recordId":record_id, "origin":origin,
                      "sourceSample":copy.deepcopy(sample),
                      "location":{k:sample[k] for k in ("stationM","longitude","latitude","radiusM") if k in sample},
                      "sourceLabel":copy.deepcopy(sample.get("legend")),
                      "sourceId":sample.get("sourceId", raw["surfaceGeology"].get("sourceId", "Unverified")),
                      "sourceUrl":sample.get("url"), "rawResponseSha256":sample.get("sha256"),
                      "matchedKeys":keys, "basisType":("SyntheticTestEvidence" if
                          "Synthetic" in str(raw["surfaceGeology"].get("sourceEdition", "")) else "MappedSurfaceUnit"),
                      "subsurfaceObserved":False,
                      "memberRelation":"SourceMapUnitMembers_UnlocatedInternally" if len(keys)>1 else "SingleNamedMember"}
            records.append(record)
            for key in keys:
                c = candidates.setdefault(key, {"key":key,"labelJa":rows[key]["ja"],
                    "labelEn":rows[key]["en"],"domains":rows[key]["domains"],
                    "recordIds":[],"onRouteCount":0,"nearbyCount":0,
                    "occurrenceBasis":record["basisType"],"generatedGeometryBasis":"SyntheticAssumption"})
                c["recordIds"].append(record_id)
                c["onRouteCount" if origin=="OnRoute" else "nearbyCount"] += 1
    relations = [{"type":"MapUnitMemberAssociation_NotVerticalOrder",
                  "recordId":r["recordId"],"members":r["matchedKeys"],
                  "contactGeometryAuthorized":False} for r in records if len(r["matchedKeys"])>1]
    return {"schemaVersion":SCHEMA,"datasetId":"route-"+digest(raw)[:16],
            "vocabularyVersion":vocabulary["version"],"vocabularySha256":digest(vocabulary),
            "planEvidenceSha256":digest(raw),"spatialApplicability":{"routeLonLat":route,"bboxLonLat":bbox,
                "scope":"ExactRouteAndRecordedNearbySamples","positionReference":"SourceLonLat_NotSurveyControl"},
            "sources":copy.deepcopy(raw["layers"]),"sourceEdition":raw["surfaceGeology"].get("sourceEdition","Unverified"),
            "candidates":[candidates[k] for k in sorted(candidates)],"records":records,"relations":relations,
            "selectionPolicy":{"keepAllEvidenceMatchedCandidates":True,"majorityOnlyFiltering":False,
                "regionNameDeterminesLithology":False,"unmatchedLabelsRetained":True,
                "mappedOccurrenceProvesBuriedDepth":False,"unresolvedPlacementMustBeReported":True},
            "vocabularyMatching":"NonExhaustive_OriginalSourceLabelsRetained",
            "coverageClaim":"SampledRouteAndLocalContext_NotNationwideInventory"}


def validate_regional_dataset(data, plan, vocabulary=None):
    vocabulary = vocabulary or load_vocabulary()
    if data.get("schemaVersion") != SCHEMA:raise ValueError("UnsupportedRegionalInput")
    if data.get("vocabularySha256") != digest(vocabulary):raise ValueError("RegionalVocabularyChanged")
    if data.get("planEvidenceSha256") != digest(plan_evidence(plan)):
        raise ValueError("RegionalInputDoesNotMatchRouteEvidence")
    # Reconstruct from authoritative input fields, not self-declared candidates.
    if data != build_regional_dataset(plan, vocabulary):
        raise ValueError("RegionalCandidateOrRelationBindingMismatch")
    return data


def write_and_load_regional_dataset(plan, path):
    vocabulary = load_vocabulary()
    data = build_regional_dataset(plan, vocabulary)
    path = Path(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    loaded = validate_regional_dataset(read_json(path), plan, vocabulary)
    plan["regionalLithologyInput"] = loaded
    plan["regionalLithologyInputFile"] = {"filename":path.name,
        "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "dataSha256":digest(loaded),"reloadedBeforeGeneration":True}
    return loaded


def regional_dataset_for_plan(plan):
    if "regionalLithologyInput" in plan:
        return validate_regional_dataset(plan["regionalLithologyInput"], plan)
    # Library/unit-test callers also use the same data contract; production
    # always materializes and reloads the JSON file first.
    return build_regional_dataset(plan)


def composite_specializations(domain, evidence):
    """Name all compatible members without inventing their internal contacts."""
    vocabulary = load_vocabulary()
    by_key = {r["key"]:r for r in vocabulary["lithologies"]}
    keys = set(evidence.get("selectedKeys", [evidence["selectedKey"]] if evidence.get("selectedKey") else []))
    result = {}
    for group in vocabulary.get("specializationGroups", {}).get(domain, []):
        members = [k for k in group["keys"] if k in keys]
        if not members:continue
        for target in group["targets"]:
            ja = "・".join(by_key[k]["ja"] for k in members)
            en = " / ".join(by_key[k]["en"] for k in members)
            templates = vocabulary.get("targetTemplates", {}).get(target)
            result[target] = {"memberKeys":members,
                "ja":(templates[0].format(members=ja) if templates else ja+group["suffixJa"])+"（地域推定）",
                "en":(templates[1].format(members=en) if templates else en+(" "+group["suffixEn"] if group["suffixEn"] else ""))+" (regionally inferred)",
                "representation":"CompositeRockPackage_InternalContactsUnresolved" if len(members)>1 else "NamedRockPackage"}
    return result


def selection_accounting(data, domain, rows, replacements, bedrock=None, geometric_ids=None):
    ids = {row[0] for row in rows}
    geometric_ids = set(geometric_ids) if geometric_ids is not None else ids
    result = []
    for candidate in data["candidates"]:
        key = candidate["key"]
        targets = [target for target, spec in replacements.items() if key in spec["memberKeys"] and target in ids]
        chosen = (bedrock or {}).get("selected")
        is_base = chosen and key in chosen.get("memberKeys", [chosen["key"]])
        if is_base and domain=="UnconsolidatedSedimentTerrain":targets.append(rows[-1][0])
        if targets:
            status=("RepresentedByRegionalPrior" if set(targets) & geometric_ids else
                    "RetainedAsUnlocatedCompositionPart")
        elif domain not in candidate["domains"]:
            status="Retained_RequiresDifferentGeologicalArchitecture"
        else:
            status="Retained_ExistingDomainPriorOrPlacementUnresolved"
        result.append({"key":key,"status":status,"unitIds":sorted(set(targets)),
                       "geometricUnitIds":sorted(set(targets) & geometric_ids),
                       "sourceRecordIds":candidate["recordIds"],"undergroundObservationClaim":False})
    return {"schemaVersion":"RegionalLithologySelectionAccounting-1.0", "candidateCount":len(result),
            "allCandidatesAccountedFor":len(result)==len(data["candidates"]),"findings":result,
            "allCandidateInternalContactsResolved":False}
