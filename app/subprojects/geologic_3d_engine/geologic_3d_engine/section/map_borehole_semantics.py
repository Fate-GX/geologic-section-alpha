"""Evidence-safe comparison of mapped geology and a borehole log."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def compare_mapped_geology_to_borehole(
    mapped_polygon: Mapping,
    borehole: Mapping,
    *,
    reviewed_binding: Mapping | None = None,
) -> dict:
    """Compare distinct representation depths without guessing lithology synonyms.

    A geological-map polygon describes mapped geology beneath topsoil at map
    scale.  A borehole describes a vertical sequence at one point.  Therefore a
    text resemblance cannot, by itself, bind a map unit to a core interval.
    """
    matches = mapped_polygon.get("matches")
    intervals = borehole.get("intervals")
    if not isinstance(matches, Sequence) or len(matches) != 1:
        raise ValueError("exactly one containing mapped polygon is required")
    if not isinstance(intervals, Sequence) or not intervals:
        raise ValueError("at least one borehole interval is required")

    base = {
        "mapRepresentation": "MappedSubTopsoilGeologyAtMapScale",
        "boreholeRepresentation": "ObservedVerticalSequenceAtPoint",
        "mapSourceId": mapped_polygon.get("sourceId"),
        "boreholeSourceId": borehole.get("sourceId"),
        "thicknessAuthorized": False,
        "contactGeometryAuthorized": False,
        "subsurfaceContinuationAuthorized": False,
    }
    if reviewed_binding is None:
        return {**base, "status": "NeedsReviewedLithologyBinding",
                "selectedIntervalIndex": None}

    required = {"mapSourceId", "boreholeSourceId", "intervalIndex",
                "relation", "reviewStatus"}
    if not required.issubset(reviewed_binding):
        raise ValueError("reviewed binding is incomplete")
    if reviewed_binding["mapSourceId"] != base["mapSourceId"] or \
       reviewed_binding["boreholeSourceId"] != base["boreholeSourceId"]:
        raise ValueError("reviewed binding source mismatch")
    index = reviewed_binding["intervalIndex"]
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(intervals):
        raise ValueError("reviewed binding intervalIndex is invalid")
    if reviewed_binding["reviewStatus"] != "IndependentlyReviewed":
        return {**base, "status": "NeedsIndependentReview",
                "selectedIntervalIndex": index}
    relation = reviewed_binding["relation"]
    if relation not in {
        "CompatibleCoverCategory_NotStratigraphicIdentity",
        "CompatibleAtDifferentRepresentationDepth",
        "Conflict",
        "Unresolved",
    }:
        raise ValueError("unsupported reviewed relation")
    return {**base, "status": relation, "selectedIntervalIndex": index,
            "selectedInterval": dict(intervals[index]),
            "bindingEvidence": dict(reviewed_binding)}
