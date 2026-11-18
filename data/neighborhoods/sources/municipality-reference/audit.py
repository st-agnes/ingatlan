#!/usr/bin/env python3
"""Check current stored OSM candidates against selected historical municipal polygons.

Vertex fractions are diagnostics, not polygon area overlap percentages. This
does not assign a city automatically and does not certify current boundaries.
"""
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parents[3]
EPSILON = 1e-8


def polygons(geometry):
    return [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']


def bounds(points):
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points)]


def ring_location(ring, point):
    x, y = point
    inside = False
    for a, b in zip(ring, ring[1:]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        length = math.hypot(dx, dy)
        cross = dx*(y-a[1])-dy*(x-a[0])
        if (abs(cross) <= EPSILON*length
                and min(a[0], b[0])-EPSILON <= x <= max(a[0], b[0])+EPSILON
                and min(a[1], b[1])-EPSILON <= y <= max(a[1], b[1])+EPSILON):
            return 'boundary'
        if (a[1] > y) != (b[1] > y) and x < dx*(y-a[1])/dy+a[0]:
            inside = not inside
    return 'inside' if inside else 'outside'


def location(reference, point):
    bbox = reference['bbox']
    if not (bbox[0]-EPSILON <= point[0] <= bbox[2]+EPSILON
            and bbox[1]-EPSILON <= point[1] <= bbox[3]+EPSILON):
        return 'outside'
    for polygon in reference['polygons']:
        outer = ring_location(polygon[0], point)
        if outer == 'boundary':
            return outer
        if outer != 'inside':
            continue
        holes = [ring_location(ring, point) for ring in polygon[1:]]
        if 'boundary' in holes:
            return 'boundary'
        if 'inside' not in holes:
            return 'inside'
    return 'outside'


def centroid(geometry):
    weight = x_total = y_total = 0
    for polygon in polygons(geometry):
        for index, ring in enumerate(polygon):
            twice_area = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(ring, ring[1:]))
            if not twice_area:
                continue
            cx = sum((a[0]+b[0])*(a[0]*b[1]-b[0]*a[1]) for a, b in zip(ring, ring[1:]))/(3*twice_area)
            cy = sum((a[1]+b[1])*(a[0]*b[1]-b[0]*a[1]) for a, b in zip(ring, ring[1:]))/(3*twice_area)
            w = abs(twice_area)*(1 if index == 0 else -1)
            weight += w
            x_total += cx*w
            y_total += cy*w
    return [x_total/weight, y_total/weight]


