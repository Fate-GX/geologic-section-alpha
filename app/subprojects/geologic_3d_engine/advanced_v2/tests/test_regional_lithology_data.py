import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import regional_lithology_data as data
from regional_major_lithology import resolve_major_lithology_evidence
from lithology_selector import select_evidence_bounded_lithologies


def plan_for(*labels):
    return {"routeLonLat":[[132,34],[132.005,34]],
            "surfaceGeology":{"sourceId":"SYNTHETIC-REGIONAL-INPUT-TEST",
                "sourceEdition":"SyntheticTestOnly", "samples":[
                    {"stationM":i*10, "legend":{"lithology_ja":label}}
                    for i,label in enumerate(labels)]}}


class RegionalLithologyDataTests(unittest.TestCase):
    def test_vocabulary_has_29_members_and_is_not_occurrence(self):
        v=data.load_vocabulary()
        self.assertEqual(len(v['lithologies']),29)
        self.assertEqual(v['scope'],'GlobalVocabulary_NotRegionalOccurrence')
        self.assertEqual(data.build_regional_dataset(plan_for())['candidates'],[])

    def test_all_members_and_minority_retained(self):
        plan=plan_for(*(['安山岩']*8), '玄武岩・デイサイト・流紋岩')
        evidence=resolve_major_lithology_evidence(plan,'VolcanicTerrain')
        self.assertEqual(set(evidence['selectedKeys']),{'basalt','andesite','dacite','rhyolite'})
        self.assertFalse(evidence['majorityOnlyFiltering'])
        self.assertFalse(evidence['subsurfaceContactAuthorized'])

    def test_specific_alias_does_not_erase_separately_named_general_rock(self):
        v=data.load_vocabulary()
        self.assertEqual(data.matching_keys({'lithology_ja':'花崗閃緑岩'},v),['granodiorite'])
        self.assertEqual(set(data.matching_keys({'lithology_ja':'花崗閃緑岩・閃緑岩'},v)),
                         {'granodiorite','diorite'})
        self.assertEqual(set(data.matching_keys({'lithology_en':'sandstone, sand and siltstone'},v)),
                         {'sandstone','sand','siltstone'})

    def test_place_name_age_and_symbol_do_not_create_rocks(self):
        self.assertEqual(data.matching_keys({'title':'玄武岩村', 'symbol':'basalt',
            'formationAge_en':'granite'},data.load_vocabulary()),[])

    def test_roundtrip_reloads_file_and_binds_digest(self):
        plan=plan_for('砂岩・泥岩')
        with tempfile.TemporaryDirectory() as folder, patch.object(data,'read_json',wraps=data.read_json) as spy:
            path=Path(folder)/'input.json'
            loaded=data.write_and_load_regional_dataset(plan,path)
            self.assertTrue(any(c.args[0]==path for c in spy.call_args_list))
            self.assertEqual(plan['regionalLithologyInputFile']['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(data.regional_dataset_for_plan(plan),loaded)
            with self.assertRaises(FileExistsError):data.write_and_load_regional_dataset(plan,path)

    def test_candidate_and_relation_forgery_rejected(self):
        plan=plan_for('砂岩・泥岩');original=data.build_regional_dataset(plan)
        for mutate in (lambda d:d['candidates'].pop(),
                       lambda d:d['relations'][0].update(contactGeometryAuthorized=True),
                       lambda d:d['records'][0]['matchedKeys'].append('granite')):
            changed=copy.deepcopy(original);mutate(changed)
            with self.assertRaisesRegex(ValueError,'BindingMismatch'):
                data.validate_regional_dataset(changed,plan)

    def test_stale_route_source_and_vocabulary_rejected(self):
        plan=plan_for('花崗岩');original=data.build_regional_dataset(plan)
        changed=copy.deepcopy(plan);changed['routeLonLat'][1][0]+=1
        with self.assertRaisesRegex(ValueError,'RouteEvidence'):data.validate_regional_dataset(original,changed)
        changed=copy.deepcopy(plan);changed['surfaceGeology']['samples'][0]['legend']['lithology_ja']='玄武岩'
        with self.assertRaisesRegex(ValueError,'RouteEvidence'):data.validate_regional_dataset(original,changed)
        v=data.load_vocabulary();v['version']='new'
        with self.assertRaisesRegex(ValueError,'VocabularyChanged'):data.validate_regional_dataset(original,plan,v)

    def test_data_edit_changes_match_without_code_edit(self):
        v=data.load_vocabulary();v['lithologies'][0]['aliases'].append('fixture-specific-basalt-alias')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'vocabulary.json';path.write_text(json.dumps(v),encoding='utf-8')
            loaded=data.load_vocabulary(path)
            result=data.build_regional_dataset(plan_for('fixture-specific-basalt-alias'),loaded)
            self.assertEqual(result['candidates'][0]['key'],'basalt')

    def test_malformed_json_missing_nonfinite_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.json'
            with self.assertRaises(ValueError):data.read_json(path)
            for text in ('{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}'):
                path.write_text(text,encoding='utf-8')
                with self.assertRaises(ValueError):data.read_json(path)
            v=data.load_vocabulary();v['specificityOrder'].append('basalt')
            path.write_text(json.dumps(v),encoding='utf-8')
            with self.assertRaises(ValueError):data.load_vocabulary(path)

    def test_invalid_route_rejected(self):
        for route in ([[132]],[[200,34],[132,34]],[[132,float('nan')]]):
            plan=plan_for('玄武岩');plan['routeLonLat']=route
            with self.assertRaises(ValueError):data.build_regional_dataset(plan)

    def test_composite_members_are_used_and_weathering_states_retained(self):
        result=select_evidence_bounded_lithologies({'profileId':'fixture'},'PlutonicTerrain',
            plan_for('花崗岩・花崗閃緑岩'))
        labels={r[0]:r[1] for r in result['substrateFacies']}
        self.assertIn('強風化花崗岩・花崗閃緑岩',labels['SYN-HIGH-WEATHERED'])
        self.assertIn('比較的新鮮な花崗岩・花崗閃緑岩',labels['SYN-FRESH-PLUTON'])
        findings=result['regionalLithologySelection']['findings']
        self.assertEqual(len(findings),2)
        self.assertTrue(all(r['status']=='RepresentedByRegionalPrior' for r in findings))
        self.assertFalse(result['regionalLithologySelection']['allCandidateInternalContactsResolved'])

    def test_incompatible_rocks_retained_with_reason_not_invented_stack(self):
        result=select_evidence_bounded_lithologies({'profileId':'fixture'},'UnconsolidatedSedimentTerrain',
            plan_for('砂質堆積物','花崗岩','玄武岩'))
        self.assertIsNone(result['regionalBedrockEvidence']['selected'])
        findings={r['key']:r for r in result['regionalLithologySelection']['findings']}
        self.assertEqual(findings['granite']['status'],'Retained_RequiresDifferentGeologicalArchitecture')
        self.assertFalse(findings['basalt']['unitIds'])
        self.assertEqual(findings['sand']['unitIds'],['ADV2-SAND'])

    def test_base_accounting_does_not_claim_surface_sand_is_granite(self):
        result=select_evidence_bounded_lithologies({'profileId':'fixture'},'UnconsolidatedSedimentTerrain',
            plan_for('砂質堆積物','花崗岩・花崗閃緑岩'))
        findings={r['key']:r for r in result['regionalLithologySelection']['findings']}
        self.assertEqual(findings['sand']['unitIds'],['ADV2-SAND'])
        self.assertEqual(findings['granodiorite']['unitIds'],['ADV2-REGIONAL-GRANITOID'])

    def test_synthetic_sources_never_upgraded_to_observed(self):
        result=data.build_regional_dataset(plan_for('玄武岩'))
        self.assertEqual(result['records'][0]['basisType'],'SyntheticTestEvidence')
        self.assertFalse(result['records'][0]['subsurfaceObserved'])

    def test_unchanged_input_deterministic(self):
        plan=plan_for('砂岩・泥岩')
        a=data.build_regional_dataset(plan);plan['unusedOutputPath']='different'
        self.assertEqual(data.canonical(a),data.canonical(data.build_regional_dataset(plan)))

    def test_missing_input_rejected_before_model_calculation(self):
        import nationwide_pipeline as pipeline
        from run_terrain_matrix import _acquisition, CASES
        from route_request import AdvancedJapanSectionRequest
        root=Path(__file__).resolve().parents[4]
        imports=list(pipeline._engine_imports(root));imports[0]=Mock(wraps=imports[0])
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline,'_engine_imports',return_value=imports), \
                patch.object(pipeline,'write_and_load_regional_dataset',side_effect=ValueError('MissingRegionalData')):
            result=pipeline.run_advanced_japan_section(root,AdvancedJapanSectionRequest(135,35,seed=45),
                folder,acquire_plan=_acquisition('plain',*CASES['plain']),native_dwg=False)
            self.assertEqual(result['reason'],'RegionalLithologyInputRejected')
            imports[0].assert_not_called()
            self.assertFalse(list(Path(folder).rglob('model.json')))

    def test_production_consumes_reloaded_multi_rock_data(self):
        import nationwide_pipeline as pipeline
        from run_terrain_matrix import _acquisition, CASES
        from route_request import AdvancedJapanSectionRequest
        root=Path(__file__).resolve().parents[4]
        original=_acquisition('mountain',*CASES['mountain'])
        def acquire(*args):
            original(*args);path=Path(args[3])/'plan_evidence_bundle.json'
            plan=json.loads(path.read_text(encoding='utf-8'))
            for sample in plan['surfaceGeology']['samples'][-5:]:
                sample['legend'].update(lithology_ja='玄武岩・安山岩',lithology_en='basalt and andesite')
            path.write_text(json.dumps(plan),encoding='utf-8')
        with tempfile.TemporaryDirectory() as folder:
            result=pipeline.run_advanced_japan_section(root,AdvancedJapanSectionRequest(135,35,seed=880102),
                folder,acquire_plan=acquire,native_dwg=False)
            self.assertTrue(result['passed'],result)
            model=json.loads(next(Path(folder).rglob('model.json')).read_text(encoding='utf-8'))
            stored=data.read_json(next(Path(folder).rglob('regional_lithology_input.json')))
            self.assertEqual(model['regionalLithologyInput'],stored)
            self.assertEqual(set(model['majorLithologyEvidence']['selectedKeys']),{'basalt','andesite'})
            self.assertTrue(any('玄武岩・安山岩' in r['label'] for r in model['renderingLithologies']))
            self.assertTrue(any(r['path'].endswith('regional_lithology_input.json') for r in result['artifacts']))


if __name__=='__main__':unittest.main()
