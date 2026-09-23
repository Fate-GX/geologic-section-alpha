import importlib.util
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("metrics",ROOT/"geologic_3d_engine/validation/facies_metrics.py")
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


class FaciesMetricsTests(unittest.TestCase):
    def test_known_alternating_volume(self):
        a = np.tile([1,2,1,2],(2,3,1))
        r = metrics.describe_facies(a,[2,3,5],max_lag=4)
        c = r["categories"][0]
        self.assertEqual(c["fraction"],.5)
        self.assertEqual(c["componentSizesDescending"],[6,6])
        self.assertEqual(c["directional"]["X"][0]["pairCount"],18)
        self.assertEqual(c["directional"]["X"][0]["indicatorSemivariance"],.5)
        self.assertEqual(c["directional"]["X"][1]["indicatorSemivariance"],0)
        self.assertIsNone(c["directional"]["X"][3]["indicatorSemivariance"])
        self.assertEqual(c["directional"]["Y"][0]["distance"],3)

    def test_mask_uses_both_endpoints(self):
        a = np.array([[[1,2,1,2]]]); mask = np.array([[[True,False,True,True]]])
        r = metrics.describe_facies(a,[1,1,1],valid_mask=mask,max_lag=1)
        c = r["categories"][0]
        self.assertEqual(c["fraction"],2/3)
        self.assertEqual(c["directional"]["X"][0]["pairCount"],1)
        self.assertEqual(c["directional"]["X"][0]["indicatorSemivariance"],.5)
        self.assertEqual(c["componentSizesDescending"],[1,1])

    def test_point_and_edge_contacts_not_face_connected(self):
        a = np.zeros((2,3,3),dtype=int)
        a[0,0,0] = a[0,1,1] = a[1,2,2] = 9
        c = metrics.describe_facies(a,[1,1,1])["categories"][1]
        self.assertEqual(c["componentSizesDescending"],[1,1,1])

    def test_uniform_and_single_cell(self):
        r = metrics.describe_facies(np.ones((1,1,1)),[1,1,1])
        self.assertEqual(r["categories"][0]["fraction"],1)
        self.assertIsNone(r["categories"][0]["directional"]["Z"][0]["indicatorSemivariance"])
        self.assertFalse(r["realRegionAuthorized"])

    def test_random_pair_oracle(self):
        # Explicit coordinate loops, not the production slicing implementation.
        rng = np.random.default_rng(9041)
        for _ in range(8):
            a = rng.integers(1,4,size=(3,4,5)); mask = rng.random(a.shape)>.2
            r = metrics.describe_facies(a,[2,4,7],valid_mask=mask,max_lag=3)
            for c in r["categories"]:
                for name,axis in (("X",2),("Y",1),("Z",0)):
                    for row in c["directional"][name]:
                        diffs = []
                        for p in np.ndindex(a.shape):
                            q = list(p); q[axis] += row["lagCells"]; q = tuple(q)
                            if q[axis]<a.shape[axis] and mask[p] and mask[q]:
                                diffs.append((int(a[p]==c["id"])-int(a[q]==c["id"]))**2)
                        self.assertEqual(row["pairCount"],len(diffs))
                        self.assertEqual(row["indicatorSemivariance"],sum(diffs)/(2*len(diffs)) if diffs else None)

    def test_category_renaming_and_nonmutation(self):
        a = np.array([[[1,2,1],[2,2,1]]]); old = a.copy()
        r = metrics.describe_facies(a,[1,1,1])
        s = metrics.describe_facies(np.where(a==1,70,90),[1,1,1])
        for c,d in zip(r["categories"],s["categories"]):
            c.pop("id");d.pop("id");self.assertEqual(c,d)
        np.testing.assert_array_equal(a,old)

    def test_rejections(self):
        for a in (np.ones((2,2)),np.ones((0,2,2)),np.array([[[np.nan]]]),
                  np.array([[[1.5]]]),np.array([[[True]]]),np.array([[['U']]])):
            with self.subTest(a=a), self.assertRaises(ValueError):
                metrics.describe_facies(a,[1,1,1])
        for spacing in ([0,1,1],[-1,1,1],[float('inf'),1,1],[1,1],[True,True,True]):
            with self.subTest(spacing=spacing), self.assertRaises(ValueError):
                metrics.describe_facies(np.ones((2,2,2)),spacing)
        for lag in (0,-1,True,1.5,65):
            with self.subTest(lag=lag), self.assertRaises(ValueError):
                metrics.describe_facies(np.ones((2,2,2)),[1,1,1],max_lag=lag)

    def test_mask_and_unit_rejections(self):
        for mask in (np.ones((2,2,2)),np.ones((1,2,2),dtype=bool),np.zeros((2,2,2),dtype=bool)):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                metrics.describe_facies(np.ones((2,2,2)),[1,1,1],valid_mask=mask)
        with self.assertRaises(ValueError):
            metrics.describe_facies(np.ones((2,2,2)),[1,1,1],length_unit="degrees")


if __name__ == "__main__":
    unittest.main()
