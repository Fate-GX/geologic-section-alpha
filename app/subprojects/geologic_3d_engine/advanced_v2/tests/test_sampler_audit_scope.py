"""Sampler regression is not a stochastic gate on the user's route length."""
import unittest
from unittest.mock import patch
import numpy as np
from advanced_contact_geometry import (audit_contact_range_ensemble,
    audit_contact_sampler_implementation)


class SamplerAuditScopeTests(unittest.TestCase):
    def test_original_user_grid_exposes_false_route_gate(self):
        audit=audit_contact_range_ensemble(np.linspace(0,304.54218803057336,32),seed_count=24)
        self.assertIn('ContactClassesNotEmpiricallyDistinguishable',audit['errors'])
        reference=audit_contact_sampler_implementation()
        self.assertTrue(reference['passed'],reference)
        self.assertFalse(reference['routeGeometryAcceptanceClaim'])
        self.assertEqual(reference['referenceGrid']['stationCount'],51)
        self.assertEqual(reference,audit_contact_sampler_implementation())

    def test_sampler_ignoring_ranges_still_fails(self):
        with patch('advanced_contact_geometry._matern32_sample',
                   side_effect=lambda x,**kwargs:np.ones(len(x))):
            result=audit_contact_sampler_implementation()
        self.assertFalse(result['passed'])
        self.assertIn('ContactClassesNotEmpiricallyDistinguishable',result['errors'])

    def test_nonfinite_sampler_still_fails(self):
        with patch('advanced_contact_geometry._matern32_sample',
                   side_effect=lambda x,**kwargs:np.full(len(x),float('nan'))):
            result=audit_contact_sampler_implementation()
        self.assertFalse(result['passed'])
        self.assertIn('NonFiniteEmpiricalCorrelation',result['errors'])


if __name__=='__main__':unittest.main()
