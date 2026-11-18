#!/usr/bin/env python3
"""Build the country-wide *names* inventory; this never manufactures polygons.

The KSH gazetteer distinguishes central/other built-up areas and outlying
settlement parts. Those records are not an inventory of urban neighborhoods.
Only Budapest's KSH data and separately evidenced municipal lists can establish
urban-neighborhood names. Uses the Python standard library only.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import posixpath
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/neighborhoods/sources/nationwide-inventory'
OUTPUT = ROOT / 'data/neighborhoods/nationwide-inventory.json'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
KSH_URL = 'https://www.ksh.hu/docs/helysegnevtar/hnt_letoltes_2026.xlsx'


def string_value(item):
    """Read visible rich text, excluding optional phonetic annotations."""
    result = []
    for child in item:
        if child.tag == '{' + NS['s'] + '}t':
            result.append(child.text or '')
        elif child.tag == '{' + NS['s'] + '}r':
            result.extend(t.text or '' for t in child.findall('s:t', NS))
    return ''.join(result)


def read_workbook(path):
    """Return sheet names, original Excel row numbers and sparse cell values."""
    with zipfile.ZipFile(path) as archive:
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NS):
                shared.append(string_value(item))
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        targets = {r.attrib['Id']: r.attrib['Target'] for r in relationships}
        sheets = {}
        for sheet in workbook.findall('s:sheets/s:sheet', NS):
            target = targets[sheet.attrib[REL]]
            member = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            rows = []
            for row in ET.fromstring(archive.read(member)).findall('s:sheetData/s:row', NS):
                values = {}
                for cell in row.findall('s:c', NS):
                    col = re.match(r'[A-Z]+', cell.attrib['r']).group()
                    kind = cell.attrib.get('t', '')
                    if kind == 'inlineStr':
                        value = string_value(cell.find('s:is', NS))
                    else:
                        element = cell.find('s:v', NS)
                        value = element.text if element is not None else ''
                        if kind == 's' and value:
                            value = shared[int(value)]
                    values[col] = (value or '').strip()
                if any(values.values()):
                    rows.append((int(row.attrib['r']), values))
            sheets[sheet.attrib['name']] = rows
        return sheets


def norm(value):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower())


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def file_metadata(path):
    data = Path(path).read_bytes()
    return {'path': str(Path(path).relative_to(ROOT)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
            'gitBlobSha1': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, default=SOURCE / 'hnt_letoltes_2026.xlsx')
    parser.add_argument('--inspect', action='store_true', help='Print sheet schemas without writing output')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    sheets = read_workbook(args.workbook)
    if args.inspect:
        for name, rows in sheets.items():
            print(json.dumps({'sheet': name, 'nonemptyRows': len(rows), 'firstRows': rows[:7], 'lastRows': rows[-2:]}, ensure_ascii=False))
        return
    result = build_inventory(sheets, args.workbook)
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding='utf-8') != text:
            raise SystemExit('Nationwide inventory is stale; run python3 scripts/neighborhoods/inventory.py')
    else:
        OUTPUT.write_text(text, encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False))


def build_inventory(sheets, workbook):
    municipality_sheet = 'Helységek 2026.01.01.'
    parts_sheet = 'Településrészek 2026.01.01.'
    expected_municipality = {'A': 'Helység megnevezése', 'B': 'Helység KSH kódja',
                             'C': 'Helység jogállása', 'D': 'Megye megnevezése'}
    expected_parts = {'A': 'Helység KSH kód', 'B': 'Helység hivatalos megnevezése',
                      'C': 'Megye megnevezése', 'D': 'Településrész megnevezése',
                      'E': 'Településrész jelleg kód', 'F': 'Postai irányító-szám',
                      'G': 'A külterület települési jellege'}
    for sheet, expected in [(municipality_sheet, expected_municipality), (parts_sheet, expected_parts)]:
        header = dict(sheets[sheet])[3]
        if any(header.get(k) != v for k, v in expected.items()):
            raise ValueError('KSH workbook header changed: ' + sheet)
    legal = {'főváros': 'capital', 'város': 'city',
             'megyei jogú város': 'county_rank_city',
             'megyeszékhely, megyei jogú város': 'county_rank_city',
             'község': 'village', 'nagyközség': 'large_village',
             'fővárosi kerület': 'capital_district'}
    categories = {'00': 'central_built_up_area', '01': 'other_built_up_area', '02': 'outlying_area'}
    municipalities, codes = {}, {}
    for rownum, row in sheets[municipality_sheet]:
        if rownum <= 3 or row.get('A') == 'Összesen':
            continue
        if row.get('C') not in legal or not re.fullmatch(r'\d{1,5}', row.get('B', '')):
            raise ValueError(f'Invalid municipality row {rownum}')
        status = legal[row['C']]
        code = row['B'].zfill(5)
        parent = 'Budapest' if status == 'capital_district' else row['A']
        if code in codes:
            raise ValueError('Duplicate KSH code: ' + code)
        codes[code] = {'municipality': parent, 'name': row['A'], 'row': rownum, 'status': status}
        if status == 'capital_district':
            continue
        municipalities[parent] = {'municipality': parent, 'kshCode': code,
            'legalStatus': status, 'sourceLegalStatus': row['C'],
            'county': row.get('D') or 'Budapest', 'municipalitySourceRow': rownum,
            'settlementParts': [], 'nameReferences': [], 'postalNotes': []}
    if len(codes) != 3178:
        raise ValueError(f'Unexpected KSH municipality/district rows: {len(codes)}')
    districts = [dict(kshCode=code, sourceName=info['name'], sourceRow=info['row'])
                 for code, info in codes.items() if info['status'] == 'capital_district']
    municipalities['Budapest']['districts'] = districts
    character_codes = {row['A']: row['B'] for rownum, row in sheets['Külterület települési jellege'] if rownum > 1}
    character_descriptions = {norm(code): desc for code, desc in character_codes.items()}
    imported_parts = 0
    for rownum, row in sheets[parts_sheet]:
        if rownum <= 3:
            continue
        code = row.get('A', '').zfill(5)
        if code not in codes or row.get('E') not in categories or not row.get('D'):
            raise ValueError(f'Unlinked/unknown settlement-part row {rownum}')
        origin = codes[code]
        category = categories[row['E']]
        character = row.get('G') or None
        if character and norm(character) not in character_descriptions:
            raise ValueError(f'Unknown outlying character code at row {rownum}: {character}')
        expected_name = origin['name'].replace('. ker.', '. kerület')
        if row['B'] != expected_name:
            raise ValueError(f'KSH code/name mismatch at part row {rownum}')
        part = {'id': f'ksh-hnt-2026:part:{rownum}', 'name': row['D'],
            'nameIsGenericLabel': norm(row['D']) in ('kozpontibelterulet', 'kulterulet'),
            'category': category, 'sourceCategoryCode': row['E'],
            'sourceRow': rownum, 'sourceMunicipalityName': row['B'],
            'sourceKshCode': code, 'postalCode': row.get('F') or None,
            'outlyingCharacterCode': character,
            'outlyingCharacter': character_descriptions.get(norm(character or '')),
            'geometryStatus': 'not_present_in_name_source'}
        municipalities[origin['municipality']]['settlementParts'].append(part)
        imported_parts += 1
    if imported_parts != len(sheets[parts_sheet]) - 2:
        raise ValueError('Not every KSH settlement-part data row was imported')
    for rownum, row in sheets['Megj. postai ir. számhoz']:
        if rownum <= 1:
            continue
        code = row.get('A', '').zfill(5)
        if code not in codes:
            raise ValueError(f'Unlinked postal note at row {rownum}')
        municipalities[codes[code]['municipality']]['postalNotes'].append({
            'sourceKshCode': code, 'sourceRow': rownum, 'text': row['B'],
            'independentCurrentNameValidation': False})
    metadata = {
        municipality_sheet: {'headerRow': 3, 'dataRows': len(codes), 'columns': dict(sheets[municipality_sheet])[3]},
        parts_sheet: {'headerRow': 3, 'dataRows': imported_parts, 'columns': dict(sheets[parts_sheet])[3],
                      'categoryCodes': categories, 'containsUrbanNeighborhoodColumn': False},
        'officialMunicipalityWebsiteColumnPresent': False,
        'postalNotesCaution': 'A postai megjegyzések korábbi közigazgatási állapotot is említhetnek; nem önálló, mai városrésznév-referencia.'}
    return assemble_inventory(municipalities, workbook, metadata, character_codes)


def assemble_inventory(municipalities, workbook, table_metadata, part_codes):
    facts = load_json(SOURCE / 'municipal-inventories.json')
    local = list(facts['inventories'])
    reference = load_json(ROOT / 'data/neighborhoods/reference-inventories.json')
    for item in reference['inventories']:
        if item['municipality'] != 'Budapest':
            item = dict(item)
            item['category'] = 'municipal_named_area'
            item['referenceInventoryFile'] = 'data/neighborhoods/reference-inventories.json'
            local.append(item)
    budapest = load_json(ROOT / 'data/neighborhoods/budapest-current-reference.json')
    local.append({
        'municipality': 'Budapest', 'title': budapest['title'],
        'sourceUrl': budapest['sourceUrl'], 'category': 'urban_neighborhood',
        'referencePeriod': budapest['legalVersionDate'],
        'completeForReferencePeriod': budapest['completeForReferencePeriod'],
        'currentCompletenessVerified': budapest['currentCompletenessVerified'],
        'names': [n['name'] for n in budapest['neighborhoodIdentities']],
        'identities': budapest['neighborhoodIdentities'],
        'referenceInventoryFile': 'data/neighborhoods/budapest-current-reference.json',
        'note': '212 területi azonosság, 211 külön név. A két eltérő kerületi Orbánhegy külön azonosság marad.'})
    local.sort(key=lambda x: (norm(x['municipality']), x['sourceUrl']))
    reference_categories = collections.Counter()
    for i, item in enumerate(local, 1):
        item = dict(item)
        municipality = item.pop('municipality')
        if municipality not in municipalities:
            raise ValueError('Reference has noncanonical municipality: ' + municipality)
        if not item.get('names'):
            raise ValueError('Empty local name reference: ' + municipality)
        item['id'] = f'municipal-reference-{i:02d}'
        item['sourceIsOfficial'] = True
        item['geometryIncluded'] = False
        item['usableForAddressAssignment'] = False
        item['nameEntryCount'] = len(item['names'])
        item.setdefault('license', {'status': 'not_established', 'redistributionApproved': False})
        reference_categories[item['category']] += len(item['names'])
        if item.get('additionalNamedAreas'):
            additional = item['additionalNamedAreas']
            reference_categories[additional['category']] += len(additional['names'])
        municipalities[municipality]['nameReferences'].append(item)
    canonical = load_json(ROOT / 'dist/data/settlements.json')['settlements']
    if set(municipalities) != set(canonical):
        raise ValueError('KSH/canonical municipality mismatch: ' + json.dumps({
            'missing': sorted(set(canonical) - set(municipalities)),
            'extra': sorted(set(municipalities) - set(canonical))}, ensure_ascii=False))
    records = [municipalities[name] for name in canonical]
    for record in records:
        refs = record['nameReferences']
        record['urbanNeighborhoodInventoryStatus'] = (
            'complete_current_official_name_reference' if any(
                r['category'] == 'urban_neighborhood' and r['currentCompletenessVerified'] for r in refs)
            else 'partial_or_historical_references' if refs else 'not_reviewed')
        record['noncentralSettlementPartCount'] = sum(
            p['category'] != 'central_built_up_area' for p in record['settlementParts'])
        record['namedSettlementPartCount'] = sum(
            not p['nameIsGenericLabel'] for p in record['settlementParts'])
    legal = collections.Counter(r['legalStatus'] for r in records)
    part_categories = collections.Counter(p['category'] for r in records for p in r['settlementParts'])
    city_count = sum(legal[k] for k in ('city', 'county_rank_city', 'capital'))
    if len(records) != 3155 or city_count != 348:
        raise ValueError(f'Unexpected KSH country totals: {len(records)} municipalities, {city_count} cities')
    referenced = [r['municipality'] for r in records if r['nameReferences']]
    return {
        'schemaVersion': 1,
        'referenceDate': '2026-01-01',
        'sourceCheckedAt': facts['checkedAt'],
        'title': 'Magyarország településrészeinek országos névjegyzéke és az ellenőrzött helyi névreferenciák',
        'attribution': facts['license']['requiredAttribution'],
        'scope': {
            'country': 'HU', 'countryMunicipalityListComplete': True,
            'kshSettlementPartTableFullyImported': True,
            'urbanNeighborhoodInventoryCompleteNationwide': False,
            'geometriesIncluded': False, 'usableForAddressAssignment': False,
            'notes': [
                'Az országos teljesség kizárólag a KSH 2026-os település- és településrész-táblájának teljes beolvasására vonatkozik.',
                'A központi és egyéb belterületek, valamint külterületek nem azonosak a városrészekkel. Tanyákból és majorokból nem készül automatikusan városrész.',
                'A forrásból beolvasott településrésznév nem igazolja külön határpoligon létezését vagy annak mai pontosságát.',
                'A helyi tervezési, statisztikai és szabályozási területek kategóriája külön marad az önkormányzati városrésznevektől.',
                'A not_reviewed állapot ismeretlen városrészi lefedettséget jelent, nem nulla városrészt.',
                'A budapesti kerületi KSH-rekordok Budapest alá kerülnek, eredeti kerületi névvel és kóddal; a kerületeket nem számoljuk 23 további településnek.']},
        'summary': {
            'municipalities': len(records), 'citiesIncludingCapital': city_count,
            'legalStatuses': dict(sorted(legal.items())),
            'kshSettlementPartRows': sum(part_categories.values()),
            'kshSettlementPartCategories': dict(sorted(part_categories.items())),
            'municipalitiesWithNoncentralSettlementParts': sum(r['noncentralSettlementPartCount'] > 0 for r in records),
            'noncityMunicipalitiesWithNoncentralSettlementParts': sum(r['noncentralSettlementPartCount'] > 0 and r['legalStatus'] in ('village', 'large_village') for r in records),
            'municipalitiesWithNamedSettlementParts': sum(r['namedSettlementPartCount'] > 0 for r in records),
            'namedSettlementPartRowsExcludingGenericLabels': sum(r['namedSettlementPartCount'] for r in records),
            'municipalitiesWithLocalNameReferences': len(referenced),
            'localReferenceNameEntriesByCategory': dict(sorted(reference_categories.items())),
            'cityMunicipalitiesWithoutReviewedLocalNameReference': sum(not r['nameReferences'] and r['legalStatus'] in ('city', 'county_rank_city', 'capital') for r in records),
            'municipalitiesWithCompleteCurrentUrbanNameReference': [r['municipality'] for r in records if r['urbanNeighborhoodInventoryStatus'] == 'complete_current_official_name_reference']},
        'sources': {
            'gazetteer': {**facts['officialDownload'], **file_metadata(workbook),
                          'license': facts['license'], 'sheets': table_metadata,
                          'acquisitionFile': 'data/neighborhoods/sources/nationwide-inventory/acquisition.json',
                          'outlyingSettlementCharacterCodes': part_codes},
            'methodology': facts['methodology'],
            'officialCountryBenchmark': {'sourceUrl': 'https://www.ksh.hu/teruletiatlasz_telepulesek',
                                        'referenceDate': '2026-01-01', 'municipalities': 3155, 'cities': 348},
            'localNameFactsFile': 'data/neighborhoods/sources/nationwide-inventory/municipal-inventories.json'},
        'municipalities': records}


if __name__ == '__main__':
    main()
