#!/usr/bin/env python3
"""Bounded current-name audit only; never edits Eger source geometry or registries."""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import unicodedata

import osmium
from shapely.geometry import shape

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCE = ROOT / 'data/neighborhoods/sources/municipal-eger-semantic-next/proposed-semantic-revision.geojson'
COUNTRY = ROOT / 'data/neighborhoods/sources/country-osm'
PBF = ROOT / '.local/neighborhoods/hungary-latest.osm.pbf'
PBF_SHA = '224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
PRIOR_POLICY = OUT / 'manual-current-name-review-next.json'
TAGS = ['name', 'alt_name', 'alt_name:hu']

# These are displayed current labels, not aliases or name-equality rules. The
# historical source qualifiers remain intact and all five records stay outside
# the strict current-name count.
RELATED = {
    'Felsőváros': ('Felsőváros (Északi városrész)', 'qualified_label_not_full_equality',
                   'The complete current primary label includes an additional parenthetical qualifier. No explicit alt_name supplies the shorter source label; no words are dropped.'),
    'Lajosváros – nyugat': ('Lajosváros', 'broader_label_not_directional_source_name',
                           'The current broader label does not independently corroborate the historical west qualifier.'),
    'Lajosváros kelet': ('Lajosváros', 'broader_label_not_directional_source_name',
                        'The current broader label does not independently corroborate the historical east qualifier.'),
    'Hajdúhegy észak': ('Hajdúhegy', 'broader_label_not_directional_source_name',
                       'The current broader label does not independently corroborate the historical north qualifier.'),
    'Belváros kelet': ('Belváros', 'broader_label_not_directional_source_name',
                      'The current broader label does not independently corroborate the historical east qualifier.'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1048576), b''):
            h.update(part)
    return h.hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def normalized(value):
    # Same whole-label orthographic rule documented in the earlier89-name
    # report. Every letter, Hungarian accent, word, digit and Roman numeral stays.
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def current_labels(tags):
    for tag in TAGS:
        value = tags.get(tag)
        if not value:
            continue
        parts = value.split(';') if tag.startswith('alt_name') else [value]
        for part in parts:
            if part.strip():
                yield tag, part.strip(), value


def verify_pbf(points):
    actual_hash = sha(PBF)
    if actual_hash != PBF_SHA:
        raise ValueError('Pinned PBF changed')
    expected = {f['properties']['source']['osmId']: f for f in points}
    actual = {}; counts = Counter()
    class Collector(osmium.SimpleHandler):
        def node(self, node):
            counts['nativeSelectedNodeCallbacks'] += 1
            if node.id in expected:
                actual[node.id] = {'coordinates': [node.location.lon, node.location.lat],
                                   'tags': dict(node.tags), 'objectVersion': node.version,
                                   'objectTimestamp': str(node.timestamp)}
    with osmium.io.Reader(str(PBF), osmium.osm.osm_entity_bits.NOTHING) as reader:
        header = {key: reader.header().get(key) for key in ['generator', 'osmosis_replication_timestamp',
                  'osmosis_replication_sequence_number', 'osmosis_replication_base_url']}
    Collector().apply_file(str(PBF), filters=[osmium.filter.EntityFilter(osmium.osm.NODE), osmium.filter.IdFilter(list(expected))])
    records = []; mismatches = []
    for ident, feature in sorted(expected.items()):
        source = feature['properties']['source']
        fields = {key: source[key] for key in ['tags', 'objectVersion', 'objectTimestamp']}
        fields['coordinates'] = feature['geometry']['coordinates']
        differences = [key for key in fields if ident not in actual or actual[ident].get(key) != fields[key]]
        if differences:
            mismatches.append({'osmNodeId': ident, 'fields': differences})
        records.append({'osmNodeId': ident, 'allOriginalFieldsMatch': not differences,
                        'comparedFields': ['complete coordinates', 'complete tags', 'objectVersion', 'objectTimestamp']})
    if len(actual) != len(expected) or mismatches:
        raise ValueError('Current Eger node PBF readback mismatch: ' + str(mismatches))
    return {'path': str(PBF.relative_to(ROOT)), 'bytes': PBF.stat().st_size, 'sha256': actual_hash,
            'header': header, 'requestedSameCityNodeCount': len(expected), 'freshlyVerifiedNodeCount': len(actual),
            'allOriginalFieldsMatch': True, 'mismatches': mismatches, 'errors': [],
            'counts': dict(counts), 'records': records}


