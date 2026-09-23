import copy
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock

import numpy as np

from domain_profiles import profile_for_domain
from lithology_selector import select_evidence_bounded_lithologies
from regional_bedrock import (resolve_regional_bedrock, acquire_bedrock_neighborhood,
                              apply_regional_bedrock_geometry, audit_regional_bedrock)


def sample(label, station=500):
    return {"stationM":station, "legend":{"lithology_ja":label, "symbol":"fixture"}}


def mixed_plan(label="花崗岩・花崗閃緑岩・トーナル岩"):
    return {"surfaceGeology":{"samples":[sample("未固結堆積物", i*50) for i in range(10)] + [sample(label)]}}


class RegionalBedrockTests(unittest.TestCase):
    def test_minority_granite_not_lost_to_surface_majority(self):
        result = resolve_regional_bedrock(mixed_plan())
        self.assertEqual(result['selected']['key'], 'granitoid')
        self.assertEqual(len(result['selected']['evidence']), 1)
        self.assertFalse(result['subsurfaceContactObserved'])

    def test_no_location_hardcoding_other_rocks(self):
        for label, key in [('玄武岩','basalt'), ('安山岩','andesite'), ('花崗岩','granite'),
                           ('花崗閃緑岩','granodiorite'), ('片麻岩','gneiss'), ('砂岩','sandstone')]:
            self.assertEqual(resolve_regional_bedrock(mixed_plan(label))['selected']['key'], key)

    def test_conflict_not_invented_stacked_rocks(self):
        plan = mixed_plan(); plan['surfaceGeology']['samples'].append(sample('玄武岩', 250))
        result = resolve_regional_bedrock(plan)
        self.assertIsNone(result['selected'])
        self.assertEqual(len(result['candidates']), 2)
        self.assertIsNone(resolve_regional_bedrock(mixed_plan('玄武岩・安山岩'))['selected'])
        self.assertEqual(resolve_regional_bedrock(mixed_plan('砂岩・泥岩'))['selected']['key'],
                         'sandstone_mudstone')

    def test_missing_and_null_no_forced_granite(self):
        for plan in ({}, {'surfaceGeology':{'samples':[{'legend':None}]}}):
            self.assertIsNone(resolve_regional_bedrock(plan)['selected'])

    def test_neighborhood_requires_two_consistent_supports(self):
        plan = {'regionalBedrockNeighborhood':{'samples':[sample('玄武岩')]}}
        self.assertIsNone(resolve_regional_bedrock(plan)['selected'])
        plan['regionalBedrockNeighborhood']['samples'].append(sample('玄武岩'))
        self.assertEqual(resolve_regional_bedrock(plan)['origin'], 'NearbyMappedBedrock')
        self.assertEqual(resolve_regional_bedrock(plan)['selected']['key'], 'basalt')

    def test_selector_actual_substrate_not_legend_only_and_ash_not_default(self):
        profile = profile_for_domain('UnconsolidatedSedimentTerrain')
        result = select_evidence_bounded_lithologies(profile, 'UnconsolidatedSedimentTerrain', mixed_plan())
        self.assertEqual(result['substrateFacies'][-1][0], 'ADV2-REGIONAL-GRANITOID')
        self.assertTrue(result['terminologyCurrencyAudit']['passed'])
        self.assertNotIn('ADV2-OLD-VOLCANIC-ASH', [r[0] for r in result['substrateFacies']])
        self.assertEqual(result['faciesMetadata'][-1]['basisType'], 'SyntheticAssumption')
        self.assertFalse(result['faciesMetadata'][-1]['localObservationClaim'])
        ash = mixed_plan(); ash['surfaceGeology']['samples'].append(sample('火山灰質土', 100))
        selected = select_evidence_bounded_lithologies(profile, 'UnconsolidatedSedimentTerrain', ash)
        self.assertIn('ADV2-OLD-VOLCANIC-ASH', [r[0] for r in selected['substrateFacies']])

    def fixture(self, nearby=False):
        evidence = resolve_regional_bedrock(mixed_plan())
        if nearby:evidence['origin'] = 'NearbyMappedBedrock'
        x = np.linspace(0, 500, 51); terrain = 20 + 10*np.sin(x/100)
        layers = []; top = terrain
        for i, depth in enumerate((2, 20, 40, 80)):
            bottom = terrain-depth
            layers.append({'unitId':'ADV2-REGIONAL-GRANITOID' if i==3 else str(i),
                'topElevationM':top.tolist(), 'bottomElevationM':bottom.tolist(),
                'thicknessM':(top-bottom).tolist(), 'activeMask':[True]*len(x)})
            top = bottom
        return {'stationsM':x.tolist(),'terrainElevationM':terrain.tolist(),
                'lithologySelection':{'domain':'UnconsolidatedSedimentTerrain'},
                'regionalBedrockEvidence':evidence, 'composition':{'layersTopDown':layers},
                'syntheticEventArchitecture':{'renderBodies':copy.deepcopy(layers)}}

    def test_closure_shared_contacts_terrain_preserved_and_anchor_thins_cover(self):
        model = self.fixture(); before=copy.deepcopy(model)
        apply_regional_bedrock_geometry(model)
        layers = model['composition']['layersTopDown']
        for a,b in zip(layers, layers[1:]):
            self.assertEqual(a['bottomElevationM'], b['topElevationM'])
        for row in layers:self.assertGreaterEqual(min(row['thicknessM']),0)
        self.assertEqual(model['terrainElevationM'], before['terrainElevationM'])
        self.assertEqual(layers[-1]['bottomElevationM'], before['composition']['layersTopDown'][-1]['bottomElevationM'])
        self.assertEqual(layers[-1]['topElevationM'][-1], layers[0]['bottomElevationM'][-1])
        self.assertTrue(audit_regional_bedrock(model)['passed'])
        model['syntheticEventArchitecture']['renderBodies'][-1]['activeMask']=[False]*51
        self.assertFalse(audit_regional_bedrock(model)['passed'])

    def test_offroute_evidence_does_not_invent_route_exposure(self):
        model = self.fixture(nearby=True); before=copy.deepcopy(model)
        apply_regional_bedrock_geometry(model)
        self.assertEqual(model['composition']['layersTopDown'][-1]['topElevationM'],
                         before['composition']['layersTopDown'][-1]['topElevationM'])

    def test_out_of_scope_and_invalid_station_rejected(self):
        model=self.fixture(); model['lithologySelection']['domain']='VolcanicTerrain'
        with self.assertRaises(ValueError):apply_regional_bedrock_geometry(model)
        for value in (-1,501,float('nan')):
            model=self.fixture(); model['regionalBedrockEvidence']['selected']['evidence'][0]['stationM']=value
            with self.assertRaises(ValueError):apply_regional_bedrock_geometry(model)

    def test_api_budget_failure_and_scope(self):
        fetch=Mock(side_effect=TimeoutError())
        result=acquire_bedrock_neighborhood({'routeLonLat':[[132,34],[132.01,34]]},fetch=fetch)
        self.assertEqual(fetch.call_count,8);self.assertEqual(result['samples'],[])
        fetch.reset_mock()
        self.assertEqual(acquire_bedrock_neighborhood({'routeLonLat':[[0,0],[1,0]]},fetch=fetch)['samples'],[])
        fetch.assert_not_called()

    def test_live_shape_parser_without_network(self):
        legend={'symbol':'fixture','lithology_ja':'花崗岩','lithology_en':'granite',
                'formationAge_ja':'白亜紀','formationAge_en':'Cretaceous','title':'fixture',
                'value':'010203','r':1,'g':2,'b':3}
        fetch=Mock(return_value=json.dumps(legend).encode())
        result=acquire_bedrock_neighborhood({'routeLonLat':[[132,34],[132.01,34]]},fetch=fetch)
        self.assertEqual(len(result['samples']),8)
        self.assertTrue(all(len(r['sha256'])==64 for r in result['samples']))

    def test_long_route_does_not_extrapolate_one_local_rock_nationwide(self):
        plan=mixed_plan();plan['terrainProfile']=[{'stationM':0},{'stationM':100000}]
        self.assertIsNone(resolve_regional_bedrock(plan)['selected'])
        plan['routeLonLat']=[[132,34],[133,34]]
        fetch=Mock();self.assertEqual(acquire_bedrock_neighborhood(plan,fetch=fetch)['queries'],[])
        fetch.assert_not_called()

    def test_production_path_retains_bedrock_without_bypassing_area_gate(self):
        from nationwide_pipeline import run_advanced_japan_section
        from run_terrain_matrix import _acquisition, CASES
        from route_request import AdvancedJapanSectionRequest
        from advanced_dwg_contract import write_advanced_dwg_handoff
        root=Path(__file__).resolve().parents[4]
        acquire=_acquisition('plain',*CASES['plain'])
        def mixture(*args):
            acquire(*args)
            path=Path(args[3])/'plan_evidence_bundle.json'
            plan=json.loads(path.read_text(encoding='utf-8'))
            plan['surfaceGeology']['samples'][-1]['legend']=dict(
                plan['surfaceGeology']['samples'][-1]['legend'],
                symbol='K2_pf',title='granite',lithology_ja='花崗岩',lithology_en='granite')
            path.write_text(json.dumps(plan,ensure_ascii=False),encoding='utf-8')
        with tempfile.TemporaryDirectory() as folder:
            result=run_advanced_japan_section(root,AdvancedJapanSectionRequest(135,35,seed=76),
                                             folder,acquire_plan=mixture,native_dwg=False)
            # This independent fixture exceeds the existing 45% portrayal gate.
            # Retaining a regional rock must NOT silently relax other gates.
            self.assertFalse(result['passed'])
            self.assertEqual(result['reason'],'AdvancedDwgContractRejected')
            self.assertIn('SingleLithologyAreaDominanceExceeded',result['errorMessage'])
            self.assertFalse(result['dwgCreated'])
            model=json.loads(next(Path(folder).rglob('model.json')).read_text(encoding='utf-8'))
            self.assertTrue(model['regionalBedrockAudit']['passed'])
            self.assertEqual(model['composition']['layersTopDown'][-1]['unitId'],'ADV2-REGIONAL-GRANITE')
            model['syntheticEventArchitecture']['renderBodies'][-1]['activeMask']=[False]*51
            target=Path(folder)/'must_not_exist.json'
            with self.assertRaisesRegex(ValueError,'regional bedrock gate'):
                write_advanced_dwg_handoff(model,target)
            self.assertFalse(target.exists())


if __name__ == '__main__':unittest.main()
