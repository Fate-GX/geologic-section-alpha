from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
from nationwide_pipeline import run_advanced_japan_section
from route_request import AdvancedJapanSectionRequest

# Dataset-specific smoke locations only.  They are deliberately outside the
# universal classifier and do not encode geological conclusions.
CASES={
    "coastal_lowland":(140.15,35.55,90.0),
    "boso_hills":(140.10,35.45,90.0),
    "yatsugatake_mountain":(138.37,35.95,90.0),
    "mountain_valley":(137.65,36.25,90.0),
}

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--case",choices=["all",*CASES],default="all")
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    root=HERE.parents[2];selected=CASES if args.case=="all" else {args.case:CASES[args.case]}
    results=[]
    for index,(name,(longitude,latitude,azimuth)) in enumerate(selected.items()):
        request=AdvancedJapanSectionRequest(longitude,latitude,500.0,azimuth,10.0,
                                             890100+index,"Show",True,"Standard")
        result=run_advanced_japan_section(root,request,args.output,native_dwg=False)
        results.append({"case":name,"request":request.to_dict(),"result":result})
    path=args.output/f"live_terrain_smoke_{args.case}.json"
    path.write_text(json.dumps({"schemaVersion":"AdvancedLiveTerrainSmoke-1.0",
        "datasetSpecificTestOnly":True,"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    print(path)

if __name__=="__main__":main()
