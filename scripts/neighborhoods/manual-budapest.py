#!/usr/bin/env python3
"""Trace the legally described XXIII Orbánhegy using pinned OSM street lines.

The legal description does not say how to bridge present road carriageways or
the mapped Millennium utca dead end to the railway. These are explicit inferred
segments in the output, rather than claims that the source contains a boundary.
No point buffer, bounding rectangle, random radius or unnamed closure is used.
"""
import collections
import hashlib
import heapq
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'data/neighborhoods/manual/sources/budapest-orban-input.geojson'
OUTPUT = ROOT / 'data/neighborhoods/manual/budapest-orban.geojson'
SCALE = (75300, 111200)


def distance(a, b):
    return math.hypot((a[0]-b[0])*SCALE[0], (a[1]-b[1])*SCALE[1])


def projection(p, a, b):
    d = [(b[i]-a[i])*SCALE[i] for i in range(2)]
    q = [(p[i]-a[i])*SCALE[i] for i in range(2)]
    t = max(0, min(1, sum(d[i]*q[i] for i in range(2))/sum(v*v for v in d)))
    return t, tuple(a[i]+t*(b[i]-a[i]) for i in range(2))


def cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def extension_intersection(a, b, rail):
    v = (b[0]-a[0], b[1]-a[1])
    found = []
    for i, (p, q) in enumerate(zip(rail, rail[1:])):
        w = (q[0]-p[0], q[1]-p[1])
        den = cross(v, w)
        if abs(den) < 1e-20:
            continue
        z = (p[0]-b[0], p[1]-b[1])
        t, u = cross(z, w)/den, cross(z, v)/den
        if t >= 0 and 0 <= u <= 1:
            c = (b[0]+t*v[0], b[1]+t*v[1])
            found.append((distance(b, c), i+u, c))
    if not found:
        raise ValueError('Street continuation does not intersect source railway')
    return min(found)


