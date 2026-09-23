"""Apply an exact, source-preserving borehole terminology profile."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


_TERM_STATUSES = {"Current", "Legacy", "LocalRelativeUnit",
                  "DerivedDisplayLabel", "Unverified", "Deprecated"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def normalize_borehole_terminology(collection: Mapping, profile: Mapping):
    """Return a new collection; never overwrite the observed source label.

    A profile match authorizes terminology display only. It cannot upgrade
    evidence, correlation, collar accuracy, or section-constraint status.
    """
    if not isinstance(collection, Mapping) or not isinstance(profile, Mapping):
        raise ValueError("collection and terminology profile must be objects")
    if profile.get("schemaVersion") != "BoreholeLithologyTerminologyProfile-1.0":
        raise ValueError("unsupported terminology profile")
    required_profile = {"profileId", "scope", "sourceAuthority", "sourceIds",
                        "sourceUrls", "vocabularyVersion", "classificationBoundary",
                        "terms", "authorizationBoundary"}
    if not required_profile.issubset(profile):
        raise ValueError("terminology profile is incomplete")
    if profile["authorizationBoundary"] != (
            "TerminologyDisplayOnly_NoUnitCorrelationOrGeologicalGeometryAuthorization"):
        raise ValueError("terminology profile overstates authorization")
    if not isinstance(profile["terms"], list) or not profile["terms"]:
        raise ValueError("terminology profile requires terms")
    by_source = {}
    for term in profile["terms"]:
        required = {"sourceLabel", "normalizedLabelJa", "normalizedLabelEn",
                    "broadMaterialClass", "fieldSymbol", "termStatus",
                    "formalEngineeringClassificationAuthorized", "normalizationNote"}
        if not isinstance(term, Mapping) or not required.issubset(term):
            raise ValueError("terminology entry is incomplete")
        label = term["sourceLabel"]
        if not isinstance(label, str) or not label.strip() or label in by_source:
            raise ValueError("terminology source labels must be unique non-empty strings")
        if term["termStatus"] not in _TERM_STATUSES:
            raise ValueError("invalid terminology status")
        if term["formalEngineeringClassificationAuthorized"] is not False:
            raise ValueError("field descriptions cannot claim formal classification")
        by_source[label] = dict(term)

    holes = collection.get("boreholes")
    if not isinstance(holes, list) or not holes:
        raise ValueError("collection requires boreholes")
    prior_authorization = collection.get("sectionConstraintAuthorized", False)
    if not isinstance(prior_authorization, bool):
        raise ValueError("sectionConstraintAuthorized must be boolean")
    output_holes = []
    unresolved = []
    for hole in holes:
        if not isinstance(hole, Mapping) or not isinstance(hole.get("intervals"), list):
            raise ValueError("borehole intervals are missing")
        intervals = []
        for index, interval in enumerate(hole["intervals"]):
            if not isinstance(interval, Mapping) or not isinstance(interval.get("sourceLabel"), str):
                raise ValueError("interval source label is missing")
            original = interval["sourceLabel"]
            match = by_source.get(original)
            if match is None:
                unresolved.append({"boreholeId": hole.get("boreholeId"),
                                   "intervalIndex": index, "sourceLabel": original})
                intervals.append({**interval, "normalizedLithology": original,
                                  "termStatus": "Unverified",
                                  "terminologyMatchState": "Unresolved",
                                  "normalizationNote": "No exact profile term; source label retained."})
            else:
                intervals.append({**interval,
                    "sourceLabel": original,
                    "normalizedLithology": match["normalizedLabelJa"],
                    "normalizedLithologyEn": match["normalizedLabelEn"],
                    "broadMaterialClass": match["broadMaterialClass"],
                    "fieldSymbol": match["fieldSymbol"],
                    "termStatus": match["termStatus"],
                    "formalEngineeringClassificationAuthorized": False,
                    "terminologyMatchState": "ExactSourceLabel",
                    "normalizationAuthority": profile["sourceAuthority"],
                    "vocabularyVersion": profile["vocabularyVersion"],
                    "normalizationNote": match["normalizationNote"]})
        output_holes.append({**hole, "intervals": intervals})
    result = {**collection, "boreholes": output_holes,
              "terminologyProfileId": profile["profileId"],
              "terminologyProfileSha256": hashlib.sha256(_canonical(profile)).hexdigest(),
              "terminologyNormalizationState": (
                  "CompleteExactLabelCoverage" if not unresolved else "PartialUnresolved"),
              "unresolvedTerminology": unresolved,
              "sectionConstraintAuthorized": prior_authorization,
              "terminologyAuthorizationBoundary": profile["authorizationBoundary"]}
    return result
