import json
import threading
import time
import unittest
from collections import OrderedDict
from dataclasses import replace
from route_request import AdvancedJapanSectionRequest, destination
from route_location import (parse_municipalities,place_label,resolve_route_locations,
                            annotation_lines,MUNICIPALITIES_URL)
from map_location_selector import TileLoader


class EndpointTests(unittest.TestCase):
    def test_exact_endpoints_and_order(self):
        a=(139.766084,35.681382);b=tuple(destination(*a,70,500))
        request=AdvancedJapanSectionRequest.from_endpoints(a,b)
        self.assertEqual(request.route(),[list(a),list(b)])
        self.assertAlmostEqual(request.length_m,500,places=6)
        self.assertAlmostEqual(request.azimuth_degrees,70,places=6)
        self.assertEqual(request.to_dict()['routeDefinition'],'OrderedEndpointsAB')
        reverse=AdvancedJapanSectionRequest.from_endpoints(b,a)
        self.assertEqual(reverse.route(),[list(b),list(a)])
        self.assertAlmostEqual(reverse.length_m,request.length_m,places=6)
        with self.assertRaises(ValueError):replace(request,length_m=501).validate()

    def test_invalid_and_missing_endpoints(self):
        a=(139.0,35.0)
        for b in (a,(139.0,35.000001),(0,0),(float('nan'),35),(True,35),None,(140,)):
            with self.subTest(b=b),self.assertRaises(ValueError):AdvancedJapanSectionRequest.from_endpoints(a,b)

    def test_legacy_route_serialization_unchanged(self):
        value=AdvancedJapanSectionRequest(138,36).to_dict()
        self.assertNotIn('route_endpoints',value)
        self.assertNotIn('routeDefinition',value)
        self.assertEqual(value['schemaVersion'],'AdvancedJapanSectionRequest-2.0')


class PlaceTests(unittest.TestCase):
    TABLE='GSI.MUNI_ARRAY["1101"] = \'1,北海道,1101,札幌市　中央区\';\nGSI.MUNI_ARRAY["13101"] = \'13,東京都,13101,千代田区\';'.encode()

    def test_actual_table_format_leading_zero(self):
        parsed=parse_municipalities(self.TABLE)
        self.assertEqual(parsed['01101']['municipality'],'札幌市中央区')
        with self.assertRaises(ValueError):parse_municipalities(b'not javascript data')

    def test_partial_address_plus_supported_terrain_only(self):
        address={'prefecture':'長野県','municipality':'松本市','detail':''}
        label=place_label(address,{'primaryClass':'MountainousRelief','confidenceClass':'ShapeSupported'})
        self.assertTrue(label.startswith('長野県松本市 山間部'))
        self.assertIn('DEM形状',label)
        ambiguous=place_label(address,{'primaryClass':'MountainousRelief','confidenceClass':'Ambiguous'})
        self.assertNotIn('山間部',ambiguous)
        self.assertIn('長野県松本市',ambiguous)
        self.assertNotIn('山間部',place_label(dict(address,detail='安曇'),{'primaryClass':'MountainousRelief','confidenceClass':'ShapeSupported'}))

    def test_partial_prefecture_not_lost_and_hashes_bound(self):
        def fetch(url):
            if url==MUNICIPALITIES_URL:return self.TABLE
            return json.dumps({'results':{'muniCd':'13999','lv01Nm':''}}).encode()
        result=resolve_route_locations([(139,35),(139.005,35)],[],fetch=fetch)
        self.assertEqual(result['endpoints'][0]['prefecture'],'東京都')
        self.assertEqual(result['endpoints'][0]['municipality'],'')
        self.assertEqual(len(result['endpoints'][0]['responseSha256']),64)
        self.assertIn('東京都',annotation_lines(result)[1])
        self.assertIn('35.00000000',annotation_lines(result)[0])

    def test_outage_keeps_coordinates(self):
        def offline(url):raise OSError('offline')
        result=resolve_route_locations([(139,35),(139.005,35)],[],fetch=offline)
        self.assertEqual(result['endpoints'][1]['longitude'],139.005)
        self.assertIn('地名未取得',result['endpoints'][0]['displayName'])
        self.assertNotIn('山間部',result['endpoints'][0]['displayName'])


class TileLoaderTests(unittest.TestCase):
    def wait_for(self,loader,predicate):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            loader.drain()
            if predicate():return
            time.sleep(.005)
        self.fail('tile loader timeout')

    def test_nonblocking_bounded_cache_and_revisit(self):
        release=threading.Event();calls=[];threads=[]
        def fetch(key):calls.append(key);threads.append(threading.get_ident());release.wait(2);return bytes([key])
        loader=TileLoader(fetch,cache=OrderedDict(),capacity=5,workers=2)
        try:
            started=time.monotonic();loader.set_view([1,2,3,4])
            self.assertLess(time.monotonic()-started,.15)
            self.assertLessEqual(len(loader.pending),2)
            release.set();self.wait_for(loader,lambda:len(loader.cache)==4)
            before=len(calls);loader.set_view([4,3,2,1]);loader.drain()
            self.assertEqual(len(calls),before)
            self.assertTrue(all(t!=threading.get_ident() for t in threads))
            loader.set_view([5,6]);self.wait_for(loader,lambda:6 in loader.cache)
            self.assertEqual(len(loader.cache),5)
        finally:release.set();loader.close()

    def test_new_view_does_not_enqueue_entire_old_map(self):
        release=threading.Event();calls=[]
        def fetch(key):calls.append(key);release.wait(2);return b'x'
        loader=TileLoader(fetch,cache=OrderedDict(),workers=1)
        try:
            loader.set_view(range(50));loader.set_view([99]);release.set()
            self.wait_for(loader,lambda:99 in loader.cache)
            self.assertLessEqual(len(calls),2)
            self.assertNotIn(20,calls)
        finally:release.set();loader.close()

    def test_failures_backoff_and_close(self):
        calls=[]
        def broken(key):calls.append(key);raise OSError('offline')
        loader=TileLoader(broken,cache=OrderedDict())
        loader.set_view([1]);self.wait_for(loader,lambda:1 in loader.failed)
        loader.set_view([1]);loader.drain();self.assertEqual(calls,[1])
        loader.close();loader.set_view([2]);self.assertNotIn(2,loader.pending)

if __name__=='__main__':unittest.main()
