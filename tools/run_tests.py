"""Selected portable regressions; this does not run AutoCAD."""
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
ADV=ROOT/'app/subprojects/geologic_3d_engine/advanced_v2'
sys.dont_write_bytecode=True
sys.path[:0]=[str(ADV),str(ADV.parent),str(ROOT/'tools')]
NAMES=('test_map_route.py','test_map_distance_limit.py','test_map_location_selector.py',
       'test_sampler_audit_scope.py','test_endpoint_tick_spacing.py','test_advanced_route.py',
       'test_regional_lithology_data.py','test_regional_bedrock.py','test_native_environment_probe.py',
       'test_native_gate_artifact_audit.py','test_user_context_native_gate.py')
if __name__=='__main__':
    raise SystemExit(pytest.main([*[str(ADV/'tests'/name) for name in NAMES],
                                 str(ROOT/'tests/test_alpha_packaging.py'),str(ROOT/'tests/test_public_sample.py'),'-q','-p','no:cacheprovider']))
