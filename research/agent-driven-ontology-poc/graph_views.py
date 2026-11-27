"""Equal-information graph/flat views. Agent chooses tools and fields; no routing."""
from copy import deepcopy
from ontology_catalog import Catalog, SR, node, route_key, canon, project


def text(s):
    return ' '.join(s.casefold().replace('_', ' ').split())


def field_id(rid, i):
    return f'{rid}.f{i}'


class Views:
    def __init__(self, concepts, routes):
        catalog = Catalog(concepts, routes)
        self.revision = catalog.revision
        self.concepts = deepcopy(concepts)
        self.routes = {}
        self.fields = {}
        self.links = []
        for i, key in enumerate(sorted(catalog._routes)):
            route = catalog._routes[key]
            rid = f'r{i}'
            endpoint = node('route', key)
            tool = node('tool', key[:2])
            if (tool, SR.hasEndpoint, endpoint) not in catalog._graph:
                raise ValueError('missing RDF endpoint relation')
            self.routes[rid] = deepcopy(route)
            for j, f in enumerate(route['fields']):
                fid = field_id(rid, j)
                field = node('field', [key, tuple(f['path'])])
                if (endpoint, SR.returnsField, field) not in catalog._graph:
                    raise ValueError('missing RDF field relation')
                self.fields[fid] = (rid, deepcopy(f))
                self.links.append([rid, 'returns', fid])
                for cid in f.get('concepts', []):
                    if (field, SR.mapsToConcept, node('concept', cid)) not in catalog._graph:
                        raise ValueError('missing RDF concept relation')
                    self.links.append([fid, 'means', cid])
                for group in f.get('groups', []):
                    if (field, SR.memberOf, node('group', [key, group])) not in catalog._graph:
                        raise ValueError('missing RDF group relation')
                    self.links.append([fid, 'memberOf', f'{rid}:{group}'])

    def view(self, representation, route_ids=None):
        if representation not in ('flat', 'graph'):
            raise ValueError('invalid representation')
        if route_ids is not None and (not isinstance(route_ids, list) or
                any(not isinstance(rid, str) or rid not in self.routes for rid in route_ids)):
            raise ValueError('invalid route IDs')
        chosen = list(self.routes) if route_ids is None else sorted(set(route_ids))
        selected = set(chosen)
        fields = {fid: f for fid, (rid, f) in self.fields.items() if rid in selected}
        cids = set(self.concepts) if route_ids is None else {
            cid for f in fields.values() for cid in f.get('concepts', [])}
        concepts = {cid: deepcopy(self.concepts[cid]) for cid in sorted(cids)}
        if representation == 'flat':
            rows = {}
            for rid in chosen:
                route = deepcopy(self.routes[rid])
                route['fields'] = {field_id(rid, i): f for i, f in enumerate(route['fields'])}
                rows[rid] = route
            return {'concepts': concepts, 'routes': rows}
        # The route retains complete original input/output schemas. Only the
        # annotation relationship representation changes; no lossy summarizing.
        nodes = {rid: {k: deepcopy(v) for k, v in self.routes[rid].items() if k != 'fields'}
                 for rid in chosen}
        annotations = {fid: {k: deepcopy(v) for k, v in f.items()
                             if k not in ('concepts', 'groups')} for fid, f in fields.items()}
        edges = [deepcopy(e) for e in self.links if e[0] in selected or e[0] in fields]
        return {'concepts': concepts, 'routeNodes': nodes, 'fieldNodes': annotations, 'edges': edges}

    def find(self, query):
        """Common literal locator for both dynamic arms. All matches, no ranking."""
        if not isinstance(query, str) or not text(query):
            raise ValueError('nonempty literal query required')
        q = text(query)
        concepts = {cid: deepcopy(aliases) for cid, aliases in self.concepts.items()
                    if any(q in text(v) for v in [cid, *aliases])}
        routes = [rid for rid, r in self.routes.items()
                  if any(q in text(r[k]) for k in ('source', 'tool', 'endpoint'))]
        hits = []
        for fid, (rid, f) in self.fields.items():
            route = self.routes[rid]
            schema = route['outputSchema']
            for name in f['path']:
                schema = schema['properties'][name]
            terms = [fid, *f['path'], schema.get('description', ''),
                     *[f.get(k, '') for k in ('unit', 'sourceType', 'license')],
                     *f.get('concepts', []),
                     *[a for cid in f.get('concepts', []) for a in self.concepts[cid]]]
            if any(q in text(s) for s in terms):
                hits.append({'route': rid, 'tool': route['tool'], 'field': fid,
                             'path': f['path'], 'concepts': f.get('concepts', [])})
        return {'routeIds': routes, 'concepts': concepts, 'fieldHits': deepcopy(hits)}

    def selected_schema(self, rid, field_ids):
        """Projection only after explicit agent selection; no group expansion."""
        if rid not in self.routes or not isinstance(field_ids, list) or not field_ids:
            raise ValueError('route and selected fields required')
        if any(fid not in self.fields or self.fields[fid][0] != rid for fid in field_ids):
            raise ValueError('field outside selected route')
        route = self.routes[rid]
        paths = {tuple(self.fields[fid][1]['path']) for fid in field_ids}
        return {'route': list(route_key(route)), 'sourceRevision': route['sourceRevision'],
                'inputSchema': deepcopy(route['inputSchema']),
                'projectedOutputSchema': project(route['outputSchema'], paths),
                'projectionKind': 'schema_view_only'}


def flatten(graph):
    """Inverse for the frozen manifest subset; checks representation parity."""
    routes = {rid: {**deepcopy(route), 'fields': {}} for rid, route in graph['routeNodes'].items()}
    fields = {fid: {**deepcopy(f), 'concepts': [], 'groups': []}
              for fid, f in graph['fieldNodes'].items()}
    owners = {}
    for a, relation, b in graph['edges']:
        if relation == 'returns':
            if b in owners:
                raise ValueError('duplicate field owner')
            owners[b] = a
            routes[a]['fields'][b] = fields[b]
        elif relation == 'means':
            if b not in graph['concepts']:
                raise ValueError('unknown concept')
            fields[a]['concepts'].append(b)
        elif relation == 'memberOf':
            rid, group = b.split(':', 1)
            if owners[a] != rid:
                raise ValueError('cross-route group')
            fields[a]['groups'].append(group)
        else:
            raise ValueError('unknown edge')
    if owners.keys() != fields.keys():
        raise ValueError('unowned field')
    return {'concepts': deepcopy(graph['concepts']), 'routes': routes}
