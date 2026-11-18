#!/usr/bin/env python3
"""Retain all useful named Debrecen service polygons under the throughput policy."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'data/neighborhoods/sources/municipal-debrecen-remaining-next'
SOURCE_PATH = SOURCE / 'debrecen-source-service.geojson'
SERVICE = 'https://services5.arcgis.com/lH5T9SRuBL94XELY/arcgis/rest/services/Debrecen_neh%C3%A9zf%C3%A9mszennyez%C3%A9s_v%C3%A1rosr%C3%A9szek_szerint_WFL1/FeatureServer/0'
ITEM = 'https://www.arcgis.com/home/item.html?id=a04e2a4ff4d2467c8bb6eb640f515b51'
NAME_EVIDENCE = 'data/neighborhoods/sources/public-arcgis-quarter-next/debrecen-fvs-quarter-name-inventory.json'
ALIASES = {
    15: ('József Attila-telep', ['József Attila telep']),
    52: ('Pércsikert', ['Percsikert']),
    56: ('Veres Péter-kert', ['Veres Péter kert', 'Veres Péter lakótelep']),
    57: ('Hőforrás', ['Hőforras']),
    70: ('Wesselényi-lakótelep', ['Wesselényi lakótelep', 'Wesselényi']),
}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    raw_bytes = SOURCE_PATH.read_bytes()
    source = json.loads(raw_bytes)
    dispositions = json.loads((SOURCE / 'all77-dispositions.json').read_text())
    prior = {row['FID']: row['disposition'] for row in dispositions['records']}
    features, excluded = [], []
    for original in source['features']:
        p = original['properties']
        fid = p['FID']
        if fid in (4, 11):
            excluded.append({
                'sourceId': fid,
                'sourceName': p['nev'],
                'reason': ('generic_area_label_not_a_distinct_named_place' if fid == 4
                           else 'duplicate_literal_name_with_known_identity_conflict'),
                'retainedRawSourcePath': str(SOURCE_PATH.relative_to(ROOT)),
                'preferredSourceId': 67 if fid == 11 else None,
                'note': ('Közterület means generic public space.' if fid == 4 else
                         'FID11 is labelled Széchenyikert but lies by Újkert; FID67 is the actual '
                         'same-name source polygon. Retain existing OSM Újkert separately; do not '
                         'rename FID11 or invent a further place.'),
            })
            continue
        name, aliases = ALIASES.get(fid, (p['nev'], []))
        features.append({
            'type': 'Feature',
            'id': f'debrecen-arcgis:{fid}',
            'geometry': original['geometry'],
            'properties': {
                'name': name,
                'sourceName': p['nev'],
                'aliases': aliases,
                'municipality': 'Debrecen',
                'municipalityId': 'city:Debrecen',
                'method': 'source_polygon',
                'boundaryKind': 'named_urban_area',
                'sourceCategory': p['tipus'],
                'isBroaderParent': fid == 39,
                'sourceId': fid,
                'priorDisposition': prior[fid],
                'admissionPolicy': '20261114-throughput-all-machine-polygons',
                'geometryUnmodified': True,
                'estimated': False,
                'accuracy': 'Published source polygon; absolute accuracy and source reference year unknown.',
                'usableForApproximateFiltering': True,
                'aliasesEvidencePath': NAME_EVIDENCE if fid in ALIASES else None,
                'source': {
                    'provider': 'public-arcgis',
                    'url': ITEM,
                    'serviceUrl': SERVICE,
                    'sourcePath': str(SOURCE_PATH.relative_to(ROOT)),
                    'sourceSha256': sha256(raw_bytes).hexdigest(),
                    'sourceFeatureId': fid,
                    'geometrySha256': sha256(json.dumps(original['geometry'], separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(),
                    'sourceCrs': 'EPSG:4326',
                    'hostingEditDateUtc': '2025-06-02T23:33:23.324Z',
                    'boundaryReferenceYear': None,
                    'reuseRights': 'Not established in published service metadata; original evidence retained.',
                },
            },
        })
    assert len(features) == 75
    assert len({f['properties']['name'] for f in features}) == 75
    assert all(f['geometry'] == source['features'][f['properties']['sourceId'] - 1]['geometry'] for f in features)
    payload = {'type': 'FeatureCollection', 'coordinateReferenceSystem': 'EPSG:4326', 'features': features}
    save(OUT / 'features.geojson', payload)
    existing = json.loads((ROOT / 'data/neighborhoods/neighborhoods.geojson').read_text())['features']
    estimated = json.loads((ROOT / 'data/neighborhoods/estimated-candidates.geojson').read_text())['features']
    old_names = {f['properties']['name'] for f in existing + estimated if f['properties'].get('municipality') == 'Debrecen'}
    canonical_aliases = {alias: canonical for canonical, aliases in ALIASES.values() for alias in aliases}
    old_names = {canonical_aliases.get(name, name) for name in old_names}
    new_names = sorted({f['properties']['name'] for f in features} - old_names)
    union_names = sorted(old_names | {f['properties']['name'] for f in features})
    save(OUT / 'summary.json', {
        'schemaVersion': 1,
        'municipality': 'Debrecen',
        'policy': '20261114-throughput-all-machine-polygons',
        'rawSourceRecords': len(source['features']),
        'exportedSourcePolygons': len(features),
        'distinctExportedNames': len({f['properties']['name'] for f in features}),
        'previousSelectedDistinctNames': len(old_names),
        'additionalDistinctNamesAgainstPreviousSelected': len(new_names),
        'additionalNames': new_names,
        'combinedDistinctNamesWithPreviousSelected': len(union_names),
        'includedPreviousDispositions': dict(Counter(prior[f['properties']['sourceId']] for f in features)),
        'excluded': excluded,
        'explicitAliases': [{'sourceFID': fid, 'canonicalName': name, 'aliases': aliases}
                            for fid, (name, aliases) in ALIASES.items()],
        'geometryChanges': 0,
        'generatedCircles': 0,
        'inputSha256': sha256(raw_bytes).hexdigest(),
        'inputPath': str(SOURCE_PATH.relative_to(ROOT)),
        'outputSha256': sha256((OUT / 'features.geojson').read_bytes()).hexdigest(),
        'scope': 'All useful named source polygons, including parent Józsa and named industrial/forest areas. '
                 'Cross-source overlaps and historical differences are intentionally allowed. Root catalogue '
                 'deduplication selects one boundary per municipality/name; this packet preserves alternatives.',
        'remainingKnownReferenceGaps': ['Köztemető', 'Alsójózsa', 'Felsőjózsa', 'Észak-Nyugati Gazdasági Övezet'],
        'possibleReferenceAliasesNotForced': [
            ['Déli ipari terület', 'Déli Gazdasági Övezet'],
            ['Debreceni Egyetem tud-tech park', 'Debreceni Egyetemi Ipari Park'],
        ],
        'nationalCompletenessClaimed': False,
    })
    print(json.dumps({'exported': len(features), 'additionalNames': len(new_names), 'unionWithPrevious': len(union_names)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
