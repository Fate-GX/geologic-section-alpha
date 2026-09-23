import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from reproduce_sample import replay

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
