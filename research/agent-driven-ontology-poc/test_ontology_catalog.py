"""Synthetic DEV checks; no model, provider, or old core dependencies."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator
from rdflib import Graph
from ontology_catalog import Catalog, SR

CONCEPTS = {'bulk': ['bulk modulus', 'elastic modulus'],
            'young': ['Young modulus', 'elastic modulus'],
            'paper': ['research paper']}


def sample(tool='materials', field='k', concept='bulk'):
    return {'source': 'synthetic', 'tool': tool, 'endpoint': 'search', 'sourceRevision': 'v1',
            'inputSchema': {'type': 'object', 'properties': {'query': {'$ref': '#/$defs/query'}},
                            'required': ['query'], 'additionalProperties': False,
                            '$defs': {'query': {'type': 'string', 'minLength': 1}}},
            'outputSchema': {'type': 'object', 'properties': {'id': {'type': 'string'},
                field: {'type': 'object', 'properties': {'value': {'$ref': '#/$defs/value'},
                    'irrelevant': {'type': 'string'}}, 'required': ['value', 'irrelevant']},
                'discard': {'type': 'number'}}, 'required': ['id', field, 'discard'],
                '$defs': {'value': {'$ref': '#/$defs/number'}, 'number': {'type': 'number'},
                          'unused': {'type': 'string'}}},
            'fields': [{'path': ['id'], 'identifier': True, 'provenance': 'fixture'},
                       {'path': [field, 'value'], 'concepts': [concept], 'unit': 'GPa',
                        'sourceType': 'synthetic', 'license': 'fixture-only',
                        'provenance': 'fixture', 'groups': ['related']}]}


def literature(tool='literature'):
    r = sample(tool)
    r['inputSchema'] = {'type': 'object', 'properties': {'topic': {'type': 'string'}}, 'required': ['topic']}
    r['outputSchema'] = {'type': 'object', 'properties': {'doi': {'type': 'string'}, 'title': {'type': 'string'},
                           'abstract': {'type': 'string'}, 'venue': {'type': 'string'}}, 'required': ['doi', 'title']}
    r['fields'] = [{'path': ['doi'], 'identifier': True, 'provenance': 'fixture'},
                   {'path': ['title'], 'concepts': ['paper'], 'groups': ['record'], 'provenance': 'fixture'},
                   {'path': ['abstract'], 'groups': ['record'], 'provenance': 'fixture'}]
    return r


class CatalogTests(unittest.TestCase):
    def test_multi_need_and_refs(self):
        routes = [sample(), sample('alternative', 'bulk_modulus'), literature()]
        result = Catalog(CONCEPTS, routes).discover(['bulk modulus', 'research paper'])
        self.assertEqual(result['coverage'], {'bulk modulus': 'matched', 'research paper': 'matched'})
        self.assertEqual(len(result['views']), 3)
        for r in routes:
            view = next(v for v in result['views'] if v['route'][1] == r['tool'])
            self.assertEqual(view['inputSchema'], r['inputSchema'])
            if r['tool'] == 'literature':
                self.assertEqual(set(view['projectedOutputSchema']['properties']), {'doi', 'title', 'abstract'})
                continue
            field = r['fields'][1]['path'][0]
            schema = view['projectedOutputSchema']
            self.assertEqual(set(schema['properties']), {'id', field})
            self.assertEqual(set(schema['properties'][field]['properties']), {'value'})
            self.assertEqual(set(schema['$defs']), {'value', 'number'})
            Draft202012Validator(schema).validate({'id': 'x', field: {'value': 1}})
            self.assertEqual(view['fields'][1], r['fields'][1])

    def test_ambiguity_unknown(self):
        r = Catalog(CONCEPTS, [sample()]).discover(['elastic modulus', 'citation count', 'Young modulus'])
        self.assertEqual(r['coverage'], {'elastic modulus': 'ambiguous', 'citation count': 'uncovered', 'Young modulus': 'uncovered'})
        self.assertEqual(r['views'], [])

    def test_budget_and_permitted_surface(self):
        routes = [sample(str(i)) for i in range(8)]
        c = Catalog(CONCEPTS, routes)
        self.assertEqual(len(c.discover(['bulk'])['views']), 8)
        self.assertEqual(c.discover(['bulk'], max_routes=2)['omittedRoutes'], 6)
        self.assertEqual(len(Catalog(CONCEPTS, routes[:1]).discover(['bulk'])['views']), 1)
        both = Catalog(CONCEPTS, [sample('a'), literature('z')])
        self.assertEqual(both.discover(['bulk', 'paper'], max_routes=1)['coverage']['paper'], 'budget_limited')

    def test_lifecycle_persist_and_tamper(self):
        c = Catalog(CONCEPTS, [sample()])
        before = c.revision
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'catalog.ttl'
            c.save(p)
            restored = Catalog.load(p)
            self.assertEqual(restored.discover(['bulk']), c.discover(['bulk']))
            changed = sample(field='replacement')
            changed['sourceRevision'] = 'v2'
            restored.put(changed)
            self.assertNotEqual(restored.revision, before)
            self.assertNotIn('k', restored.discover(['bulk'])['views'][0]['projectedOutputSchema']['properties'])
            restored.remove(('synthetic', 'materials', 'search'))
            restored.save(p)
            self.assertEqual(Catalog.load(p).discover(['bulk'])['views'], [])
            g = Graph().parse(p, format='turtle')
            g.remove((SR.catalog, SR.revision, None))
            g.serialize(destination=p, format='turtle')
            with self.assertRaises(ValueError):
                Catalog.load(p)

    def test_malformed_and_unsupported(self):
        bad = sample()
        bad['fields'][1]['path'] = ['missing']
        with self.assertRaises(ValueError):
            Catalog(CONCEPTS, [bad])
        bad = sample()
        bad['inputSchema']['properties']['query']['$ref'] = 'https://example.org/schema'
        with self.assertRaises(ValueError):
            Catalog(CONCEPTS, [bad])
        bad = sample()
        bad['outputSchema']['minProperties'] = 3
        result = Catalog(CONCEPTS, [bad]).discover(['bulk'])
        self.assertEqual(result['coverage']['bulk'], 'unsupported_projection')
        self.assertEqual(result['views'], [])

    def test_declared_groups_and_atomic_failure(self):
        r = sample()
        r['fields'].append({'path': ['k', 'irrelevant'], 'groups': ['related'], 'provenance': 'fixture'})
        c = Catalog(CONCEPTS, [r])
        self.assertIn('irrelevant', c.discover(['bulk'])['views'][0]['projectedOutputSchema']['properties']['k']['properties'])
        before = c.discover(['bulk'])
        bad = deepcopy(r)
        bad['fields'][0]['path'] = ['bad']
        with self.assertRaises(ValueError):
            c.put(bad)
        self.assertEqual(c.discover(['bulk']), before)

    def test_identity_and_determinism(self):
        a, b = sample(), sample()
        b['source'] = 'second-source'
        self.assertEqual(Catalog(CONCEPTS, [a, b]).discover(['bulk']), Catalog(CONCEPTS, [b, a]).discover(['bulk']))
        with self.assertRaises(ValueError):
            Catalog(CONCEPTS, [a, a])


if __name__ == '__main__':
    unittest.main()
