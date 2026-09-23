"""State and information-architecture gate for the Advanced V2 GUI."""
from dataclasses import dataclass
PRIMARY_GROUPS=("Location","SectionRoute","Output","Generate","ValidationStatus")
ADVANCED_GROUPS=("Sampling","Randomness","Drawing","Diagnostics")
@dataclass(frozen=True)
class DisclosureState:
    expanded: bool=False
    @property
    def button_text(self):return "▲ 詳細設定を隠す" if self.expanded else "▼ 詳細設定を表示"
    @property
    def help_text(self):return ("標本間隔、seed、境界線、目盛密度を表示しています。" if self.expanded else "通常は地域・測線・出力先だけで生成できます。")
    def toggled(self):return DisclosureState(not self.expanded)
def audit_information_architecture(primary=PRIMARY_GROUPS,advanced=ADVANCED_GROUPS):
    overlap=sorted(set(primary).intersection(advanced));missing=sorted(set(PRIMARY_GROUPS)-set(primary))
    return {"schemaVersion":"AdvancedV2GuiInformationArchitecture-1.0","passed":not overlap and not missing,
            "duplicates":overlap,"missingPrimaryGroups":missing,"primaryCount":len(tuple(primary)),"advancedCount":len(tuple(advanced))}
