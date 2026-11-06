#!/usr/bin/env python3
"""Generate the shared city-area snapshot from the official KSH 2026 TSZJ XLSX.

Uses only Python's standard library. Input stays outside version control; source
hash, attribution and the extraction date are recorded in the generated JSON.
"""
import argparse
import hashlib
import json
from pathlib import Path
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

SOURCE_URL = 'https://www.ksh.hu/docs/osztalyozasok/teruleti_szamjel/teruleti_szamjelrendszer_struktura_elemei_2026.xlsx'
COUNT_URL = 'https://www.ksh.hu/stadat_files/fol/hu/fol0016.html'
EXPECTED_COUNTS = {
    'Budapest': 81, 'Győr': 78, 'Miskolc': 41, 'Pécs': 49, 'Eger': 19,
    'Szombathely': 63, 'Zalaegerszeg': 67, 'Békéscsaba': 11, 'Debrecen': 13,
    'Kaposvár': 30, 'Kecskemét': 13, 'Nyíregyháza': 11, 'Salgótarján': 12,
    'Sopron': 15, 'Szeged': 16, 'Szekszárd': 10, 'Székesfehérvár': 43,
    'Szolnok': 13, 'Tatabánya': 11, 'Veszprém': 27, 'Dunaújváros': 9,
    'Nagykanizsa': 27, 'Baja': 3, 'Esztergom': 2,
}
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ROOT = Path(__file__).resolve().parents[1]


def read_rows(path):
    """Read the source's first sheet, including shared and inline strings."""
    with zipfile.ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            tree = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            strings = [''.join(node.itertext()) for node in tree.findall('m:si', NS)]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        for row in sheet.findall('m:sheetData/m:row', NS):
            result = {}
            for cell in row.findall('m:c', NS):
                letters = ''.join(character for character in cell.attrib['r'] if character.isalpha())
                index = 0
                for character in letters:
                    index = index * 26 + ord(character) - ord('A') + 1
                value = cell.find('m:v', NS)
                if cell.attrib.get('t') == 's':
                    text = strings[int(value.text)] if value is not None else ''
                elif cell.attrib.get('t') == 'inlineStr':
                    text = ''.join(cell.find('m:is', NS).itertext())
                else:
                    text = value.text if value is not None else ''
                result[index - 1] = text
            yield result


def sort_key(value):
    return ''.join(character for character in unicodedata.normalize('NFD', value)
                   if unicodedata.category(character) != 'Mn').casefold()


def snapshot(source, retrieved_on):
    names = set(json.loads((ROOT / 'dist/data/settlements.json').read_text())['settlements'])
    rows = iter(read_rows(source))
    header = next(rows)
    columns = {value: index for index, value in header.items()}
    if 'Név' not in columns or 'Agglomeráció kódja' not in columns:
        raise ValueError('Use the full TSZJ structure XLSX, not its shortened named version.')
    town_codes = {}
    for row in rows:
        name = row.get(columns['Név'], '')
        if name in names:
            if name in town_codes:
                raise ValueError('Duplicate municipality in the KSH workbook: ' + name)
            town_codes[name] = row.get(columns['Agglomeráció kódja'], '')
    if set(town_codes) != names:
        raise ValueError('The source workbook and shared settlement catalogue differ.')
    areas = []
    centers = sorted(EXPECTED_COUNTS, key=lambda city: (city != 'Budapest', sort_key(city)))
    for city in centers:
        code = town_codes[city]
        if not code.endswith('1') or len(code) != 4:
            raise ValueError('The expected central city has no central-city code: ' + city)
        # Budapest is represented by its center (0001) and six legal sectors
        # (001x..006x), not the broader research boundary from the 2024 paper.
        members = [name for name, member_code in town_codes.items()
                   if (member_code.startswith('0') if city == 'Budapest'
                       else member_code[:3] == code[:3])]
        members = sorted(members, key=lambda name: (name != city, sort_key(name)))
        if len(members) != EXPECTED_COUNTS[city] or members.count(city) != 1:
            raise ValueError(f'KSH/STADAT membership count mismatch for {city}: {len(members)}')
        areas.append({'id': 'area:' + city, 'city': city, 'settlements': members})
    return {
        'schemaVersion': 1,
        'version': 'ksh-2024-' + retrieved_on,
        'sources': [
            {'title': 'KSH – Területi számjelrendszer struktúra elemei, 2026',
             'url': SOURCE_URL, 'retrievedOn': retrieved_on,
             'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
             'license': 'CC BY 4.0', 'licenseUrl': 'https://www.ksh.hu/copyright'},
            {'title': 'KSH STADAT 8.1.2.11. – Agglomerációk és településegyüttesek, 2026. január 1.',
             'url': COUNT_URL, 'updatedOn': '2026-09-15',
             'role': 'Independent verification of settlement counts, including central cities.'}
        ],
        'processing': 'Filtered to the 24 city-centered areas; excluded the non-city-centered Balaton area and non-settlement rows. Names were matched to the existing municipality catalogue; centers occur once. Budapest uses its legal 81-settlement delimitation.',
        'areas': areas
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xlsx', type=Path)
    parser.add_argument('--retrieved-on', default='2026-11-06')
    parser.add_argument('--check', action='store_true', help='Compare generated output without writing files.')
    args = parser.parse_args()
    data = snapshot(args.xlsx, args.retrieved_on)
    json_text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    js_text = ('// Generated from data/agglomerations.json. Source: KSH (CC BY 4.0); see THIRD-PARTY-NOTICES.txt.\n'
               + 'export const agglomerations = Object.freeze('
               + json.dumps(data['areas'], ensure_ascii=False, indent=2)
               + '.map(area => Object.freeze({...area, settlements: Object.freeze(area.settlements)})));\n')
    outputs = [(ROOT / 'dist/data/agglomerations.json', json_text),
               (ROOT / 'dist/agglomerations-data.js', js_text)]
    for path, content in outputs:
        if args.check:
            if path.read_text() != content:
                raise ValueError('Generated output differs: ' + str(path))
        else:
            path.write_text(content)
    print('Verified 24 KSH city areas and their STADAT settlement counts; Budapest 81, Debrecen 13.')


if __name__ == '__main__':
    main()
