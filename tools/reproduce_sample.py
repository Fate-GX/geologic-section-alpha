"""Replay the explicitly synthetic public fixture through the alpha pipeline."""
import argparse
import hashlib
import json
import math
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

# One micrometre: numerical replay tolerance, NOT geological accuracy.
# Only coordinate leaves use this absolute tolerance (no relative tolerance).
COORDINATE_ATOL_M = 1e-6

def compare_geometry(expected, actual):
    errors=[]
    maximum=0.0
    def walk(a,b,path,coordinate=False):
        nonlocal maximum
        if isinstance(a,dict) and isinstance(b,dict):
            if a.keys()!=b.keys():
                errors.append(path+':keys');return
            for key in a:
                walk(a[key],b[key],path+'/'+key,
                     coordinate or key in ('vertices','terrainLine'))
        elif isinstance(a,list) and isinstance(b,list):
            if len(a)!=len(b):
                errors.append(path+':length');return
            for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+'/'+str(i),coordinate)
        elif coordinate and type(a) in (int,float) and type(b) in (int,float):
            if not math.isfinite(a) or not math.isfinite(b):
                errors.append(path+':nonfinite');return
            delta=abs(a-b)
            maximum=max(maximum,delta)
            if delta>COORDINATE_ATOL_M:errors.append(path+':coordinate')
        elif type(a)!=type(b) or a!=b:errors.append(path+':value')
    walk(expected,actual,'geometry')
    return {'passed':not errors,'coordinateAbsoluteToleranceM':COORDINATE_ATOL_M,
            'maximumCoordinateDifferenceM':maximum,'errorCount':len(errors),'errors':errors[:20]}

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
        saved=fixture.with_name('native_dwg_contract_envelope.json')
        name=saved.relative_to(ROOT).as_posix()
        if hashlib.sha256(saved.read_bytes()).hexdigest()!=old['artifactHashes'][name]:
            raise RuntimeError('SavedSampleIntegrityMismatch')
        reference,_=verify_integrity_envelope(json.loads(saved.read_text(encoding='utf-8'))['geologicContractEnvelope'])
        comparison=compare_geometry({key:reference[key] for key in semantic},semantic)
        summary['geometryComparison']=comparison
        summary['exactGeometryHashMatched']=old['geometrySha256']==fingerprint
        summary['expectedGeometryMatched']=comparison['passed']
    (run/'public_sample_check.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    if not summary.get('expectedGeometryMatched',False):
        raise RuntimeError('SampleGeometryMismatch:'+json.dumps(summary,ensure_ascii=True))
    print(json.dumps({'runDirectory':str(run),**summary},ensure_ascii=True))
    return run,summary

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'results/public_sample')
    parser.add_argument('--native',action='store_true',help='Windows + AutoCAD 2027 required; creates a new DWG')
    args=parser.parse_args()
    replay(args.output,args.native)
