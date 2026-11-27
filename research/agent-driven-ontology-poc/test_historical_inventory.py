"""Schema-only DEV checks on the pinned public paper inventory, never answer gold."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator
from rdflib import RDF
from ontology_catalog import Catalog, SR
from historical_inventory import (APIS_BLOB, FIXTURE, FIXTURE_BLOB, SOURCE, api_bytes,
                                  catalog, field_id, git_blob, load_apis, normalize)


class HistoricalInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        extracted = os.environ.get('SR_API_EXTRACT')
        cls.apis = load_apis(Path(extracted) if extracted else FIXTURE, extracted=bool(extracted))
        cls.concepts, cls.routes = normalize(cls.apis)
        cls.catalog = catalog(cls.apis)

    def test_pinned_schema_cardinality(self):
        self.assertEqual(git_blob(api_bytes(self.apis)), APIS_BLOB)
        g = self.catalog._graph
        self.assertEqual(len(set(g.subjects(RDF.type, SR.Tool))), 19)
        self.assertEqual(len(list(g.triples((None, SR.returnsField, None)))), 166)
        self.assertEqual(len(list(g.triples((None, SR.acceptsParameter, None)))), 80)
        self.assertEqual(len(self.concepts), 171)
        self.assertEqual(sum(len(f['equivalent_to']) for a in self.apis for f in a['fields']), 15)
        for api, route in zip(self.apis, self.routes):
            self.assertEqual(route['sourceRevision'], FIXTURE_BLOB)
            self.assertEqual(set(route['inputSchema']['properties']), {p['name'] for p in api['parameters']})
            self.assertEqual(set(route['inputSchema']['required']), {p['name'] for p in api['parameters'] if p['required']})
            self.assertEqual(set(route['outputSchema']['properties']), {f['name'] for f in api['fields']})
            self.assertNotIn('required', route['outputSchema'])
            for f in api['fields']:
                match = next(x for x in route['fields'] if x['path'] == [f['name']])
                self.assertEqual(match.get('unit'), f['unit'])
                self.assertEqual(match['identifier'], f['is_identifier'])
                self.assertEqual(match['sourceType'], f['source_type'])
                self.assertEqual(match['license'], api['license'])
                self.assertEqual(route['outputSchema']['properties'][f['name']]['x-sr-original-type'], f['type'])
                self.assertEqual(set(match['groups']), {g['name'] for g in api['field_groups'] if f['name'] in g['field_names']})

    def test_every_field_is_discoverable_by_qualified_id(self):
        for api in self.apis:
            for f in api['fields']:
                with self.subTest(tool=api['name'], field=f['name']):
                    term = field_id(api['name'], f['name'])
                    found = self.catalog.discover([term])
                    self.assertEqual(found['coverage'][term], 'matched')
                    self.assertEqual(len(found['views']), 1)
                    view = found['views'][0]
                    self.assertEqual(view['route'], [SOURCE, api['name'], 'search'])
                    self.assertIn(f['name'], view['projectedOutputSchema']['properties'])
                    Draft202012Validator.check_schema(view['projectedOutputSchema'])

    def test_agent_multiple_requirements(self):
        result = self.catalog.discover(['bulk modulus', 'research paper'])
        self.assertEqual(result['coverage'], {'bulk modulus': 'matched', 'research paper': 'matched'})
        tools = {v['route'][1]: v for v in result['views']}
        self.assertEqual(set(tools), {'materials_project', 'jarvis', 'arxiv', 'crossref', 'europe_pmc', 'openalex', 'pubmed'})
        self.assertIn('k_vrh', tools['materials_project']['projectedOutputSchema']['properties'])
        self.assertIn('bulk_modulus_kv', tools['jarvis']['projectedOutputSchema']['properties'])
        self.assertNotIn('band_gap', tools['materials_project']['projectedOutputSchema']['properties'])
        self.assertNotIn('optb88vdw_bandgap', tools['jarvis']['projectedOutputSchema']['properties'])
        for tool, v in tools.items():
            self.assertEqual(v['inputSchema'], next(r['inputSchema'] for r in self.routes if r['tool'] == tool))
            self.assertEqual(v['projectionKind'], 'schema_view_only')
        self.assertIn('VRH', tools['materials_project']['projectedOutputSchema']['properties']['k_vrh']['description'])
        self.assertIn('Voigt', tools['jarvis']['projectedOutputSchema']['properties']['bulk_modulus_kv']['description'])

    def test_structured_agent_requirements(self):
        result = self.catalog.discover([
            {'id': 'modulus', 'conceptId': 'capability:bulk_modulus', 'unit': 'GPa',
             'sourceType': 'calculated'},
            {'id': 'papers', 'concept': 'research paper', 'sourceType': 'literature'},
            {'id': 'young', 'conceptId': 'capability:young_modulus'},
        ])
        self.assertEqual(result['coverage'], {'modulus': 'matched', 'papers': 'matched',
                                              'young': 'uncovered'})
        self.assertFalse(result['allRequirementsMatched'])
        receipts = {r['requirement']['id']: r for r in result['requirementResults']}
        self.assertEqual([receipts[k]['returnedRoutes'] for k in ('modulus', 'papers', 'young')], [2, 5, 0])
        views = {v['route'][1]: v for v in result['views']}
        mp = views['materials_project']
        self.assertEqual(mp['matches'], [{'requirementId': 'modulus', 'paths': [['k_vrh']]}])
        self.assertIn(['g_vrh'], mp['adjunctPaths'])
        self.assertEqual(views['crossref']['matches'], [
            {'requirementId': 'papers', 'paths': [['abstract'], ['title']]}])
        exact_license = mp['fields'][0]['license']
        restricted = self.catalog.discover([{'id': 'x', 'conceptId': 'capability:bulk_modulus',
                                             'license': exact_license}])
        self.assertEqual([v['route'][1] for v in restricted['views']], ['materials_project'])

    def test_ambiguity_and_uncovered(self):
        result = self.catalog.discover(['elastic modulus', "Young's modulus", 'unsupported invented concept', 'title'])
        self.assertEqual(result['coverage'], {'elastic modulus': 'ambiguous', "Young's modulus": 'uncovered',
                                              'unsupported invented concept': 'uncovered', 'title': 'ambiguous'})
        self.assertEqual(result['views'], [])
        count = self.catalog.discover(['citation count'])
        self.assertEqual([v['route'][1] for v in count['views']], ['crossref'])
        self.assertIn('is-referenced-by-count', count['views'][0]['projectedOutputSchema']['properties'])
        # FieldGroup may carry reference-count as context, but it is not
        # mapped to the citation-count concept.
        refs = next(r for r in self.routes if r['tool'] == 'crossref')['fields']
        self.assertNotIn('capability:citation_count', next(f for f in refs if f['path'] == ['reference-count'])['concepts'])

    def test_unknown_native_types_and_literal_paths(self):
        routes = {r['tool']: r for r in self.routes}
        mp = routes['materials_project']['inputSchema']['properties']
        for name in ('crystal_system', 'magnetic_ordering'):
            self.assertIn('x-sr-type-limit', mp[name])
            self.assertNotIn('type', mp[name])
            self.assertNotIn('enum', mp[name])
        self.assertEqual(mp['band_gap']['anyOf'][1]['maxItems'], 2)
        nomad = routes['nomad']
        self.assertIn('results.material.chemical_formula_hill', nomad['outputSchema']['properties'])
        self.assertIn('pagination.page_size', nomad['inputSchema']['properties'])
        self.assertNotIn('results', nomad['outputSchema']['properties'])
        self.assertIn('x-sr-type-limit', nomad['inputSchema']['properties']['query'])

    def test_persisted_inventory_and_budget(self):
        expected = self.catalog.discover(['bulk modulus', 'research paper'])
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'catalog.ttl'
            self.catalog.save(file)
            restored = Catalog.load(file)
            self.assertEqual(restored.discover(['bulk modulus', 'research paper']), expected)
        limited = self.catalog.discover(['bulk modulus', 'research paper'], max_routes=2)
        self.assertEqual(limited['omittedRoutes'], 5)
        self.assertEqual(len(limited['views']), 2)

    def test_reject_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'apis.json'
            file.write_bytes(api_bytes(self.apis) + b'\n')
            with self.assertRaisesRegex(ValueError, 'blob mismatch'):
                load_apis(file, extracted=True)
        altered = json.loads(api_bytes(self.apis))
        altered[0]['fields'][0]['description'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'exact exposed'):
            normalize(altered)


if __name__ == '__main__':
    unittest.main()
