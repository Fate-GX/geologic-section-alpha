import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from reproduce_sample import replay
from reproduce_sample import compare_geometry
from copy import deepcopy
import pytest

def fixture_geometry():
    return {'polygons':[{'unitId':'A','vertices':[[0.0,0.0],[2.0,3.0],[4.0,0.0]]}],
            'terrainLine':[[0.0,5.0],[4.0,5.0]]}

@pytest.mark.parametrize('delta',[0.0,5.2e-7,1e-6])
def test_coordinate_roundoff_accepted(delta):
    a=fixture_geometry();b=deepcopy(a)
    b['polygons'][0]['vertices'][0][1]=delta
    assert compare_geometry(a,b)['passed']

@pytest.mark.parametrize('delta',[1.0001e-6,0.001,float('nan'),float('inf')])
def test_coordinate_changes_rejected(delta):
    a=fixture_geometry();b=deepcopy(a)
    b['polygons'][0]['vertices'][0][1]=delta
    assert not compare_geometry(a,b)['passed']

@pytest.mark.parametrize('change',['unit','count','order','field','terrain','bool'])
def test_structural_changes_rejected(change):
    a=fixture_geometry();b=deepcopy(a)
    if change=='unit':b['polygons'][0]['unitId']='B'
    elif change=='count':b['polygons'][0]['vertices'].pop()
    elif change=='order':b['polygons'][0]['vertices'].reverse()
    elif change=='field':b['polygons'][0]['extra']='bad'
    elif change=='terrain':b['terrainLine'][0][1]+=0.001
    elif change=='bool':b['polygons'][0]['vertices'][0][1]=False
    assert not compare_geometry(a,b)['passed']

def test_public_artifact_hashes():
    expected=json.loads((ROOT/'examples/synthetic_plain/expected.json').read_text(encoding='utf-8'))
    for name,digest in expected['artifactHashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    assert expected['realSiteEvidence'] is False
    assert (ROOT/'dwg/synthetic_plain.dwg').read_bytes()[:6]==b'AC1032'

def test_replay_matches_saved_geometry(tmp_path):
    _,summary=replay(tmp_path,native=False)
    assert summary['expectedGeometryMatched']
    assert summary['nativeSuccess'] is False
