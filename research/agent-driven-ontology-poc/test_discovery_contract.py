"""Gate B structured-discovery and reference/scope DEV regressions."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator
from ontology_catalog import Catalog


CONCEPTS = {'bulk': ['bulk modulus', 'elastic modulus'],
            'shear': ['shear modulus', 'elastic modulus'],
            'paper': ['research paper']}


def route(tool='materials', unit='GPa', source_type='calculated', license_id='fixture-only'):
    return {'source': 'synthetic', 'tool': tool, 'endpoint': 'search', 'sourceRevision': 'v1',
            'inputSchema': {'type': 'object', 'properties': {'formula': {'type': 'string'}},
                            'required': ['formula'], 'additionalProperties': False},
            'outputSchema': {'type': 'object', 'properties': {'id': {'type': 'string'},
                'k': {'type': 'number'}, 'g': {'type': 'number'}, 'secret': {'type': 'string'}}},
            'fields': [{'path': ['id'], 'identifier': True, 'provenance': 'fixture'},
                       {'path': ['k'], 'concepts': ['bulk'], 'groups': ['elastic'], 'unit': unit,
                        'sourceType': source_type, 'license': license_id, 'provenance': 'fixture'},
                       {'path': ['g'], 'concepts': ['shear'], 'groups': ['elastic'], 'unit': 'MPa',
                        'sourceType': source_type, 'license': license_id, 'provenance': 'fixture'}]}


def req(rid='r1', **kwargs):
    return {'id': rid, 'conceptId': 'bulk', **kwargs}


class DiscoveryContractTests(unittest.TestCase):
    def test_exact_qualifiers_and_adjuncts(self):
        good = route('a')
        wrong_unit = route('b', unit='MPa')
        wrong_source = route('c', source_type='experimental')
        wrong_license = route('d', license_id='other')
        unknown = route('e')
        unknown['fields'][1].pop('license')
        c = Catalog(CONCEPTS, [good, wrong_unit, wrong_source, wrong_license, unknown])
        result = c.discover([req(unit='GPa', sourceType='calculated', license='fixture-only')])
        self.assertEqual(result['coverage'], {'r1': 'matched'})
        self.assertTrue(result['allRequirementsMatched'])
        self.assertEqual(len(result['views']), 1)
        view = result['views'][0]
        self.assertEqual(view['route'][1], 'a')
        self.assertEqual(view['matches'], [{'requirementId': 'r1', 'paths': [['k']]}])
        self.assertEqual(view['adjunctPaths'], [['g'], ['id']])
        self.assertEqual(view['projectionPaths'], [['g'], ['id'], ['k']])
        self.assertNotIn('secret', view['projectedOutputSchema']['properties'])
        self.assertEqual(view['inputSchema'], good['inputSchema'])
        self.assertEqual(result['requirementResults'][0]['matchingRoutes'], 1)
        self.assertTrue(result['requirementResults'][0]['allMatchingRoutesReturned'])
        self.assertEqual(c.discover([req(unit='gpa')])['coverage'], {'r1': 'uncovered'})
        self.assertEqual(c.discover([req(license='other')])['views'][0]['route'][1], 'd')

    def test_two_requirements_do_not_share_adjunct_evidence(self):
        c = Catalog(CONCEPTS, [route()])
        result = c.discover([req('gpa', unit='GPa'), req('mpa', unit='MPa'),
                             {'id': 'shear', 'conceptId': 'shear', 'unit': 'MPa'}])
        self.assertEqual(result['coverage'], {'gpa': 'matched', 'mpa': 'uncovered', 'shear': 'matched'})
        self.assertFalse(result['allRequirementsMatched'])
        self.assertEqual(result['views'][0]['matches'], [{'requirementId': 'gpa', 'paths': [['k']]},
                                                        {'requirementId': 'shear', 'paths': [['g']]}])
        self.assertEqual(result['views'][0]['adjunctPaths'], [['id']])

    def test_explicit_concept_id_and_alias_ambiguity(self):
        concepts = deepcopy(CONCEPTS)
        concepts['shear'].append('bulk')
        c = Catalog(concepts, [route()])
        self.assertEqual(c.discover(['bulk'])['coverage'], {'bulk': 'ambiguous'})
        self.assertEqual(c.discover([req()])['coverage'], {'r1': 'matched'})
        # Qualifiers do not silently disambiguate a physical meaning.
        a = c.discover([{'id': 'x', 'concept': 'elastic modulus', 'unit': 'GPa'}])
        self.assertEqual(a['coverage'], {'x': 'ambiguous'})
        self.assertEqual(a['requirementResults'][0]['matchingRoutes'], 0)
        self.assertEqual(a['requirementResults'][0]['candidateConceptIds'], ['bulk', 'shear'])
        self.assertEqual(c.discover([{'id': 'x', 'conceptId': 'unknown'}])['coverage'], {'x': 'uncovered'})

    def test_budget_and_projection_failure_counts(self):
        invalid = route('b')
        invalid['outputSchema']['minProperties'] = 1
        c = Catalog(CONCEPTS, [route('a'), invalid, route('c')])
        result = c.discover([req()], max_routes=1)
        receipt = result['requirementResults'][0]
        self.assertEqual(receipt['status'], 'matched')
        self.assertEqual((receipt['matchingRoutes'], receipt['returnedRoutes'],
                          receipt['omittedRoutes'], receipt['unsupportedProjectionRoutes']), (3, 1, 1, 1))
        self.assertFalse(receipt['allMatchingRoutesReturned'])
        self.assertEqual(result['omittedRoutes'], 1)
        self.assertEqual(Catalog(CONCEPTS, [invalid]).discover([req()])['coverage'],
                         {'r1': 'unsupported_projection'})
        # A different requirement can be entirely dropped by caller budget.
        p = route('z')
        p['fields'][1]['concepts'] = ['paper']
        result = Catalog(CONCEPTS, [route('a'), p]).discover([req(), 'paper'], max_routes=1)
        self.assertEqual(result['coverage'], {'r1': 'matched', 'paper': 'budget_limited'})
        self.assertEqual(result['requirementResults'][1]['omittedRoutes'], 1)

    def test_prepermitted_catalog_isolation(self):
        # Host owns the complete permitted schema surface, not a query-side mask.
        a = route('allowed')
        a['outputSchema']['properties'].pop('secret')
        a['outputSchema']['properties'].pop('g')
        a['fields'].pop()
        permitted = Catalog({'bulk': ['bulk modulus']}, [a])
        denied = route('denied')
        other = Catalog(CONCEPTS, [denied])
        result = permitted.discover([req()])
        self.assertEqual(result['requirementResults'][0]['matchingRoutes'], 1)
        self.assertEqual(result['views'][0]['projectionPaths'], [['id'], ['k']])
        serialized = json.dumps(result)
        self.assertNotIn('denied', serialized)
        self.assertNotIn('secret', serialized)
        self.assertNotIn('shear', serialized)
        self.assertEqual(other.discover([req()])['views'][0]['route'][1], 'denied')
        # Returned structures cannot mutate the catalog's stored source contract.
        result['views'][0]['inputSchema']['required'].clear()
        self.assertEqual(permitted.discover([req()])['views'][0]['inputSchema']['required'], ['formula'])

    def test_annotation_revision_atomic_and_persistent(self):
        c = Catalog(CONCEPTS, [route()])
        old = c.revision
        revised = deepcopy(CONCEPTS)
        revised['bulk'] = ['bulk stiffness']
        c.replace_concepts(revised)
        self.assertNotEqual(c.revision, old)
        self.assertEqual(c.discover(['bulk modulus'])['coverage'], {'bulk modulus': 'uncovered'})
        self.assertEqual(c.discover(['bulk stiffness'])['coverage'], {'bulk stiffness': 'matched'})
        current = c.discover([req()])
        del revised['bulk']
        with self.assertRaises(ValueError):
            c.replace_concepts(revised)
        self.assertEqual(c.discover([req()]), current)
        updated = route()
        updated['fields'][1]['unit'] = 'MPa'
        c.put(updated)
        self.assertEqual(c.discover([req(unit='GPa')])['coverage'], {'r1': 'uncovered'})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'catalog.ttl'
            c.save(path)
            restored = Catalog.load(path)
            self.assertEqual(restored.discover([req(unit='MPa')]), c.discover([req(unit='MPa')]))

    def test_local_definitions_and_reference_safety(self):
        a = route()
        a['outputSchema']['properties']['k'] = {'$ref': '#/$defs/a~1b'}
        a['outputSchema']['$defs'] = {'a/b': {'$ref': '#/$defs/n~0m'}, 'n~m': {'type': 'number'},
                                     'unused': {'type': 'string'}}
        schema = Catalog(CONCEPTS, [a]).discover([req()])['views'][0]['projectedOutputSchema']
        self.assertEqual(set(schema['$defs']), {'a/b', 'n~m'})
        Draft202012Validator(schema).validate({'id': 'x', 'k': 1, 'g': 2})
        for bad_ref in ('https://example.com/x', '#/$defs/unused/default', '#/$defs/a%2Fb',
                        '#/$defs/a~2b', '#/$defs/missing'):
            with self.subTest(ref=bad_ref):
                bad = deepcopy(a)
                bad['outputSchema']['properties']['k'] = {'$ref': bad_ref}
                with self.assertRaises(ValueError):
                    Catalog(CONCEPTS, [bad])
        bad = deepcopy(a)
        bad['outputSchema']['$defs']['unused']['$schema'] = 'http://json-schema.org/draft-07/schema#'
        with self.assertRaises(ValueError):
            Catalog(CONCEPTS, [bad])
        for k, value in (('$dynamicRef', '#x'), ('$id', 'urn:other'), ('definitions', {})):
            bad = deepcopy(a)
            bad['outputSchema']['$defs']['unused'][k] = value
            with self.assertRaises(ValueError):
                Catalog(CONCEPTS, [bad])

    def test_invalid_requests_and_annotations(self):
        c = Catalog(CONCEPTS, [route()])
        for malformed in ('bulk', [{'conceptId': 'bulk'}], [req(concept='bulk')], [req(), req()],
                          [req(unit=1)], [req(unknown='x')], ['']):
            with self.subTest(request=malformed), self.assertRaises(ValueError):
                c.discover(malformed)
        self.assertFalse(c.discover([])['allRequirementsMatched'])
        for update in ({'identifier': 'false'}, {'concepts': [{}]}, {'groups': [1]},
                       {'provenance': ''}, {'unit': False}):
            bad = route()
            bad['fields'][1].update(update)
            with self.assertRaises(ValueError):
                Catalog(CONCEPTS, [bad])
        bad = route()
        bad['outputSchema']['properties']['k'] = {'type': 'invalid'}
        with self.assertRaises(ValueError):
            Catalog(CONCEPTS, [bad])
        with self.assertRaises(ValueError):
            Catalog({'bulk': [1]}, [route()])


if __name__ == '__main__':
    unittest.main()
