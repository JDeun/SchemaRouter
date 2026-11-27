"""Isolated RDF discovery over complete host-permitted schema surfaces."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from rdflib import Graph, Literal, Namespace, RDF, SKOS
from rdflib.plugins.sparql import prepareQuery

SR = Namespace('urn:sr:poc:')
QUERY = prepareQuery('''SELECT DISTINCT ?route ?path ?field WHERE {
    ?tool sr:hasEndpoint ?route .
    ?route sr:returnsField ?field .
    ?field sr:path ?path ; sr:mapsToConcept ?concept .
}''', initNs={'sr': SR})
ROOT = SR.catalog
DIALECT = "https://json-schema.org/draft/2020-12/schema"
QUALIFIERS = ("unit", "sourceType", "license")


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return sha256(canon(value).encode()).hexdigest()


def node(kind, value):
    return SR[kind + ':' + digest(value)]


def route_key(route):
    return tuple(route[k] for k in ('source', 'tool', 'endpoint'))


def label(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('empty semantic label')
    return value.strip().casefold()


def refs(schema, root):
    """Validate local root definitions only; reject external/dynamic scopes."""
    if not isinstance(schema, dict):
        return set()
    if schema.get('$schema', DIALECT) != DIALECT:
        raise ValueError('unsupported schema dialect')
    if any(k in schema for k in ('$id', '$anchor', '$dynamicAnchor', '$dynamicRef',
                                 '$recursiveRef', '$recursiveAnchor', '$vocabulary',
                                 'definitions', 'dependencies', 'additionalItems')):
        raise ValueError('unsupported reference scope or legacy schema keyword')
    found = set()
    if '$ref' in schema:
        ref = schema['$ref']
        if not isinstance(ref, str) or not ref.startswith('#/$defs/') or '%' in ref:
            raise ValueError('only local root $defs references supported')
        part = ref[8:]
        # Deliberately restrict to named root definitions. Arbitrary pointers
        # can target instance literals rather than schema-valued positions.
        if '/' in part or '~' in part.replace('~1', '').replace('~0', ''):
            raise ValueError('only direct root definition references supported')
        name = part.replace('~1', '/').replace('~0', '~')
        try:
            target = root['$defs'][name]
        except (KeyError, TypeError):
            raise ValueError('missing local reference') from None
        if not isinstance(target, (dict, bool)):
            raise ValueError('reference is not a schema')
        found.add(name)
    # Traverse schema-valued keywords, not instance literals/defaults.
    for key in ('properties', 'patternProperties', '$defs', 'dependentSchemas'):
        for child in schema.get(key, {}).values():
            found |= refs(child, root)
    for key in ('items', 'contains', 'additionalProperties', 'unevaluatedProperties',
                'unevaluatedItems', 'propertyNames', 'not', 'if', 'then', 'else', 'contentSchema'):
        if key in schema:
            found |= refs(schema[key], root)
    for key in ('allOf', 'anyOf', 'oneOf', 'prefixItems'):
        for child in schema.get(key, []):
            found |= refs(child, root)
    return found


def check(schema):
    if not isinstance(schema, dict) or schema.get('$schema', DIALECT) != DIALECT:
        raise ValueError('expected JSON Schema 2020-12 object')
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError:
        raise ValueError('invalid JSON Schema') from None
    refs(schema, schema)


def property_at(schema, path):
    current = schema
    for name in path:
        if not isinstance(current, dict) or current.get('type') != 'object':
            raise ValueError('unsupported annotated property path')
        try:
            current = current['properties'][name]
        except KeyError:
            raise ValueError('annotation not in source schema') from None
    return current


def project(schema, paths):
    """Explicit output VIEW, not a replacement for provider validation."""
    def visit(obj, wanted, root=False):
        # Only simple object ancestors can be safely narrowed in this milestone.
        allowed = {'type', 'properties', 'required', 'additionalProperties', 'title', 'description'}
        if root:
            allowed |= {'$schema', '$defs'}
        if not isinstance(obj, dict) or obj.get('type') != 'object' or set(obj) - allowed:
            raise ValueError('unsupported projection ancestor')
        if obj.get('additionalProperties', True) not in (True, False):
            raise ValueError('unsupported additionalProperties schema')
        names = {p[0] for p in wanted}
        out = {k: deepcopy(v) for k, v in obj.items() if k not in ('$defs', 'properties', 'required', 'additionalProperties')}
        out['properties'] = {}
        for name in sorted(names):
            child = obj['properties'][name]
            rest = {p[1:] for p in wanted if p[0] == name}
            out['properties'][name] = deepcopy(child) if () in rest else visit(child, rest)
        out['required'] = [n for n in obj.get('required', []) if n in names]
        out['additionalProperties'] = False
        return out

    view = visit(schema, paths, root=True)
    needed = refs(view, schema)
    while True:
        more = needed | set().union(*(refs(schema['$defs'][n], schema) for n in needed))
        if more == needed:
            break
        needed = more
    if needed:
        view['$defs'] = {n: deepcopy(schema['$defs'][n]) for n in sorted(needed)}
    check(view)
    return view


class Catalog:
    """A single trusted, already-permitted catalog; not an auth service."""
    def __init__(self, concepts, routes=()):
        if concepts is None:
            raise ValueError('concepts required')
        self._replace(routes, concepts)

    def _replace(self, routes, concepts=None):
        concepts = deepcopy(self._concepts if concepts is None else concepts)
        if not isinstance(concepts, dict) or any(
                not isinstance(k, str) or not k.strip() or not isinstance(v, list)
                or any(not isinstance(a, str) or not a.strip() for a in v)
                for k, v in concepts.items()):
            raise ValueError('concepts require identifiers and alias lists')
        g = Graph()
        for concept, aliases in sorted(concepts.items()):
            c = node('concept', concept)
            g.add((c, RDF.type, SKOS.Concept))
            g.add((c, SR.identifier, Literal(concept)))
            for alias in {concept, *aliases}:
                g.add((c, SKOS.altLabel, Literal(label(alias))))
        data = {}
        for raw in routes:
            r = deepcopy(raw)
            if not isinstance(r, dict) or not {'source', 'tool', 'endpoint', 'sourceRevision',
                                                'inputSchema', 'outputSchema', 'fields'} <= r.keys():
                raise ValueError('invalid source manifest')
            if not isinstance(r['fields'], list):
                raise ValueError('fields must be an array')
            key = route_key(r)
            if any(not isinstance(k, str) or not k.strip() for k in key) or key in data:
                raise ValueError('invalid or duplicate route identity')
            if not isinstance(r.get('sourceRevision'), str) or not r['sourceRevision']:
                raise ValueError('source revision required')
            check(r['inputSchema'])
            check(r['outputSchema'])
            e = node('route', key)
            t = node('tool', key[:2])
            g.add((t, RDF.type, SR.Tool))
            g.add((t, SR.hasEndpoint, e))
            g.add((e, SR.manifest, Literal(canon(r))))
            g.add((e, SR.sourceRevision, Literal(r['sourceRevision'])))
            for name in r['inputSchema'].get('properties', {}):
                p = node('parameter', [key, name])
                g.add((e, SR.acceptsParameter, p))
                g.add((p, SR.path, Literal(canon([name]))))
            seen = set()
            for f in r['fields']:
                if not isinstance(f, dict) or not isinstance(f.get('path'), list):
                    raise ValueError('annotation path must be an array')
                path = tuple(f['path'])
                if not path or any(not isinstance(n, str) or not n for n in path) or path in seen:
                    raise ValueError('invalid or duplicate annotation path')
                property_at(r['outputSchema'], path)
                seen.add(path)
                if not isinstance(f.get('provenance'), str) or not f['provenance']:
                    raise ValueError('annotation provenance required')
                field = node('field', [key, path])
                g.add((e, SR.returnsField, field))
                g.add((field, SR.path, Literal(canon(path))))
                if any(not isinstance(f.get(k, []), list) for k in ('concepts', 'groups')):
                    raise ValueError('concepts and groups must be arrays')
                if any(not isinstance(group, str) or not group for group in f.get('groups', [])):
                    raise ValueError('invalid field group')
                if type(f.get('identifier', False)) is not bool:
                    raise ValueError('identifier must be boolean')
                for concept in f.get('concepts', []):
                    if not isinstance(concept, str) or concept not in concepts:
                        raise ValueError('unknown declared concept')
                    g.add((field, SR.mapsToConcept, node('concept', concept)))
                for meta in ('unit', 'sourceType', 'license', 'provenance'):
                    if meta in f:
                        if not isinstance(f[meta], str) or not f[meta]:
                            raise ValueError('invalid declared metadata')
                        g.add((field, SR[meta], Literal(f[meta])))
                if f.get('identifier', False):
                    g.add((field, SR.identifierField, Literal(True)))
                for group in f.get('groups', []):
                    g.add((field, SR.memberOf, node('group', [key, group])))
            data[key] = r
        ordered = [data[k] for k in sorted(data)]
        revision = digest({'concepts': concepts, 'routes': ordered})
        g.add((ROOT, SR.concepts, Literal(canon(concepts))))
        g.add((ROOT, SR.revision, Literal(revision)))
        self._graph, self._routes, self._concepts, self.revision = g, data, concepts, revision

    def put(self, route):
        key = route_key(route)
        self._replace([r for k, r in self._routes.items() if k != key] + [route])
        return self.revision

    def remove(self, key):
        self._replace([r for k, r in self._routes.items() if k != tuple(key)])
        return self.revision

    def replace_concepts(self, concepts):
        """Atomic alias/vocabulary revision for the current permitted routes."""
        if concepts is None:
            raise ValueError('concepts required')
        self._replace(self._routes.values(), concepts)
        return self.revision

    def save(self, path):
        path = Path(path)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
            name = tmp.name
        try:
            self._graph.serialize(destination=name, format='turtle')
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)

    @classmethod
    def load(cls, path):
        g = Graph().parse(data=Path(path).read_text(encoding='utf-8'), format='turtle')
        result = cls(json.loads(str(g.value(ROOT, SR.concepts))),
                     [json.loads(str(v)) for v in g.objects(None, SR.manifest)])
        if set(result._graph) != set(g):
            raise ValueError('snapshot graph does not match manifests')
        return result

    def discover(self, terms, max_routes=None):
        """Search agent-supplied concepts; exact declared qualifiers, not inference.

        String terms use the alias vocabulary. Structured requirements carry a
        unique id and exactly one of concept (alias) or conceptId (exact ID).
        Qualifiers restrict direct matches; group/identifier adjuncts are not
        additional evidence of the requirement. The host supplies the entire
        already-permitted schema surface, including refs and annotations.
        """
        if max_routes is not None and (type(max_routes) is not int or max_routes < 1):
            raise ValueError('invalid caller budget')
        if not isinstance(terms, (list, tuple)):
            raise ValueError('requirements must be a list or tuple')
        requests = {}
        for term in terms:
            req = {'id': term, 'concept': term} if isinstance(term, str) else deepcopy(term)
            if (not isinstance(req, dict) or set(req) - {'id', 'concept', 'conceptId', *QUALIFIERS}
                    or 'id' not in req or len({'concept', 'conceptId'} & req.keys()) != 1
                    or any(not isinstance(v, str) or not v.strip() for v in req.values())):
                raise ValueError('invalid semantic requirement')
            if req['id'] in requests:
                raise ValueError('duplicate requirement id')
            requests[req['id']] = req

        # Every lookup and returned count is relative to this permitted graph.
        hits, results = {}, {}
        for rid, req in requests.items():
            if 'conceptId' in req:
                concepts = {node('concept', req['conceptId'])} if req['conceptId'] in self._concepts else set()
            else:
                concepts = set(self._graph.subjects(SKOS.altLabel, Literal(label(req['concept']))))
            receipt = dict(requirement=req, status='uncovered', matchingRoutes=0,
                           returnedRoutes=0, omittedRoutes=0, unsupportedProjectionRoutes=0)
            results[rid] = receipt
            if len(concepts) != 1:
                receipt['status'] = 'ambiguous' if concepts else 'uncovered'
                if concepts:
                    receipt['candidateConceptIds'] = sorted(
                        str(self._graph.value(c, SR.identifier)) for c in concepts)
                continue
            concept = next(iter(concepts))
            receipt['conceptId'] = str(self._graph.value(concept, SR.identifier))
            candidates = set()
            for route, path, field in self._graph.query(QUERY, initBindings={'concept': concept}):
                if any(k in req and (field, SR[k], Literal(req[k])) not in self._graph
                       for k in QUALIFIERS):
                    continue
                hits.setdefault(route, {}).setdefault(rid, set()).add(tuple(json.loads(str(path))))
                candidates.add(route)
            receipt['matchingRoutes'] = len(candidates)

        views = []
        omitted = 0
        for route in sorted(hits, key=lambda e: route_key(json.loads(str(self._graph.value(e, SR.manifest))))):
            r = json.loads(str(self._graph.value(route, SR.manifest)))
            direct = set().union(*hits[route].values())
            paths = direct | {tuple(f['path']) for f in r['fields'] if f.get('identifier')}
            groups = {group for f in r['fields'] if tuple(f['path']) in direct for group in f.get('groups', [])}
            paths |= {tuple(f['path']) for f in r['fields'] if groups.intersection(f.get('groups', []))}
            try:
                view = project(r['outputSchema'], paths)
            except ValueError:
                for rid in hits[route]:
                    results[rid]['unsupportedProjectionRoutes'] += 1
                continue
            if max_routes is not None and len(views) >= max_routes:
                omitted += 1
                for rid in hits[route]:
                    results[rid]['omittedRoutes'] += 1
                continue
            for rid in hits[route]:
                results[rid]['returnedRoutes'] += 1
            fields = [deepcopy(f) for f in r['fields'] if any(tuple(f['path'])[:len(p)] == p for p in paths)]
            views.append(dict(route=list(route_key(r)), sourceRevision=r['sourceRevision'],
                              inputSchema=r['inputSchema'], projectedOutputSchema=view,
                              fields=fields, projectionKind='schema_view_only',
                              matches=[dict(requirementId=rid, paths=[list(p) for p in sorted(hits[route][rid])])
                                       for rid in requests if rid in hits[route]],
                              adjunctPaths=[list(p) for p in sorted({tuple(f['path']) for f in fields} - direct)],
                              projectionPaths=[list(p) for p in sorted(paths)]))
        for receipt in results.values():
            if receipt['returnedRoutes']:
                receipt['status'] = 'matched'
            elif receipt['omittedRoutes']:
                receipt['status'] = 'budget_limited'
            elif receipt['unsupportedProjectionRoutes']:
                receipt['status'] = 'unsupported_projection'
            # 'matched' means a returned direct match, not all alternatives or
            # a complete task. Report the loss of alternatives explicitly.
            receipt['allMatchingRoutesReturned'] = bool(receipt['matchingRoutes']) and (
                receipt['matchingRoutes'] == receipt['returnedRoutes'])
        status = {rid: receipt['status'] for rid, receipt in results.items()}
        return dict(revision=self.revision, coverage=status, views=views, omittedRoutes=omitted,
                    requirementResults=list(results.values()),
                    allRequirementsMatched=bool(status) and all(v == 'matched' for v in status.values()))
