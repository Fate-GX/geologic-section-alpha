"""Replay the explicitly synthetic public fixture through the alpha pipeline."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
ADV=ROOT/'app/subprojects/geologic_3d_engine/advanced_v2'
sys.dont_write_bytecode=True
sys.path[:0]=[str(ADV),str(ADV.parent),str(ROOT/'tools')]
from route_request import AdvancedJapanSectionRequest
from nationwide_pipeline import run_advanced_japan_section
from geologic_3d_engine.export.contract_integrity import verify_integrity_envelope

def replay(output,native=False):
    fixture=ROOT/'examples/synthetic_plain/input.json'
    data=json.loads(fixture.read_text(encoding='utf-8'))
    request=AdvancedJapanSectionRequest.from_endpoints(*data['endpointsLonLat'],seed=data['seed'])
    def acquire(_root,route,spacing,destination,*unused):
        Path(destination,'plan_evidence_bundle.json').write_text(json.dumps(data['plan'],ensure_ascii=False),encoding='utf-8')
    def pipeline(root,req,out):
        return run_advanced_japan_section(root,req,out,acquire_plan=acquire,native_dwg=native)
    if native:
        from operator_ui import run_section
        result=run_section(ROOT/'app',request,output,pipeline=pipeline)
    else:result=pipeline(ROOT/'app',request,output)
    if not result.get('passed'):raise RuntimeError(json.dumps(result,ensure_ascii=True))
    run=Path(result['manifestPath']).parent
    model=next(run.rglob('model.json'))
    envelope=next(run.rglob('native_dwg_contract_envelope.json'))
    payload,_=verify_integrity_envelope(json.loads(envelope.read_text(encoding='utf-8'))['geologicContractEnvelope'])
    semantic={'polygons':payload['polygons'],'terrainLine':payload['terrainLine']}
    fingerprint=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    summary={'syntheticInput':True,'realSiteEvidence':False,'seed':data['seed'],
        'inputSha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
        'geometrySha256':fingerprint,'nativeRequested':native,'pipelinePassed':True,
        'nativeSuccess':native,'scope':'Software reproduction only; not geological certification'}
    expected=fixture.with_name('expected.json')
    if expected.is_file():
        old=json.loads(expected.read_text(encoding='utf-8'))
        if old['geometrySha256']!=fingerprint:raise RuntimeError('SampleGeometryMismatch')
        summary['expectedGeometryMatched']=True
    (run/'public_sample_check.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'runDirectory':str(run),**summary},ensure_ascii=True))
    return run,summary

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'results/public_sample')
    parser.add_argument('--native',action='store_true',help='Windows + AutoCAD 2027 required; creates a new DWG')
    args=parser.parse_args()
    replay(args.output,args.native)
