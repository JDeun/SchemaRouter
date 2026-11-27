"""Gate A: ordinary RDFLib/SPARQL baseline; synthetic flat-schema DEV only."""
from copy import deepcopy
from hashlib import sha256
import json
import tempfile
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from rdflib import Graph, Literal, Namespace, RDF
from rdflib.plugins.sparql import prepareQuery

NS = Namespace('urn:sr:demo:')
QUERY = prepareQuery('''SELECT DISTINCT ?endpoint ?name WHERE {
    ?tool a sr:Tool ; sr:hasEndpoint ?endpoint .
    ?endpoint sr:returnsField ?field .
    ?field sr:name ?name ; sr:mapsToConcept ?concept .
    ?concept sr:alias ?term .
}''', initNs={'sr': NS})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def fixture():
    # Synthetic schemas: no claim about actual providers or physical values.
    def route(name, argument, fields, meanings, identifiers):
        return dict(id=name, inputSchema=dict(type='object', properties={argument: {'type': 'string'}},
                    required=[argument], additionalProperties=False),
                    outputSchema=dict(type='object', properties=fields, required=list(fields),
                                      additionalProperties=False),
                    concepts=meanings, identifiers=identifiers,
                    fieldMeta={key: {'unit': 'GPa'} for key, concept in meanings.items()
                               if concept in ('bulk', 'shear')},
                    sourceType='synthetic', license='synthetic-fixture-only')
    s, n = {'type': 'string'}, {'type': 'number'}
    return [route('material_a', 'formula', {'id': s, 'k': n, 'gap': n}, {'k': 'bulk'}, ['id']),
            route('material_b', 'formula', {'id': s, 'bulk_modulus': n, 'shear': n},
                  {'bulk_modulus': 'bulk', 'shear': 'shear'}, ['id']),
            route('papers', 'topic', {'doi': s, 'title': s, 'abstract': s, 'venue': s},
                  {'title': 'paper', 'abstract': 'paper'}, ['doi']),
            route('chemistry', 'formula', {'id': s, 'mass': n}, {'mass': 'mass'}, ['id'])]


ALIASES = {'bulk': ('bulk modulus', 'elastic modulus'), 'shear': ('shear modulus', 'elastic modulus'),
           'paper': ('research paper',), 'mass': ('molecular mass',)}


def build(routes):
    g = Graph()
    g.bind('sr', NS)
    for concept, aliases in ALIASES.items():
        for alias in (concept, *aliases):
            g.add((NS['concept:' + concept], NS.alias, Literal(alias)))
    for r in routes:
        # Only the deliberately flat synthetic subset is supported.
        out = r['outputSchema']
        if set(out) != {'type', 'properties', 'required', 'additionalProperties'} or out['type'] != 'object':
            raise ValueError('unsupported output schema')
        if any(set(v) != {'type'} or v['type'] not in ('string', 'number') for v in out['properties'].values()):
            raise ValueError('unsupported output field schema')
        Draft202012Validator.check_schema(r['inputSchema'])
        Draft202012Validator.check_schema(out)
        eid = NS['endpoint:' + r['id']]
        tool = NS['tool:' + r['id']]
        g.add((tool, RDF.type, NS.Tool))
        g.add((tool, NS.hasEndpoint, eid))
        g.add((eid, NS.sourceSchema, Literal(canonical(r))))
        g.add((eid, NS.sourceType, Literal(r['sourceType'])))
        g.add((eid, NS.license, Literal(r['license'])))
        g.add((eid, NS.revision, Literal(sha256(canonical(r).encode()).hexdigest())))
        for name in r['inputSchema']['properties']:
            g.add((eid, NS.acceptsParameter, NS['param:' + r['id'] + ':' + name]))
        for name in r['outputSchema']['properties']:
            f = NS['field:' + r['id'] + ':' + name]
            g.add((eid, NS.returnsField, f))
            g.add((f, NS.name, Literal(name)))
            if 'unit' in r['fieldMeta'].get(name, {}):
                g.add((f, NS.unit, Literal(r['fieldMeta'][name]['unit'])))
            if name in r['concepts']:
                g.add((f, NS.mapsToConcept, NS['concept:' + r['concepts'][name]]))
    return g


def discover(g, terms):
    matches, coverage = {}, {}
    for term in terms:
        literal = Literal(term.strip().lower())
        meanings = set(g.subjects(NS.alias, literal))
        if len(meanings) != 1:
            coverage[term] = 'ambiguous' if meanings else 'uncovered'
            continue
        rows = list(g.query(QUERY, initBindings={'term': literal}))
        coverage[term] = 'matched' if rows else 'uncovered'
        for endpoint, name in rows:
            matches.setdefault(endpoint, set()).add(str(name))
    views = []
    for endpoint, names in sorted(matches.items()):
        r = json.loads(str(g.value(endpoint, NS.sourceSchema)))
        out = deepcopy(r['outputSchema'])
        names.update(r['identifiers'])
        out['properties'] = {k: v for k, v in out['properties'].items() if k in names}
        out['required'] = [k for k in out['required'] if k in names]
        Draft202012Validator.check_schema(out)
        views.append(dict(id=r['id'], inputSchema=r['inputSchema'], projectedOutputSchema=out,
                          fieldMeta={k: v for k, v in r['fieldMeta'].items() if k in names},
                          sourceType=r['sourceType'], license=r['license'],
                          revision=str(g.value(endpoint, NS.revision))))
    return dict(coverage=coverage, views=views)


class BaselineTests(unittest.TestCase):
    def test_two_needs(self):
        result = discover(build(fixture()), ['bulk modulus', 'research paper'])
        views = {r['id']: r for r in result['views']}
        self.assertEqual(set(views), {'material_a', 'material_b', 'papers'})
        self.assertEqual(set(views['material_a']['projectedOutputSchema']['properties']), {'id', 'k'})
        self.assertEqual(set(views['material_b']['projectedOutputSchema']['properties']), {'id', 'bulk_modulus'})
        self.assertEqual(set(views['papers']['projectedOutputSchema']['properties']), {'doi', 'title', 'abstract'})
        for r in fixture():
            if r['id'] in views:
                self.assertEqual(views[r['id']]['inputSchema'], r['inputSchema'])
        self.assertEqual(set(result['coverage'].values()), {'matched'})
        self.assertEqual(views['material_b']['fieldMeta'], {'bulk_modulus': {'unit': 'GPa'}})
        self.assertEqual(views['material_b']['license'], 'synthetic-fixture-only')

    def test_ambiguity_and_missing(self):
        self.assertEqual(discover(build(fixture()), ['elastic modulus', 'citation count']),
                         {'coverage': {'elastic modulus': 'ambiguous', 'citation count': 'uncovered'}, 'views': []})

    def test_persist_reload(self):
        g = build(fixture())
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'catalog.ttl'
            g.serialize(destination=str(p), format='turtle')
            self.assertEqual(discover(g, ['bulk']), discover(Graph().parse(p, format='turtle'), ['bulk']))

    def test_more_than_five_routes(self):
        routes = [dict(fixture()[0], id=f'material_{i}') for i in range(8)]
        self.assertEqual(len(discover(build(routes), ['bulk'])['views']), 8)

    def test_unsupported_nested_output(self):
        routes = fixture()
        routes[0]['outputSchema']['properties']['k'] = {'type': 'object', 'properties': {}}
        with self.assertRaises(ValueError):
            build(routes)

    def test_prepermitted_surface(self):
        self.assertNotIn('material_b', canonical(discover(build(fixture()[:1]), ['bulk'])))


if __name__ == '__main__':
    unittest.main()