def build():
    source_bytes = INPUT.read_bytes()
    features = json.loads(source_bytes)['features']
    rail_feature = next(f for f in features if f['properties']['source']['osmId'] == 348178874)
    rail = [tuple(c) for c in rail_feature['geometry']['coordinates']]
    streets = [f for f in features if f is not rail_feature]
    original = []
    adjacency = collections.defaultdict(set)
    for f in streets:
        for a, b in zip(f['geometry']['coordinates'], f['geometry']['coordinates'][1:]):
            a, b = tuple(a), tuple(b)
            original.append((a, b, f['id']))
            adjacency[a].add(b)
            adjacency[b].add(a)
    components = {}
    for p in adjacency:
        if p in components:
            continue
        component = len(components)
        queue = [p]
        components[p] = component
        for u in queue:
            for v in adjacency[u]:
                if v not in components:
                    components[v] = component
                    queue.append(v)

    # Only bridge separate source components in the named legal road corridor.
    # Every bridge actually used is retained as a measured inferred segment.
    splits = [dict([(0, a), (1, b)]) for a, b, _ in original]
    bridges = []
    for p in adjacency:
        for i, (a, b, source_id) in enumerate(original):
            if components[p] == components[a]:
                continue
            t, q = projection(p, a, b)
            length = distance(p, q)
            if length <= 40:
                splits[i][t] = q
                bridges.append((p, q, length))
    graph = collections.defaultdict(list)
    def edge(a, b, source_id, inferred=False):
        length = distance(a, b)
        # Prefer actual source geometry unless a carriageway connection is needed.
        cost = length + (1000 if inferred else 0)
        graph[a].append((b, cost, source_id, inferred))
        graph[b].append((a, cost, source_id, inferred))
    for i, (_, _, source_id) in enumerate(original):
        points = [p for _, p in sorted(splits[i].items())]
        for a, b in zip(points, points[1:]):
            edge(a, b, source_id)
    for a, b, _ in bridges:
        edge(a, b, None, True)
    start = (19.1225428, 47.3871412)  # Grassalkovich service-branch source terminus.
    end = (19.1127502, 47.3772068)    # Millennium utca source terminus.
    queue = [(0, start)]
    distances, previous = {start: 0}, {}
    while queue:
        cost, u = heapq.heappop(queue)
        if cost != distances[u]:
            continue
        if u == end:
            break
        for v, step, source_id, inferred in graph[u]:
            new_cost = cost+step
            if new_cost < distances.get(v, math.inf):
                distances[v] = new_cost
                previous[v] = (u, source_id, inferred)
                heapq.heappush(queue, (new_cost, v))
    if end not in previous:
        raise ValueError('Named legal corridor remains disconnected')
    path, proof = [end], []
    u = end
    while u != start:
        v, source_id, inferred = previous[u]
        proof.append({'from': v, 'to': u, 'sourceLineId': source_id,
                      'inferred': inferred, 'lengthMetres': round(distance(v, u), 2),
                      **({'reason': 'Approximate connection across separately mapped carriageways/junction in the legally named street corridor.'} if inferred else {})})
        path.append(v)
        u = v
    path.reverse()
    proof.reverse()
    north_len, north_position, north = extension_intersection((19.1224169, 47.3871783), start, rail)
    south_len, south_position, south = extension_intersection((19.1123427, 47.377369), end, rail)
    assert north_len < 100 and south_len < 500 and north_position < south_position
    middle_rail = rail[math.floor(north_position)+1:math.ceil(south_position)]
    ring = [north] + path + [south] + list(reversed(middle_rail)) + [north]
    inferred = [p for p in proof if p['inferred']]
    inferred.extend([
        {'from': north, 'to': start, 'inferred': True, 'lengthMetres': round(north_len, 2),
         'reason': 'Straight continuation of the final Grassalkovich service-road source segment to the source railway; legal text names their common limit.'},
        {'from': end, 'to': south, 'inferred': True, 'lengthMetres': round(south_len, 2),
         'reason': 'Straight continuation of the final Millennium utca source segment to the source railway. The legal text names Millennium utca/Millenniumtelep but the mapped street stops short; this continuation is inferred and needs review.'}])
    definitions = json.loads((ROOT/'data/neighborhoods/manual/budapest-definitions.json').read_text())
    definition = next(r for r in definitions['records'] if r['referenceName'] == 'Orbánhegy')
    used = sorted({p['sourceLineId'] for p in proof if p['sourceLineId']} | {rail_feature['id']})
    properties = dict(name='Orbánhegy (XXIII. kerület)', referenceName='Orbánhegy', municipality='Budapest', district=23,
        boundaryKind='neighbourhood', method='legal_street_and_railway_trace_with_explicit_inferred_connections',
        sourceDocuments=definition['sourceDocuments'], sourceParagraph=definition['sourceParagraph'],
        evidenceUrls=[d['url'] for d in definition['sourceDocuments']], sourceLineIds=used,
        source={'provider':'manual-openstreetmap','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors',
                'attributionUrl':'https://www.openstreetmap.org/copyright',
                'inputPath':str(INPUT.relative_to(ROOT)), 'inputSha256':hashlib.sha256(source_bytes).hexdigest(),
                'pbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a',
                'osmTimestamp':'2026-11-12T21:23:05Z'},
        quality='inferred_candidate_boundary', reviewStatus='manual_inference_needs_review',
        reviewNotes=['Road and railway centre lines approximate the legally described boundary.',
                     'Present split carriageways require short inferred junction connections.',
                     'The Millennium utca-to-railway continuation is uncertain and explicitly measured.'],
        sourceIsOfficial=False, sourceIsHardBoundary=False, usableForAddressAssignment=False,
        constructionProof={'streetSegments':proof, 'railSourceLineId':rail_feature['id'],
                           'railSourceStartPosition':north_position,'railSourceEndPosition':south_position,
                           'inferredSegments':inferred, 'inferredSegmentCount':len(inferred),
                           'totalInferredLengthMetres':round(sum(x['lengthMetres'] for x in inferred),2)})
    result={'type':'FeatureCollection','features':[{'type':'Feature','id':'manual:Budapest:23:Orbanhegy',
             'properties':properties,'geometry':{'type':'Polygon','coordinates':[ring]}}]}
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(OUTPUT.relative_to(ROOT)), 'vertices':len(ring),
                      'inferredSegments':inferred},ensure_ascii=False))


if __name__ == '__main__':
    build()
