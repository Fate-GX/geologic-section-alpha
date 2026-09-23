"""Stage-12 declared-use and publication-evidence contract."""

from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED=("regionalProfile","citedUnitOrder","meaningfulVisibleLines","geologicalTopology",
 "terrainAndControls","titleAndSectionId","directions","horizontalScale","verticalScale",
 "verticalExaggeration","datumAndUnits","bilateralElevationTicks","completeLegend",
 "unitDescriptions","symbolExplanation","creditsAndSources","visibleSyntheticDisclaimer",
 "nativeEntities","associativeSolidHatches","exclusivePolygonPartition","hatchDrawOrder",
 "documentedLayers","separateLanguageLayouts","lockedViewports","fontPersistence",
 "textCollisionReview","grayscaleReview","colorVisionReview","namedPageSetup","plotStyle",
 "pdfVisualReview","rasterVisualReview","dwgReopenValidation","archivedSourcesAndLicenses",
 "dwgSyntheticMetadata")

@dataclass(frozen=True)
class ReleaseSpec:
    intended_use:str
    checks:dict
    reviewer:str
    artifact_path:str
    @classmethod
    def from_dict(cls,data): return cls(str(data.get("intendedUse","")),dict(data.get("checks",{})),
      str(data.get("reviewer","")),str(data.get("artifactPath","")))
    def validate(self):
        if self.intended_use not in {"IntegrationFixture","SyntheticPortfolioPublication"}:
            raise ValueError("unsupported intendedUse")
        if not self.reviewer or not self.artifact_path: raise ValueError("reviewer and artifactPath are required")
        unknown=set(self.checks)-set(REQUIRED)
        if unknown: raise ValueError(f"unknown release checks: {sorted(unknown)}")
        if any(not isinstance(v,bool) for v in self.checks.values()): raise ValueError("release checks must be boolean")
        return self

def load_release_spec(path:str|Path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,dict): raise ValueError("release specification root must be an object")
    return ReleaseSpec.from_dict(data)
