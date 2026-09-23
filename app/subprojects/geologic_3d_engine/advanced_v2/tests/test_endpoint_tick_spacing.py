import unittest
from advanced_dwg_contract import _enclosing_ticks, _endpoint_priority_ticks


class EndpointTickSpacingTests(unittest.TestCase):
    def test_exact_endpoint_survives_without_nearby_regular_label(self):
        for length,expected in ((304.54218803057336,[0,100,200,304.54218803057336]),
                                (300,[0,100,200,300]),(350,[0,100,200,300,350]),
                                (437.033,[0,100,200,300,437.033]),
                                (500,[0,100,200,300,400,500]),(10,[0,10])):
            with self.subTest(length=length):
                values=_endpoint_priority_ticks(_enclosing_ticks(0,length,100),length,100)
                self.assertEqual(values,expected)
                self.assertEqual(values[-1],length)
                self.assertTrue(all(0<=x<=length for x in values))

    def test_invalid_spacing_is_rejected(self):
        for spacing in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):_endpoint_priority_ticks([0,100],100,spacing)


if __name__=='__main__':unittest.main()
