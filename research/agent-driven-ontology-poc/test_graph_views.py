"""Representation and browsing mechanism tests, not model scores."""
from pathlib import Path
import os
import unittest
from historical_inventory import FIXTURE, load_apis, normalize
from ontology_catalog import canon
from graph_views import Views, flatten


class GraphViewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.getenv('SR_API_EXTRACT')
        cls.views = Views(*normalize(load_apis(Path(path) if path else FIXTURE, extracted=bool(path))))

    def test_complete_equal_information(self):
        v = self.views
        self.assertEqual(canon(v.view('flat')), canon(flatten(v.view('graph'))))
        self.assertEqual((len(v.routes), len(v.fields), len(v.concepts)), (19, 166, 171))

    def test_every_route_neighborhood(self):
        v = self.views
        for rid in v.routes:
            self.assertEqual(canon(v.view('flat', [rid])), canon(flatten(v.view('graph', [rid]))))

    def test_ambiguous_alias_exposes_alternatives(self):
        v = self.views
        found = v.find('band_gap')
        self.assertGreaterEqual(len({h['tool'] for h in found['fieldHits']}), 2)
        elastic = v.find('elastic modulus')
        self.assertIn('capability:young_modulus', elastic['concepts'])
        self.assertIn('capability:bulk_modulus', elastic['concepts'])
        self.assertIn('capability:shear_modulus', elastic['concepts'])
        self.assertTrue(elastic['fieldHits'])
        self.assertEqual(v.find('not_a_real_field_123'), {'routeIds': [], 'concepts': {}, 'fieldHits': []})

    def test_explicit_field_selection(self):
        v = self.views
        hit = next(h for h in v.find('bulk modulus')['fieldHits'] if h['tool'] == 'materials_project' and h['path'] == ['k_vrh'])
        result = v.selected_schema(hit['route'], [hit['field']])
        self.assertEqual(list(result['projectedOutputSchema']['properties']), ['k_vrh'])
        self.assertEqual(result['inputSchema'], v.routes[hit['route']]['inputSchema'])
        with self.assertRaises(ValueError):
            v.selected_schema(hit['route'], [next(fid for fid, (rid, _) in v.fields.items() if rid != hit['route'])])

    def test_invalid_scope_and_isolation(self):
        v = self.views
        with self.assertRaises(ValueError):
            v.view('graph', ['not-permitted'])
        got = v.view('flat', ['r0'])
        got['routes']['r0']['fields'].clear()
        self.assertTrue(v.view('flat', ['r0'])['routes']['r0']['fields'])


if __name__ == '__main__':
    unittest.main()
