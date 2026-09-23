"""Reusable synthetic priors selected from mapped geological domains."""
from __future__ import annotations

DOMAIN_MODELS = {
 "VolcanicTerrain":{"architectureType":"VolcanicPaleosurfaceStack","facies":(
  ("SYN-SURFACE-COVER","表土・薄層火山灰被覆（推定）",2.0,"#8f7659"),
  ("SYN-TEPHRA-SCORIA","降下火砕物・スコリア質層（推定）",7.0,"#b58a62"),
  ("SYN-LAVA-BRECCIA","溶岩・火山角礫岩互層（推定）",15.0,"#806c75"),
  ("SYN-ANDESITE-LAVA","中性火山岩質溶岩（推定）",22.0,"#625f68"),
  ("SYN-PYROCLASTIC","火砕岩・凝灰角礫岩（推定）",28.0,"#9a8174"),
  ("SYN-OLDER-VOLCANIC","旧期火山岩類・表示基底（推定）",75.0,"#514e52"))},
 "SedimentaryRockTerrain":{"architectureType":"DeformedSedimentaryStack","facies":(
  ("SYN-SURFACE-COVER","表土・崩積性被覆（推定）",2.0,"#a58b68"),
  ("SYN-SILTSTONE","シルト岩優勢層（推定）",10.0,"#a9aaa0"),
  ("SYN-SANDSTONE","砂岩優勢層（推定）",17.0,"#d2b46d"),
  ("SYN-MUDSTONE","泥岩優勢層（推定）",20.0,"#84928e"),
  ("SYN-CONGLOMERATE","礫岩・砂岩互層（推定）",24.0,"#a17c61"),
  ("SYN-OLDER-SEDIMENTARY","旧期堆積岩類・表示基底（推定）",75.0,"#676a68"))},
 "AccretionaryComplex":{"architectureType":"DeformedSedimentaryStack","facies":(
  ("SYN-SURFACE-COVER","表土・崩積性被覆（推定）",2.0,"#9b8264"),
  ("SYN-MUDSTONE-MATRIX","泥質岩基質（推定）",13.0,"#777f7f"),
  ("SYN-SANDSTONE-BLOCK","砂岩優勢岩体（推定）",17.0,"#b89d68"),
  ("SYN-CHERT-BLOCK","チャート質岩体（推定）",14.0,"#8e7770"),
  ("SYN-MIXED-ROCK","混在岩相（推定）",24.0,"#686d70"),
  ("SYN-OLDER-COMPLEX","旧期付加体・表示基底（推定）",75.0,"#51565a"))},
 "PlutonicTerrain":{"architectureType":"PlutonicWeatheringMass","facies":(
  ("SYN-SURFACE-COVER","表土・崩積性被覆（推定）",1.8,"#9c8262"),
  ("SYN-MASADO","まさ状風化帯（母岩状態・推定）",4.0,"#d0b98a"),
  ("SYN-WEATHERED-PLUTON","風化深成岩体（推定）",9.0,"#b6a48e"),
  ("SYN-FRACTURED-PLUTON","割れ目を伴う深成岩体（推定）",17.0,"#9a8e82"),
  ("SYN-FRESH-PLUTON","比較的新鮮な深成岩体（推定）",34.0,"#817b76"),
  ("SYN-DEEP-PLUTON","深成岩体・表示基底（推定）",75.0,"#686563"))},
 "MetamorphicBelt":{"architectureType":"DeformedSedimentaryStack","facies":(
  ("SYN-SURFACE-COVER","表土・崩積性被覆（推定）",2.0,"#9b8264"),
  ("SYN-WEATHERED-METAMORPHIC","風化変成岩帯（推定）",8.0,"#958b80"),
  ("SYN-PELMET","泥質変成岩優勢帯（推定）",16.0,"#77767b"),
  ("SYN-PSAMMET","砂質変成岩優勢帯（推定）",20.0,"#9b8d78"),
  ("SYN-MIXED-METAMORPHIC","片理を伴う混合変成岩帯（推定）",28.0,"#686a72"),
  ("SYN-DEEP-METAMORPHIC","変成岩類・表示基底（推定）",75.0,"#52545b"))}}

def select_domain_model(domain):
 model=DOMAIN_MODELS.get(domain)
 if model is None:return {"architectureType":"DefaultRelativeDepthStack","facies":None,"selectionStatus":"NoSpecificReusableModel"}
 return {"architectureType":model["architectureType"],"facies":[list(row) for row in model["facies"]],
  "selectionStatus":"ReusableDomainPriorSelected","basisType":"SyntheticAssumption",
  "subsurfaceMeaning":"PriorOnly_NotObservedLocalSequence"}
