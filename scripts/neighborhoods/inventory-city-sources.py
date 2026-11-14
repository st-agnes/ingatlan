#!/usr/bin/env python3
"""Export all 348 city research targets and optional OSM website leads.

OSM website tags are discovery leads, not verified municipal homepages.
No network requests are made. --pbf requires pyosmium.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'data/neighborhoods/sources/nationwide-inventory/municipality-website-candidates.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pbf', type=Path)
    args = parser.parse_args()
    inventory = json.loads((ROOT / 'data/neighborhoods/nationwide-inventory.json').read_text())
    cities = [r for r in inventory['municipalities'] if r['legalStatus'] in ('capital', 'city', 'county_rank_city')]
    byname = {r['municipality']: r for r in cities}
    candidates = {name: [] for name in byname}
    pbf_source = None
    if args.pbf:
        import osmium
        pbf_source = json.loads(Path(str(args.pbf) + '.source.json').read_text())
        processor = osmium.FileProcessor(args.pbf).with_filter(
            osmium.filter.EntityFilter(osmium.osm.NODE)).with_filter(
            osmium.filter.TagFilter(('place', 'city'), ('place', 'town')))
        for node in processor:
            name = node.tags.get('name:hu') or node.tags.get('name')
            if name not in byname:
                continue
            for key in ('website', 'contact:website', 'url'):
                value = node.tags.get(key)
                if not value:
                    continue
                candidates[name].append({'tag': key, 'value': value,
                    'osmType': 'node', 'osmId': node.id,
                    'sourceUrl': f'https://www.openstreetmap.org/node/{node.id}',
                    'objectTimestamp': str(node.timestamp),
                    'officialMunicipalityWebsiteVerified': False})
    result = []
    for city in cities:
        name = city['municipality']
        refs = city['nameReferences']
        result.append({'municipality': name, 'kshCode': city['kshCode'],
            'county': city['county'], 'legalStatus': city['legalStatus'],
            'legalStatusReferenceDate': inventory['referenceDate'],
            'urbanNeighborhoodInventoryStatus': city['urbanNeighborhoodInventoryStatus'],
            'reviewedDocumentSources': [{'url': r['sourceUrl'], 'category': r['category'],
                'nameEntries': len(r['names']), 'title': r['title']} for r in refs],
            'documentHostnames': sorted(set(urlsplit(r['sourceUrl']).hostname for r in refs)),
            'websiteCandidates': candidates[name],
            'officialHomepageUrl': None,
            'homepageVerificationStatus': 'pending',
            'nextSourceReview': 'Locate and verify municipal ITS/FVS/regulation/map sources and individual neighborhood boundaries.'})
    output = {'schemaVersion': 1, 'referenceDate': inventory['referenceDate'],
        'scope': 'All 348 current Hungarian cities, including the capital. This is a source research queue, not nationwide neighborhood completeness.',
        'municipalityIdentitySource': {'url': 'https://www.ksh.hu/docs/helysegnevtar/hnt_letoltes_2026.xlsx',
                                     'license': 'CC-BY-4.0', 'attribution': 'Forrás: KSH'},
        'websiteCandidateSource': pbf_source,
        'notes': ['The KSH workbook has no official municipality website column.',
                  'OSM website tags are unverified leads. A URL may be stale, unofficial or refer to another entity.',
                  'A reviewed document host is not automatically the municipal homepage.',
                  'Missing website candidates do not establish that no municipal website or neighborhood source exists.'],
        'summary': {'cities': len(result), 'citiesWithReviewedDocuments': sum(bool(r['reviewedDocumentSources']) for r in result),
                    'citiesWithWebsiteCandidates': sum(bool(r['websiteCandidates']) for r in result),
                    'websiteCandidateTags': sum(len(r['websiteCandidates']) for r in result)},
        'cities': result}
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(output['summary']))


if __name__ == '__main__':
    main()