def build():
    source_bytes = SOURCE.read_bytes(); source_doc = json.loads(source_bytes)
    source_features = [f for f in source_doc['features'] if f['properties'].get('boundaryKind') == 'neighbourhood']
    if len(source_features) != 23 or any(f['properties']['municipality'] != 'Eger' for f in source_features):
        raise ValueError('Eger source-name cohort is not the expected23 quarters')
    node_gzip = (COUNTRY / 'named-nodes.geojson.gz').read_bytes()
    parent_gzip = (COUNTRY / 'municipalities.geojson.gz').read_bytes()
    node_bytes, parent_bytes = gzip.decompress(node_gzip), gzip.decompress(parent_gzip)
    all_points = json.loads(node_bytes)['features']
    points = [f for f in all_points if f['properties'].get('municipality') == 'Eger']
    parents = json.loads(parent_bytes)['features']
    parent = next(f for f in parents if f['properties']['name'] == 'Eger')
    relation_id = parent['properties']['source']['osmId']
    if relation_id != 1418156 or parent['properties']['source']['pbfSha256'] != PBF_SHA:
        raise ValueError('Eger municipality provenance differs')
    municipality = shape(parent['geometry'])
    city_checks = []
    for feature in points:
        p = feature['properties']; ident = p['source']['osmId']
        check = {'osmNodeId': ident, 'geometryType': feature['geometry']['type'],
                 'municipality': p.get('municipality'), 'municipalityId': p.get('municipalityId'),
                 'municipalityOsmId': p.get('municipalityOsmId'),
                 'municipalityEvidence': p.get('municipalityEvidence'),
                 'coveringMunicipalityOsmIds': p.get('coveringMunicipalityOsmIds'),
                 'completeObjectGeometryCoveredBySameSnapshotEgerMunicipality': municipality.covers(shape(feature['geometry'])),
                 'originalPbfSha256Matches': p['source']['pbfSha256'] == PBF_SHA}
        if not (check['completeObjectGeometryCoveredBySameSnapshotEgerMunicipality'] and check['originalPbfSha256Matches']
                and check['municipalityId'] == 'city:Eger' and check['municipalityOsmId'] == 'osm:relation:1418156'
                and check['municipalityEvidence'] == 'source_full_containment'
                and p.get('place') in {'suburb', 'quarter', 'neighbourhood'}):
            raise ValueError('Current Eger object has inadmissible city/place evidence: ' + str(ident))
        city_checks.append(check)
    pbf = verify_pbf(points)
    checks_by_id = {r['osmNodeId']: r for r in city_checks}
    records = []
    for feature in source_features:
        p = feature['properties']; name = p['name']; matches = []
        for current in points:
            tags = current['properties']['source']['tags']
            for tag, value, literal in current_labels(tags):
                if normalized(name) == normalized(value):
                    method = ('explicit_current_alt_name_tag' if tag.startswith('alt_name') else
                              'exact_primary_name' if value == name else 'whole_label_orthographic_normalization')
                    ident = current['properties']['source']['osmId']
                    matches.append({'method': method, 'matchingTag': tag, 'matchedCurrentLabel': value,
                                    'fullLiteralTagValue': literal, 'normalizedWholeLabelKey': normalized(value),
                                    'currentObject': current, 'municipalityEvidence': checks_by_id[ident],
                                    'freshOriginalPbfReadbackVerified': True,
                                    'evidenceRole': 'Current same-city name only; neither source-quarter identity equivalence nor historical/current extent, accuracy or address assignment is approved.'})
        related = []
        if name in RELATED:
            literal, evidence_class, reason = RELATED[name]
            for current in points:
                if current['properties']['source']['tags'].get('name') == literal:
                    ident = current['properties']['source']['osmId']
                    related.append({'evidenceClass': evidence_class, 'fullCurrentLiteralLabel': literal,
                                    'strictWholeLabelEquality': False, 'countsAsStrictCurrentSourceNameMatch': False,
                                    'aliasApplied': False, 'reason': reason,
                                    'currentObject': current, 'municipalityEvidence': checks_by_id[ident],
                                    'freshOriginalPbfReadbackVerified': True,
                                    'sourceExtentApproved': False})
        if matches:
            status = ('current_osm_explicit_alt_name_match' if any(m['matchingTag'].startswith('alt_name') for m in matches) else
                      'current_osm_exact_primary_name_match' if any(m['method'] == 'exact_primary_name' for m in matches) else
                      'current_osm_whole_label_orthographic_match')
        else:
            status = 'unknown_current_exact_source_name_in_checked_place_node_cohort'
        records.append({'sourceFeatureId': feature.get('id'), 'sourceName': name, 'municipality': 'Eger',
                        'sourcePlanId': p.get('sourcePlanId'), 'sourcePdfDrawingIndex': p.get('sourcePdfDrawingIndex'),
                        'sourceSchemaDate': p.get('sourceSchemaDate'), 'sourceBasePlanReferenceYear': p.get('sourceBasePlanReferenceYear'),
                        'normalizedWholeSourceNameKey': normalized(name), 'nameEvidenceStatus': status,
                        'strictCurrentSameCityNameMatch': bool(matches), 'strictMatches': matches,
                        'qualifiedOrBroaderCurrentLabelsWithoutEquality': related,
                        'currentNameEvidenceIsBoundaryEvidence': False,
                        'historicalSourceOrCurrentQuarterExtentApproved': False,
                        'currentLegalQuarterStatusApproved': False, 'usableForAddressAssignment': False,
                        'unknownMeaning': None if matches else 'No admissible whole-label equality or explicit current alt_name in the checked snapshot cohort. This is not absence, discontinuation or a rejection of the displayed qualified/broader current labels.'})
    status_counts = Counter(r['nameEvidenceStatus'] for r in records)
    matched_ids = sorted({m['currentObject']['properties']['source']['osmId'] for r in records for m in r['strictMatches']})
    unknown = [r['sourceName'] for r in records if not r['strictCurrentSameCityNameMatch']]
    fingerprints = []
    for path in [SOURCE, COUNTRY / 'named-nodes.geojson.gz', COUNTRY / 'municipalities.geojson.gz', COUNTRY / 'manifest.json', PRIOR_POLICY]:
        fingerprints.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    result = {'schemaVersion': 1, 'auditDate': '2026-11-14',
              'scope': 'Current names only for the23 newly qualified historical Eger source-quarter names; separate from the frozen previous89-name audit and all boundary approvals.',
              'sourceCohort': {'path': str(SOURCE.relative_to(ROOT)), 'sha256': digest(source_bytes),
                               'selection': 'boundaryKind == neighbourhood', 'selectedSourceNames': len(source_features)},
              'currentCatalogue': {'path': str((COUNTRY / 'named-nodes.geojson.gz').relative_to(ROOT)),
                                   'storedGzipSha256': digest(node_gzip), 'uncompressedSha256': digest(node_bytes),
                                   'nationalPointCount': len(all_points), 'sameCityEgerPointCount': len(points),
                                   'selection': 'Archived current place=suburb|quarter|neighbourhood nodes associated to Eger; not every possible named object or a statutory quarter inventory.',
                                   'completeCurrentObjects': 'eger-current-name-evidence.geojson'},
              'municipalityEvidence': {'path': str((COUNTRY / 'municipalities.geojson.gz').relative_to(ROOT)),
                                       'storedGzipSha256': digest(parent_gzip), 'uncompressedSha256': digest(parent_bytes),
                                       'osmRelationId': relation_id,
                                       'sameCityRule': 'Complete current object geometry is covered by same-snapshot Eger relation1418156, and original catalogue municipalityId/containment evidence agrees. Historical source polygons are never used for name selection.',
                                       'all25CompleteCurrentObjectsRechecked': all(r['completeObjectGeometryCoveredBySameSnapshotEgerMunicipality'] for r in city_checks),
                                       'records': city_checks},
              'freshOriginalPbfVerification': pbf,
              'matchingPolicy': {'priorDocumentedOrthographicRule': str(PRIOR_POLICY.relative_to(ROOT)),
                                 'normalization': 'NFKC, casefold, keep every alphanumeric codepoint and Hungarian accent; discard only punctuation/separators. Compare the complete resulting label, retaining every word/direction/digit. Actual admitted orthographic differences in this cohort are three whitespace joins.',
                                 'currentTagsChecked': TAGS, 'altNameSemicolonListsSplit': True,
                                 'primaryNameParenthesesOrQualifiersDropped': False, 'historicalOldNameTagsUsed': False,
                                 'semanticAliasesInvented': False, 'substringFuzzyOrNearestPointMatching': False,
                                 'broaderLabelsSubstitutedForDirectionalSourceNames': False,
                                 'qualifiedAndBroaderLabelsShownAsWeakerEvidenceOnly': True},
              'summary': {'sourceNamesReviewed': len(records), 'strictCurrentNameMatches': len(records)-len(unknown),
                          'exactPrimaryNameMatches': status_counts['current_osm_exact_primary_name_match'],
                          'orthographicWholeLabelMatches': status_counts['current_osm_whole_label_orthographic_match'],
                          'explicitCurrentAltNameMatches': status_counts['current_osm_explicit_alt_name_match'],
                          'sourceNamesWithoutStrictWholeLabelMatch': len(unknown), 'noStrictWholeLabelMatchNames': unknown,
                          'sourceNamesWithQualifiedLabelButNoEquality': [r['sourceName'] for r in records if any(x['evidenceClass'] == 'qualified_label_not_full_equality' for x in r['qualifiedOrBroaderCurrentLabelsWithoutEquality'])],
                          'sourceNamesWithBroaderLabelButNoDirectionalEquality': [r['sourceName'] for r in records if any(x['evidenceClass'] == 'broader_label_not_directional_source_name' for x in r['qualifiedOrBroaderCurrentLabelsWithoutEquality'])],
                          'uniqueStrictMatchedOriginalNodeIds': matched_ids, 'uniqueStrictMatchedOriginalNodeCount': len(matched_ids),
                          'all25EgerCatalogueObjectsFreshlyVerifiedInOriginalPbf': pbf['freshlyVerifiedNodeCount'] == 25,
                          'boundaryOrGeometryApprovals': 0, 'frozenSourcePropertyChanges': 0, 'globalRegistryOrExportChanges': 0},
              'records': records, 'inputFingerprints': fingerprints,
              'limitations': ['Present means a community-mapped label in the pinned2026-11-12 snapshot, not a municipal or legal designation. Object timestamps are edit times, not dated municipal name declarations.',
                              'The14 strict name matches provide no evidence that the historical statutory source footprints equal current ordinary, ITS, legal or cadastral extents, or that georeferencing is accurate.',
                              'Nine labels lack strict whole-label equality in this bounded catalogue. Qualified/broader current labels are preserved separately; unknown never means absent or discontinued.',
                              'No new web search was used; no unsupported semantic alias, directional qualifier removal or cross-quarter merger was applied.'],
              'networkUsed': False, 'frozenSourceFilesModified': False, 'globalRegistryOrExportsModified': False,
              'sourceBoundaryExtentApproved': False, 'claimedAbsoluteAccuracyMetres': None, 'usableForAddressAssignment': False}
    if result['summary']['strictCurrentNameMatches'] != 14 or len(unknown) != 9 or len(points) != 25:
        raise ValueError('Bounded Eger name-audit counts differ from independent policy review')
    csv_stream = io.StringIO(); writer = csv.writer(csv_stream, lineterminator='\n')
    writer.writerow(['source_feature_id', 'source_name', 'source_plan_id', 'name_evidence_status', 'strict_current_name_match',
                     'current_literal_labels', 'matched_node_ids', 'matching_tags', 'qualified_or_broader_labels_without_equality', 'boundary_approval'])
    for r in records:
        writer.writerow([r['sourceFeatureId'], r['sourceName'], r['sourcePlanId'], r['nameEvidenceStatus'], str(r['strictCurrentSameCityNameMatch']).lower(),
                         '; '.join(m['matchedCurrentLabel'] for m in r['strictMatches']),
                         '; '.join(str(m['currentObject']['properties']['source']['osmId']) for m in r['strictMatches']),
                         '; '.join(m['matchingTag'] for m in r['strictMatches']),
                         '; '.join(x['fullCurrentLiteralLabel'] for x in r['qualifiedOrBroaderCurrentLabelsWithoutEquality']), 'false'])
    outputs = {'eger-current-name-review.json': encode(result), 'eger-current-name-review.csv': csv_stream.getvalue(),
               'eger-current-name-evidence.geojson': encode({'type': 'FeatureCollection', 'features': points})}
    audit_manifest = {'schemaVersion': 1, 'status': 'frozen_current_name_only_research', 'source23CohortSha256': digest(source_bytes),
                      'inputs': fingerprints, 'originalPbf': {'path': str(PBF.relative_to(ROOT)), 'sha256': pbf['sha256'], 'header': pbf['header']},
                      'outputs': [{'path': str((OUT / name).relative_to(ROOT)), 'sha256': digest(content.encode())} for name, content in outputs.items()],
                      'reproducer': {'path': str(Path(__file__).resolve().relative_to(ROOT)), 'sha256': sha(Path(__file__))},
                      'command': 'PYTHONPATH=.local/geodata python data/neighborhoods/research/eger-current-name-review.py --check',
                      'boundaryApprovals': 0, 'frozenEgerSourceChanges': 0, 'globalChanges': 0}
    outputs['eger-current-name-input-manifest.json'] = encode(audit_manifest)
    return outputs, result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    outputs, result = build()
    for name, content in outputs.items():
        path = OUT / name
        if args.check:
            if path.read_text() != content:
                raise ValueError('Frozen Eger name audit changed: ' + name)
        else:
            path.write_text(content)
    print(json.dumps({'reviewed': 23, 'strictMatched': result['summary']['strictCurrentNameMatches'],
                      'withoutStrictMatch': result['summary']['sourceNamesWithoutStrictWholeLabelMatch'],
                      'freshPbfNodes': result['freshOriginalPbfVerification']['freshlyVerifiedNodeCount'],
                      'boundaryApprovals': 0, 'check': args.check}))
