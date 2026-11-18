#!/usr/bin/env python3
"""Build the offline Magyar Posta street catalogue, using only the standard library.

The runtime gzip is a JSON array [header, street, street, ...], so .NET can read
one record at a time. It contains street metadata only: the source does not
provide house numbers or coordinates. Acquisition is a separate, bounded step.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/streets'
SOURCE = DATA / 'sources/StreetNames.xml.gz'
MANIFEST = DATA / 'source.json'
OUTPUT = ROOT / 'dist/data/streets.json.gz'
AUDIT = DATA / 'coverage.json'
DEMO_OUTPUT = ROOT / 'dist/street-demo-data.js'
SOURCE_URL = 'http://httpmegosztas.posta.hu/PartnerExtra/Out/StreetNames.xml'
ROMANS = ('I.', 'II.', 'III.', 'IV.', 'V.', 'VI.', 'VII.', 'VIII.', 'IX.',
          'X.', 'XI.', 'XII.', 'XIII.', 'XIV.', 'XV.', 'XVI.', 'XVII.',
          'XVIII.', 'XIX.', 'XX.', 'XXI.', 'XXII.', 'XXIII.')
FIELDS = {'zipcode', 'city', 'name', 'type'}
DEMO_STREETS = {
    ('Budapest', 'II.', 'Fény utca'), ('Budapest', 'II.', 'Margit körút'),
    ('Budapest', 'II.', 'Pasaréti út'), ('Budapest', 'XI.', 'Bartók Béla út'),
    ('Budapest', 'XI.', 'Budafoki út'), ('Budapest', 'XI.', 'Karinthy Frigyes út'),
    ('Budapest', 'XIII.', 'Pannónia utca'), ('Budapest', 'XIII.', 'Pozsonyi út'),
    ('Budapest', 'XIII.', 'Váci út'), ('Debrecen', None, 'Böszörményi út'),
    ('Debrecen', None, 'Egyetem sugárút'), ('Szeged', None, 'Tisza Lajos körút'),
}


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def clean(value):
    return ' '.join(unicodedata.normalize('NFC', value or '').split())


def identity_text(value):
    """Preserve accents while ignoring typography-only space/case differences."""
    return clean(value).casefold()


def folded(value):
    return ''.join(character for character in unicodedata.normalize('NFD', clean(value))
                   if unicodedata.category(character) != 'Mn').casefold()


def street_id(city, district, name, street_type):
    # A JSON tuple avoids delimiter ambiguity; zip codes are deliberately absent.
    identity = [identity_text(city), district or '', identity_text(name), identity_text(street_type)]
    return 'street:' + hashlib.sha256(packed(identity).encode('utf-8')).hexdigest()[:24]


def local_name(tag):
    return tag.rsplit('}', 1)[-1].casefold()


def xml_rows(content):
    """Read direct field children or attributes, with namespace-safe field names."""
    count = 0
    tag_counts = Counter()
    record_counts = Counter()
    for _, element in ET.iterparse(io.BytesIO(content), events=('end',)):
        tag_counts[element.tag] += 1
        fields = {local_name(key): clean(value) for key, value in element.attrib.items()}
        fields.update({local_name(child.tag): clean(child.text) for child in element
                       if local_name(child.tag) in FIELDS})
        if FIELDS.issubset(fields):
            count += 1
            record_counts[element.tag] += 1
            yield {key: fields[key] for key in sorted(FIELDS)}
            element.clear()
    if not count:
        raise ValueError('The XML contains no records with ZipCode, city, name and type fields.')
    if any(tag_counts[tag] != valid_count for tag, valid_count in record_counts.items()):
        raise ValueError('A source record is missing required ZipCode, city, name or type fields.')


def city_resolver(cities, overrides):
    exact = {identity_text(city): city for city in cities}
    accents = {}
    for city in cities:
        accents.setdefault(folded(city), []).append(city)
    for raw, canonical in overrides.items():
        if canonical not in cities:
            raise ValueError('A reviewed city mapping has an unknown canonical target: ' + canonical)

    def resolve(raw):
        if raw in overrides:
            return overrides[raw], None, 'reviewedMapping'
        city = exact.get(identity_text(raw))
        if city:
            return city, None, 'canonical'
        # The explicit Budapest district suffix is stronger evidence than a zip.
        match = re.fullmatch(r'Budapest\s+([IVX]+)\.?\s*(?:ker(?:ület|\.)?)?', raw, re.IGNORECASE)
        if match and match[1].upper() + '.' in ROMANS:
            return 'Budapest', match[1].upper() + '.', 'explicitDistrict'
        matches = accents.get(folded(raw), [])
        if len(matches) == 1:
            return matches[0], None, 'unambiguousAccentVariant'
        return None, None, 'unmapped'

    return resolve


def postal_district(postal_code):
    """Only ordinary Budapest street postcodes encode a district.

    Special 100x/1xxx mail handling codes do not establish a district. Source
    postcodes outside 1011..1239 with a 01..23 district and nonzero final digit
    remain unresolved and are reported, rather than assigned a guessed district.
    """
    if re.fullmatch(r'1[0-9]{2}[1-9]', postal_code):
        number = int(postal_code[1:3])
        if 1 <= number <= 23:
            return ROMANS[number - 1]
    return None


def deterministic_gzip(content):
    buffer = io.BytesIO()
    # GzipFile writes the portable OS=255 header; gzip.compress(mtime=0) in
    # Python 3.11/3.12 can instead copy zlib's platform-dependent OS byte.
    with gzip.GzipFile(filename='', fileobj=buffer, mode='wb', compresslevel=9, mtime=0) as archive:
        archive.write(content)
    return buffer.getvalue()


def build(content, manifest, cities, overrides=None):
    source_hash = hashlib.sha256(content).hexdigest()
    if source_hash != manifest['sha256']:
        raise ValueError('The source XML SHA-256 differs from the reviewed source manifest.')
    resolve_city = city_resolver(cities, overrides or {})
    grouped = {}
    source_city_counts = Counter()
    mapping_counts = Counter()
    unmapped = Counter()
    unresolved_budapest = Counter()
    explicit_conflicts = Counter()
    postal_rows = Counter()
    source_rows = 0
    for raw in xml_rows(content):
        source_rows += 1
        source_city_counts[raw['city']] += 1
        if not re.fullmatch(r'[0-9]{4}', raw['zipcode']):
            raise ValueError(f'Source row {source_rows} has a non-four-digit postcode.')
        if not raw['city'] or not raw['name']:
            raise ValueError(f'Source row {source_rows} has no city or street name.')
        city, explicit_district, mapping_kind = resolve_city(raw['city'])
        mapping_counts[mapping_kind] += 1
        if city is None:
            unmapped[(raw['city'], raw['zipcode'])] += 1
            continue
        district = explicit_district
        if city == 'Budapest':
            inferred = postal_district(raw['zipcode'])
            if explicit_district and inferred and explicit_district != inferred:
                explicit_conflicts[(raw['city'], raw['zipcode'])] += 1
            district = explicit_district or inferred
            if district is None:
                unresolved_budapest[raw['zipcode']] += 1
        street_name = clean(raw['name'] + ' ' + raw['type'])
        identifier = street_id(city, district, raw['name'], raw['type'])
        key = (city, district, identity_text(raw['name']), identity_text(raw['type']))
        if identifier in grouped and grouped[identifier]['key'] != key:
            raise ValueError('A stable street ID hash collision occurred.')
        row = grouped.setdefault(identifier, {'key': key, 'variants': set(), 'postalCodes': set(), 'aliases': set()})
        row['variants'].add((raw['name'], raw['type'], street_name))
        row['postalCodes'].add(raw['zipcode'])
        row['aliases'].add(street_name)
        if raw['city'] != city:
            row['aliases'].add(raw['city'] + ', ' + street_name)
        postal_rows[(identifier, raw['zipcode'])] += 1
    if explicit_conflicts:
        raise ValueError('Explicit Budapest districts conflict with ordinary postal districts: ' +
                         packed([[*key, count] for key, count in sorted(explicit_conflicts.items())]))
    rows = []
    for identifier, grouped_row in grouped.items():
        city, district, _, _ = grouped_row['key']
        name, street_type, street_name = min(grouped_row['variants'])
        place = city + (' ' + district + ' kerület' if district else '')
        row = {'id': identifier, 'city': city, 'district': district, 'name': name,
               'type': street_type, 'streetName': street_name,
               'label': place + ', ' + street_name,
               'postalCodes': sorted(grouped_row['postalCodes']),
               'aliases': sorted(grouped_row['aliases'] - {street_name})}
        bounds = {'city': 255, 'name': 255, 'type': 128, 'streetName': 384, 'label': 600}
        if any(len(row[key]) > bound for key, bound in bounds.items()):
            raise ValueError('A source street exceeds the runtime text length bounds: ' + identifier)
        if any(len(alias) > 384 for alias in row['aliases']):
            raise ValueError('A source alias exceeds the runtime text length bounds: ' + identifier)
        rows.append(row)
    rows.sort(key=lambda row: (folded(row['city']), row['district'] or '', folded(row['streetName']), row['id']))
    covered = sorted({row['city'] for row in rows}, key=lambda city: (folded(city), city))
    missing = sorted(set(cities) - set(covered), key=lambda city: (folded(city), city))
    stats = {'sourceRows': source_rows, 'sourceCityNames': len(source_city_counts),
             'streetCount': len(rows), 'postalStreetPairs': len(postal_rows),
             'duplicatePostalRows': sum(count - 1 for count in postal_rows.values()),
             'multiPostcodeStreets': sum(len(row['postalCodes']) > 1 for row in rows),
             'canonicalMunicipalities': len(cities), 'coveredMunicipalities': len(covered),
             'missingMunicipalities': missing, 'unmappedSourceRows': sum(unmapped.values()),
             'unresolvedBudapestRows': sum(unresolved_budapest.values())}
    dataset_version = hashlib.sha256(packed([1, source_hash, rows]).encode('utf-8')).hexdigest()
    header = {'schemaVersion': 1, 'datasetVersion': dataset_version,
              'sourceSha256': source_hash, 'count': len(rows), 'stats': stats,
              'source': {'name': 'Magyar Posta Partner Extra – Belföldi utcanevek',
                         'url': manifest.get('url', SOURCE_URL), 'retrievedOn': manifest['retrievedOn']}}
    audit = {'schemaVersion': 1, 'datasetVersion': header['datasetVersion'],
             'sourceSha256': source_hash, 'stats': stats,
             'cityResolution': dict(sorted(mapping_counts.items())),
             'sourceCities': dict(sorted(source_city_counts.items())),
             'unmappedCities': [{'sourceCity': city, 'postalCode': postal_code, 'sourceRows': count}
                                for (city, postal_code), count in sorted(unmapped.items())],
             'unresolvedBudapestPostcodes': [{'postalCode': code, 'sourceRows': count}
                                             for code, count in sorted(unresolved_budapest.items())]}
    runtime = ('[\n' + ',\n'.join(packed(row) for row in [header] + rows) + '\n]\n').encode('utf-8')
    return header, rows, deterministic_gzip(runtime), audit


def write_or_check(path, content, check):
    if check:
        if not path.exists() or path.read_bytes() != content:
            raise ValueError('Generated output differs: ' + str(path.relative_to(ROOT)))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def demo_module(rows):
    selected = [{**row, 'kind': 'street'} for row in rows
                if (row['city'], row['district'], row['streetName']) in DEMO_STREETS]
    if len(selected) != len(DEMO_STREETS):
        raise ValueError('A pinned demo street is missing from the reviewed source.')
    return ('// Generated by scripts/import-streets.py from Magyar Posta Partner Extra.\n'
            '// Street metadata only; fictional property coordinates are maintained separately.\n'
            '// Source and permitted use: THIRD-PARTY-NOTICES.txt and docs/STREET-DATA.md.\n'
            'export const streetDemoData = Object.freeze(' + json.dumps(selected, ensure_ascii=False, indent=2) +
            '.map(street => Object.freeze({...street, postalCodes: Object.freeze(street.postalCodes), '
            'aliases: Object.freeze(street.aliases)})));\n').encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE, help='Reviewed XML or gzip XML; offline input only.')
    parser.add_argument('--check', action='store_true', help='Verify pinned source and generated files without writes.')
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    content = args.source.read_bytes()
    if content[:2] == b'\x1f\x8b':
        content = gzip.decompress(content)
    cities = set(json.loads((ROOT / 'dist/data/settlements.json').read_text(encoding='utf-8'))['settlements'])
    mappings_path = DATA / 'city-mappings.json'
    mappings = json.loads(mappings_path.read_text(encoding='utf-8')) if mappings_path.exists() else {}
    header, rows, runtime, audit = build(content, manifest, cities, mappings)
    if 'sourceRows' in manifest and header['stats']['sourceRows'] != manifest['sourceRows']:
        raise ValueError('The parsed source row count differs from the reviewed manifest.')
    if 'streetCount' in manifest and header['count'] != manifest['streetCount']:
        raise ValueError('The generated street count differs from the reviewed manifest.')
    # Unknown source cities are a reviewable blocker, rather than silent omissions.
    if audit['stats']['unmappedSourceRows']:
        print(json.dumps(audit['unmappedCities'], ensure_ascii=False, indent=2))
        raise ValueError('Unmapped source cities require explicit, documented mappings before publication.')
    write_or_check(SOURCE, deterministic_gzip(content), args.check)
    write_or_check(OUTPUT, runtime, args.check)
    write_or_check(AUDIT, (json.dumps(audit, ensure_ascii=False, indent=2) + '\n').encode('utf-8'), args.check)
    write_or_check(DEMO_OUTPUT, demo_module(rows), args.check)
    print(packed(header))


if __name__ == '__main__':
    main()
