"""Gate B: schema-only import of the exposed historical paper inventory.

Not a live provider contract. The source fixture is immutable DEV evidence.
No archived queries, selected calls, intent labels or answer keys enter the graph.
"""
from hashlib import sha1
import json
from pathlib import Path

from ontology_catalog import Catalog, label

FIXTURE_BLOB = 'fbfe0dcf5b2bfcff325bf673d5bcd3bab5b3985e'
APIS_BLOB = 'da3b3dbda4173fec83d7fee064d01202fa69b04e'
FIXTURE = Path(__file__).resolve().parents[2] / 'tests/fixtures/original_paper_full_replay.json'
SOURCE = 'historical-paper-inventory'


def git_blob(raw):
    return sha1(f'blob {len(raw)}\0'.encode() + raw, usedforsecurity=False).hexdigest()


def api_bytes(apis):
    return json.dumps(apis, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def load_apis(path=FIXTURE, *, extracted=False):
    raw = Path(path).read_bytes()
    if git_blob(raw) != (APIS_BLOB if extracted else FIXTURE_BLOB):
        raise ValueError('historical source blob mismatch')
    data = json.loads(raw)
    apis = data if extracted else data['inventory']['apis']
    if git_blob(api_bytes(apis)) != APIS_BLOB:
        raise ValueError('historical API-only blob mismatch')
    return apis


# Capability categories, NOT OWL equivalence or equality of measured values.
# The historical fields' descriptions identify Voigt vs VRH explicitly.
SHARED = {
    'capability:bulk_modulus': (
        ['bulk modulus', 'bulk_modulus', 'elastic modulus'],
        [('materials_project', 'k_vrh'), ('jarvis', 'bulk_modulus_kv')]),
    'capability:shear_modulus': (
        ['shear modulus', 'shear_modulus', 'elastic modulus'],
        [('materials_project', 'g_vrh'), ('jarvis', 'shear_modulus_gv')]),
    'capability:young_modulus': (['Young modulus', "Young's modulus", 'elastic modulus'], []),
    'capability:research_paper': (
        ['research paper', 'literature search'],
        [(tool, field) for tool, summary in (
            ('arxiv', 'summary'), ('crossref', 'abstract'), ('europe_pmc', 'abstract'),
            ('openalex', 'abstract'), ('pubmed', 'abstract')) for field in ('title', summary)]),
    'capability:citation_count': (['citation count'], [('crossref', 'is-referenced-by-count')]),
}


# Only the literal types recorded in this fixture are mapped. Unknown enum
# domains are deliberately unconstrained/flagged, never guessed from spelling.
SCALARS = {'str': 'string', 'string': 'string', 'float': 'number', 'int': 'integer',
           'integer': 'integer', 'bool': 'boolean', 'boolean': 'boolean',
           'object': 'object', 'dict': 'object', 'datetime': 'string'}


def shape(text):
    if text in SCALARS:
        return {'type': SCALARS[text]}
    if text.startswith('list[') and text.endswith(']') and ' | ' not in text:
        return {'type': 'array', 'items': shape(text[5:-1])}
    if text == 'tuple[float, float]':
        return {'type': 'array', 'prefixItems': [{'type': 'number'}, {'type': 'number'}],
                'minItems': 2, 'maxItems': 2}
    if ' | ' in text:
        alternatives = [shape(part) for part in text.split(' | ')]
        if any(not part for part in alternatives):
            return {}
        return {'anyOf': alternatives}
    return {}


def historical_schema(item):
    raw = item['type']
    # A union with an unknown enum branch cannot be validated from the source.
    unresolved = any(x in raw for x in ('CrystalSystem', 'Ordering'))
    result = {} if unresolved else shape(raw)
    if not result and not unresolved:
        raise ValueError(f'unrecognized historical type: {raw}')
    if unresolved:
        result['x-sr-type-limit'] = 'enum domain absent; validation unproved'
    elif raw in ('dict', 'object', 'datetime'):
        result['x-sr-type-limit'] = 'historical shape/format not fully specified'
    result['x-sr-original-type'] = raw
    if item.get('description'):
        result['description'] = item['description']
    return result


def field_id(tool, name):
    return f'field:{tool}:{name}'


def normalize(apis):
    """Map the exact API-only source into logical schemas and reviewed concepts."""
    if git_blob(api_bytes(apis)) != APIS_BLOB:
        raise ValueError('normalize requires the exact exposed API inventory')
    if (len(apis), sum(len(a['fields']) for a in apis), sum(len(a['parameters']) for a in apis)) != (19, 166, 80):
        raise ValueError('historical inventory cardinality changed')
    concepts = {cid: list(aliases) for cid, (aliases, _) in SHARED.items()}
    members = {}
    for cid, (_, fields) in SHARED.items():
        for pair in fields:
            members.setdefault(pair, []).append(cid)
    available = {(a['name'], f['name']) for a in apis for f in a['fields']}
    if not members.keys() <= available:
        raise ValueError('reviewed capability field missing from source')
    routes = []
    for api in apis:
        tool = api['name']
        fields = {f['name']: f for f in api['fields']}
        params = {p['name']: p for p in api['parameters']}
        if len(fields) != len(api['fields']) or len(params) != len(api['parameters']):
            raise ValueError('duplicate historical field or parameter name')
        groups = {g['name']: g['field_names'] for g in api['field_groups']}
        if any(not set(names) <= fields.keys() for names in groups.values()):
            raise ValueError('historical group member missing')
        annotations = []
        for name, f in fields.items():
            shared = members.get((tool, name), [])
            # Field-local IDs always remain discoverable. Only reviewed shared
            # aliases are delegated to the capability. Other collisions remain
            # explicit ambiguity, even if the historical source calls them equal.
            reserved = {label(a) for cid in shared for a in concepts[cid]}
            local_aliases = sorted({name, *f['aliases']} - {''})
            cid = field_id(tool, name)
            concepts[cid] = [a for a in local_aliases if label(a) not in reserved]
            item = {'path': [name], 'concepts': [cid, *shared],
                    'identifier': f['is_identifier'],
                    'groups': [group for group, names in groups.items() if name in names],
                    'provenance': f'{SOURCE}:{FIXTURE_BLOB}:{tool}:{name}'}
            if f.get('unit'):
                item['unit'] = f['unit']
            if f.get('source_type'):
                item['sourceType'] = f['source_type']
            if api.get('license'):
                # Declared historical label, not current legal verification.
                item['license'] = api['license']
            if shared:
                item['mappingBasis'] = 'reviewed capability category; not numerical equivalence'
            annotations.append(item)
        routes.append({
            'source': SOURCE, 'tool': tool, 'endpoint': 'search',
            'sourceRevision': FIXTURE_BLOB,
            'inputSchema': {'type': 'object', 'properties': {k: historical_schema(p) for k, p in params.items()},
                            'required': [p['name'] for p in api['parameters'] if p['required']],
                            'description': 'Historical logical parameters; native invocation unverified.'},
            'outputSchema': {'type': 'object', 'properties': {k: historical_schema(f) for k, f in fields.items()},
                             'description': 'Historical logical fields; dotted names are literal, not verified wire paths.'},
            'fields': annotations,
        })
    return concepts, routes


def catalog(apis):
    return Catalog(*normalize(apis))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--api-extract', action='store_true', help='verified API-only transport, same pinned bytes')
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('terms', nargs='*', default=['bulk modulus', 'research paper'])
    args = parser.parse_args()
    graph = catalog(load_apis(args.fixture, extracted=args.api_extract))
    if args.snapshot:
        graph.save(args.snapshot)
    print(json.dumps(graph.discover(args.terms), ensure_ascii=False, indent=2))
