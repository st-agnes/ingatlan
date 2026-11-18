#!/usr/bin/env python3
"""Read-only Pécs name evidence from the archived original KSH XLSX."""
import argparse
from collections import Counter
import hashlib
import json
import posixpath
import re
import unicodedata
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'data/neighborhoods'
WORKBOOK = BASE / 'sources/nationwide-inventory/hnt_letoltes_2026.xlsx'
INVENTORY = BASE / 'nationwide-inventory.json'
ACQUISITION = BASE / 'sources/nationwide-inventory/acquisition.json'
NAMES = BASE / 'sources/municipal-pecs-final-gaps-review/source-coverage-accounting.json'
OUTPUT = Path(__file__).with_name('pecs-current-name-ksh-evidence.json')
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_name(value):
    return ''.join(c for c in unicodedata.normalize('NFC', value).casefold()
                   if not c.isspace() and not unicodedata.category(c).startswith('P'))


def rich_text(item):
    parts = []
    for child in item:
        if child.tag == '{'+NS['s']+'}t':
            parts.append(child.text or '')
        elif child.tag == '{'+NS['s']+'}r':
            parts.extend(v.text or '' for v in child.findall('s:t', NS))
    return ''.join(parts)


def read_original_xlsx():
    sheets = {}
    with ZipFile(WORKBOOK) as archive:
        shared = [rich_text(v) for v in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        rels = {v.attrib['Id']: v.attrib['Target'] for v in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        for sheet in workbook.findall('s:sheets/s:sheet', NS):
            target = rels[sheet.attrib[RID]]
            member = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows = []
            for row in ET.fromstring(archive.read(member)).findall('s:sheetData/s:row', NS):
                values = {}
                for cell in row.findall('s:c', NS):
                    col = re.match(r'[A-Z]+', cell.attrib['r']).group()
                    if cell.attrib.get('t') == 'inlineStr':
                        value = rich_text(cell.find('s:is', NS))
                    else:
                        item = cell.find('s:v', NS)
                        value = item.text if item is not None and item.text is not None else ''
                        if cell.attrib.get('t') == 's' and value:
                            value = shared[int(value)]
                    values[col] = value
                if any(values.values()):
                    rows.append((int(row.attrib['r']), values))
            sheets[sheet.attrib['name']] = {'member': member, 'memberSha256': hashlib.sha256(archive.read(member)).hexdigest(), 'rows': rows}
        core = ET.fromstring(archive.read('docProps/core.xml'))
        created = core.find('{http://purl.org/dc/terms/}created').text
        modified = core.find('{http://purl.org/dc/terms/}modified').text
    return sheets, {'created': created, 'modified': modified}


def build():
    source_names = json.loads(NAMES.read_text())['records']
    assert len(source_names) == 67 and len({r['sourceName'] for r in source_names}) == 67
    inventory = json.loads(INVENTORY.read_text())
    acquisition = json.loads(ACQUISITION.read_text())
    gazetteer = inventory['sources']['gazetteer']
    official = next(r for r in acquisition['results'] if r['id'] == 'ksh-2026')
    assert sha(WORKBOOK) == official['sha256'] == gazetteer['sha256']
    assert WORKBOOK.stat().st_size == official['bytes'] == gazetteer['bytes']
    pecs = next(r for r in inventory['municipalities'] if r['municipality'] == 'Pécs')
    assert pecs['kshCode'] == '19415'
    sheets, core = read_original_xlsx()
    municipality_sheet = sheets['Helységek 2026.01.01.']
    parts_sheet = sheets['Településrészek 2026.01.01.']
    municipality_matches = [(row, cells) for row,cells in municipality_sheet['rows']
                            if cells.get('A') == 'Pécs' and cells.get('B','').zfill(5) == '19415']
    assert len(municipality_matches) == 1
    municipality_row, municipality_cells = municipality_matches[0]
    assert municipality_row == pecs['municipalitySourceRow'] == 2154
    assert municipality_cells['D'] == 'Baranya'
    assert municipality_cells['C'] == pecs['sourceLegalStatus']
    original_parts = [(row,cells) for row,cells in parts_sheet['rows']
                      if cells.get('A','').zfill(5) == '19415']
    assert len(original_parts) == len(pecs['settlementParts']) == 55
    assert {row for row,cells in original_parts} == {r['sourceRow'] for r in pecs['settlementParts']}
    imported_by_row = {r['sourceRow']:r for r in pecs['settlementParts']}
    categories = {'00':'central_built_up_area','01':'other_built_up_area','02':'outlying_area'}
    rows = []
    for row,cells in original_parts:
        imported = imported_by_row[row]
        assert cells['B'] == 'Pécs' and cells['C'] == 'Baranya'
        assert imported['name'] == cells['D']
        assert imported['sourceKshCode'] == cells['A'].zfill(5) == '19415'
        assert imported['sourceMunicipalityName'] == cells['B']
        assert imported['sourceCategoryCode'] == cells['E']
        assert imported['category'] == categories[cells['E']]
        assert imported['postalCode'] == (cells.get('F') or None)
        assert imported['outlyingCharacterCode'] == (cells.get('G') or None)
        rows.append({'id': imported['id'], 'sheet': 'Településrészek 2026.01.01.',
                     'sourceRow': row, 'name': cells['D'], 'municipalityKshCode':'19415',
                     'municipalityOfficialName':'Pécs', 'county':'Baranya',
                     'categoryCode':cells['E'], 'category':categories[cells['E']],
                     'postalCode': cells.get('F') or None,
                     'rawOriginalRowCellValues':cells,
                     'importedInventoryRecordMatchesOriginalRow':True})
    results = []
    for source in source_names:
        name = source['sourceName']
        exact = [row for row in rows if row['name'] == name]
        matches = exact or [row for row in rows if normalized_name(row['name']) == normalized_name(name)]
        status = 'literal_exact_ksh_settlement_part_name' if exact else 'punctuation_whitespace_case_normalized_ksh_settlement_part_name' if matches else 'no_ksh_entry_for_this_source_name_under_pecs'
        results.append({'sourceName':name, 'sourceMunicipality':'Pécs', 'sourceMunicipalityKshCode':'19415',
                        'nameEvidenceStatus':status, 'normalizationKey':normalized_name(name),
                        'supportsOfficialSettlementPartLabelAtReferenceDate':bool(matches),
                        'officialReferenceDate':'2026-01-01', 'kshMatches':matches,
                        'acceptedSemanticAliases':[], 'fuzzyMatchingUsed':False,
                        'noEntryMeansMissingQuarter':False,
                        'sameNameCertifiesSameUrbanFootprint':False,
                        'currentLegalQuarterStatusOrBoundaryApproved':False,
                        'geographicAccuracyOrGeometryEvaluated':False})
    counts = Counter(r['nameEvidenceStatus'] for r in results)
    assert counts['literal_exact_ksh_settlement_part_name'] == 14
    assert counts['punctuation_whitespace_case_normalized_ksh_settlement_part_name'] == 3
    assert counts['no_ksh_entry_for_this_source_name_under_pecs'] == 50
    return {'schemaVersion':1, 'reviewDate':'2026-11-14',
            'scope':'Name-only official KSH gazetteer evidence for all67frozen Pécs source names; original XLSX rows re-read independently of the inventory importer. No geometry,registry or frozen-source writes.',
            'inputFingerprints':[{'path':str(q.relative_to(ROOT)), 'bytes':q.stat().st_size, 'sha256':sha(q)} for q in [NAMES,INVENTORY,ACQUISITION,WORKBOOK]],
            'officialSource':{'publisher':'Központi Statisztikai Hivatal', 'title':'Magyarország helységnévtára2026',
                              'sourceUrl':official['url'], 'officialDownloadPageUrl':gazetteer['pageUrl'],
                              'referenceDate':'2026-01-01', 'archivedAcquisitionRetrievedAt':official['retrievedAt'],
                              'archivedAcquisitionHttpStatus':official['httpStatus'],
                              'localWorkbookSha256MatchesArchivedOfficialDownload':True,
                              'archivedOfficialAndMirrorBytesMatch':acquisition['mirrorBytesMatchOfficial'],
                              'workbookCoreDocumentDates':core,
                              'dateMeaning':'2026-01-01 is the table reference date;core-modified and acquisition dates do not establish a later reference date or present-day changes.',
                              'license':acquisition['license'], 'licenseUrl':acquisition['licenseUrl'], 'attribution':'Forrás: KSH'},
            'municipalityIdentityProof':{'municipality':'Pécs', 'kshCode':'19415', 'county':'Baranya',
                                         'sheet':'Helységek 2026.01.01.', 'sourceRow':municipality_row,
                                         'rawOriginalRowCellValues':municipality_cells,
                                         'originalWorksheetMember':municipality_sheet['member'],
                                         'originalWorksheetSha256':municipality_sheet['memberSha256'],
                                         'allMatchedPartRowsIndependentlyRequireSameCodeNameAndCounty':True},
            'pecsOriginalPartTable':{'sheet':'Településrészek 2026.01.01.',
                                     'originalWorksheetMember':parts_sheet['member'],
                                     'originalWorksheetSha256':parts_sheet['memberSha256'],
                                     'allPecsRows':55, 'sourceRows':[row for row,cells in original_parts],
                                     'categoryCounts':dict(Counter(r['category'] for r in rows)),
                                     'allDerivedInventoryPecsRowsMatchOriginalXlsx':True,
                                     'containsUrbanNeighborhoodColumn':False,
                                     'allOriginalPecsPartRows':rows},
            'matchingRules':{'exact':'Literal unchanged source string equals original KSH D-column string.',
                             'normalized':'Unicode NFC and casefold;delete whitespace and Unicode punctuation categories only. Preserve accents,digits and all remaining symbols.',
                             'diacriticsRemoved':False, 'prefixOrSuffixRemoval':False,
                             'fuzzyOrSubstringMatching':False, 'semanticAliasesAccepted':False},
            'records':results,
            'summary':{'sourceNameCount':67, 'literalExactMatches':14,
                        'punctuationWhitespaceCaseNormalizedMatches':3,
                        'supportedOfficialSettlementPartNamesAtReferenceDate':17,
                        'namesWithoutKshEntryForSameSourceStringUnderPecs':50,
                        'semanticAliasesAccepted':0},
            'explicitlyNotAcceptedAsAliases':[
                {'sourceName':'Üszögi tározó-major','differentKshLabel':'Üszögi-víztároló','kshSourceRow':9277},
                {'sourceName':'Üszög','differentKshLabel':'Üszögpuszta','kshSourceRow':9278},
                {'sourceName':'Szentkút','differentKshLabel':'Mecsekszentkúti erdészház','kshSourceRow':9258},
                {'sourceName':'Nagyárpád','differentKshLabel':'Nagyárpádi zártkert','kshSourceRow':9262}],
            'limits':['The KSH source lists central/other built-up settlement parts and outlying places;it is not a complete urban-neighbourhood inventory.',
                      'A name absent from this gazetteer is not proven missing,obsolete or unofficial as a Pécs quarter.',
                      'An exact name establishes a Pécs official settlement-part label at2026-01-01,not equality of extent with the historical fine source polygon.',
                      'No present-day boundary,legal footprint,geographic accuracy or address assignment is approved.'],
            'networkUsedByThisAudit':False, 'newGeometriesCreated':0,
            'frozenSourcesOrRegistriesChanged':False, 'usableForAddressAssignment':False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    report = build()
    expected = json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.check:
        assert OUTPUT.read_text() == expected
    else:
        OUTPUT.write_text(expected)
    print(json.dumps({'check':args.check, 'summary':report['summary'], 'outputSha256':sha(OUTPUT)},ensure_ascii=False))


if __name__ == '__main__':
    main()
