from pathlib import Path
import json
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
ADV=ROOT/'app/subprojects/geologic_3d_engine/advanced_v2'
sys.path[:0]=[str(ROOT/'tools'),str(ADV),str(ADV.parent)]
import operator_ui
from frozen_guard import verify_frozen_basic_v1

def test_no_research_menu_or_next_runtime():
    assert not (ROOT/'app/subprojects/geologic_3d_engine_next').exists()
    text=(ROOT/'tools/operator_ui.py').read_text(encoding='utf-8')
    assert '研究用ツール' not in text
    assert 'nationwide_pipeline' in text

def test_frozen_public_runtime():
    assert verify_frozen_basic_v1(ROOT/'app')['passed']

def test_generation_sources_unchanged():
    import hashlib
    data=json.loads((ROOT/'docs/packaging_provenance.json').read_text(encoding='utf-8'))
    for record in data['preservedGenerationFiles']:
        assert hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest()==record['sha256']

def test_atomic_settings(tmp_path):
    path=tmp_path/'settings.json'
    operator_ui.atomic_write_json(path,{'routePoints':[[135,35],[135.001,35.001]]})
    assert len(json.loads(path.read_text(encoding='utf-8'))['routePoints'])==2
    assert list(tmp_path.iterdir())==[path]

def test_profile_policy_restored(tmp_path):
    import os
    from run_user_context_native_gate import ensure_interactive_user
    def pipeline(root,request,output):
        assert 'GEO3D_AUTOCAD_PROFILE_ARG' not in os.environ
        assert os.environ['GEO3D_AUTOCAD_USE_CURRENT_DEFAULT']=='1'
        return {'passed':False,'reason':'SyntheticTestRefusal'}
    with patch('run_user_context_native_gate.windows_process_identity',return_value='TestInteractiveUser'):
        with patch.dict(os.environ,{'GEO3D_AUTOCAD_PROFILE_ARG':'not-imported.arg'},clear=False):
            result=operator_ui.run_section(ROOT/'app',object(),tmp_path,pipeline=pipeline)
            assert result['passed'] is False
            assert os.environ['GEO3D_AUTOCAD_PROFILE_ARG']=='not-imported.arg'