def audit_frankhegy(references, reference_sha256):
    source_path = 'data/neighborhoods/sources/whosonfirst/85901113.geojson'
    raw = (REPOSITORY_ROOT/source_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'b123e85b6521118b12259eb094215446ff43bff316dc5cf925fe46b2a088ee9e'
    feature = json.loads(raw)
    points = sorted({tuple(point) for polygon in polygons(feature['geometry']) for ring in polygon for point in ring})
    bbox = bounds(points)
    center = [(bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2]
    middle = centroid(feature['geometry'])
    result = {'sourcePath': source_path, 'sourceSha256': hashlib.sha256(raw).hexdigest(),
              'id': 'wof:85901113', 'name': 'Frankhegy', 'bbox': bbox,
              'bboxCenter': center, 'planarAreaCentroid': middle, 'uniqueVertices': len(points),
              'referenceGeojsonSha256': reference_sha256, 'notAreaOverlap': True, 'references': {}}
    for name in ['Budaörs', 'Budapest']:
        reference = references[name]
        counts = {'inside': 0, 'boundary': 0, 'outside': 0}
        for point in points:
            counts[location(reference, point)] += 1
        result['references'][name] = {
            'referenceId': reference['id'], 'bboxCenter': location(reference, center),
            'planarAreaCentroid': location(reference, middle), 'uniqueVertices': counts,
            'coveredVertexPercent': round(100*(counts['inside']+counts['boundary'])/len(points), 4)}
    (ROOT/'wof-frankhegy-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')


def main():
    manifest = json.loads((ROOT/'manifest.json').read_text())
    raw = (ROOT/'municipalities.geojson').read_bytes()
    assert len(raw) == manifest['geojson']['bytes']
    assert hashlib.sha256(raw).hexdigest() == manifest['geojson']['sha256']
    references = {}
    for feature in json.loads(raw)['features']:
        poly = polygons(feature['geometry'])
        points = [p for polygon in poly for ring in polygon for p in ring]
        references[feature['properties']['name']] = {'id': feature['id'], 'polygons': poly, 'bbox': bounds(points)}
    audit_frankhegy(references, manifest['geojson']['sha256'])
    node = r'''
import {createHash} from 'node:crypto';
import {readFile,readdir} from 'node:fs/promises';
import {osmGeometry,classifyOsmBoundary} from './scripts/neighborhoods/osm.mjs';
const directory='data/neighborhoods/sources/openstreetmap',features=[],skipped=[];
for(const file of (await readdir(directory)).filter(n=>n.endsWith('.source.json')).sort()){
 const manifest=JSON.parse(await readFile(`${directory}/${file}`,'utf8'));
 const path=`${directory}/${manifest.file??manifest.rawFile??file.replace(/\.source\.json$/,'.json')}`;
 const bytes=await readFile(path),document=JSON.parse(bytes),index=new Map(document.elements.map(e=>[`${e.type}:${e.id}`,e]));
 for(const element of document.elements){
  if(classifyOsmBoundary(element.tags,manifest.city)?.boundaryKind!=='neighbourhood')continue;
  const id=`osm:${element.type}:${element.id}`;
  try {features.push({id,name:element.tags.name,queryCity:manifest.city,sourcePath:path,
    sourceSha256:createHash('sha256').update(bytes).digest('hex'),geometry:osmGeometry(element,index)});}
  catch(error){skipped.push({id,name:element.tags.name,queryCity:manifest.city,reason:error.message});}
 }
}
process.stdout.write(JSON.stringify({features,skipped}));
'''
    collected = json.loads(subprocess.run(['node', '--input-type=module', '-e', node],
                           cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True, timeout=45).stdout)
    records = []
    for candidate in collected['features']:
        points = sorted({tuple(point) for polygon in polygons(candidate['geometry']) for ring in polygon for point in ring})
        bbox = bounds(points)
        center = [(bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2]
        middle = centroid(candidate['geometry'])
        corners = [[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]]]
        matches = {}
        for name, reference in references.items():
            rb = reference['bbox']
            if bbox[2] < rb[0] or bbox[0] > rb[2] or bbox[3] < rb[1] or bbox[1] > rb[3]:
                continue
            counts = {'inside': 0, 'boundary': 0, 'outside': 0}
            for point in points:
                counts[location(reference, point)] += 1
            matches[name] = {'referenceId': reference['id'], 'bboxCenter': location(reference, center),
                             'planarAreaCentroid': location(reference, middle),
                             'bboxCorners': [location(reference, point) for point in corners],
                             'uniqueVertices': counts,
                             'insideVertexPercent': round(100*counts['inside']/len(points), 4),
                             'coveredVertexPercent': round(100*(counts['inside']+counts['boundary'])/len(points), 4)}
        own = matches.get(candidate['queryCity'], {})
        status = ('reference-not-selected' if candidate['queryCity'] not in references
                  else 'clear-query-context-outlier' if own.get('bboxCenter', 'outside') == 'outside'
                  and own.get('planarAreaCentroid', 'outside') == 'outside' and own.get('coveredVertexPercent', 0) < 50
                  else 'border-or-snapshot-detail' if own.get('coveredVertexPercent', 0) < 100
                  else 'reference-contained-vertices')
        records.append({key: value for key, value in candidate.items() if key != 'geometry'} | {
            'bbox': bbox, 'bboxCenterCoordinates': center, 'planarAreaCentroidCoordinates': middle,
            'uniqueVertexCount': len(points), 'classification': status, 'references': matches})
    counts = {}
    for record in records:
        counts[record['queryCity']] = counts.get(record['queryCity'], 0)+1
    result = {'method': 'Historical municipal reference point-in-polygon diagnostics; unique vertices, bbox center/corners and planar polygon area centroid.',
              'notAreaOverlap': True, 'noAutomaticReassignment': True, 'coordinateEpsilonDegrees': EPSILON,
              'limitations': ['Vertex percentages are not polygon area overlap percentages.',
                             'No exact edge containment or current boundary certification is performed.',
                             'A concave polygon centroid or bbox center may be outside its own polygon.',
                             'Minor border discrepancies between the 2025 reference and current OSM are diagnostic only.'],
              'referenceManifest': 'data/neighborhoods/sources/municipality-reference/manifest.json',
              'referenceGeojsonSha256': manifest['geojson']['sha256'], 'candidateCountsByQueryCity': counts,
              'records': records, 'skippedGeometry': collected['skipped']}
    (ROOT/'association-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'counts': counts, 'outliers': [{k: v for k, v in record.items() if k in ['id', 'name', 'queryCity', 'classification', 'references']}
                     for record in records if record['classification'] == 'clear-query-context-outlier'],
                     'skipped': len(collected['skipped'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
