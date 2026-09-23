from __future__ import annotations
import argparse,json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
from advanced_visual_qa import plot_disposable_layout_pdfs

def main():
    parser=argparse.ArgumentParser();parser.add_argument("summary",type=Path);parser.add_argument("output",type=Path)
    args=parser.parse_args();data=json.loads(args.summary.read_text(encoding="utf-8"));records=[]
    for row in data["results"]:
        dwg=next(Path(item["path"]) for item in row["artifacts"] if item["path"].lower().endswith(".dwg"))
        folder=args.output/row["case"]
        pdfs=plot_disposable_layout_pdfs(dwg,folder)
        records.append({"case":row["case"],"sourceDwg":str(dwg),"pdfs":[str(path) for path in pdfs]})
    args.output.mkdir(parents=True,exist_ok=True)
    manifest=args.output/"layout_pdf_manifest.json"
    manifest.write_text(json.dumps({"schemaVersion":"TerrainMatrixLayoutPdfQA-1.0","records":records},indent=2),encoding="utf-8")
    print(manifest)
if __name__=="__main__":main()
