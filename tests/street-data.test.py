#!/usr/bin/env python3
"""Offline regressions for street identity, postal deduplication and source review."""
import gzip
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('import_streets', ROOT / 'scripts/import-streets.py')
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)


class StreetImportTests(unittest.TestCase):
    def build(self, xml, cities=None, overrides=None):
        content = xml.encode('utf-8')
        return IMPORTER.build(content, {'sha256': hashlib.sha256(content).hexdigest(),
                                       'retrievedOn': '2026-11-18'},
                              cities or {'Budapest', 'Szeged'}, overrides)

    def test_stable_identity_excludes_postcode_preserves_district_and_accents(self):
        identifier = IMPORTER.street_id('Budapest', 'XI.', 'Bartók Béla', 'út')
        self.assertEqual(identifier, IMPORTER.street_id(' BUDAPEST ', 'XI.', 'Bartók  Béla', 'ÚT'))
        self.assertNotEqual(identifier, IMPORTER.street_id('Budapest', 'II.', 'Bartók Béla', 'út'))
        self.assertNotEqual(IMPORTER.street_id('Szeged', None, 'Élő', 'utca'),
                            IMPORTER.street_id('Szeged', None, 'Elő', 'utca'))

    def test_namespaced_child_fields_and_postal_deduplication(self):
        header, rows, compressed, audit = self.build('''<root xmlns="urn:posta">
          <row><ZipCode>1111</ZipCode><city>Budapest</city><name>Bartók Béla</name><type>út</type></row>
          <row><ZipCode>1114</ZipCode><city>Budapest</city><name>Bartók Béla</name><type>út</type></row>
          <row><ZipCode>1111</ZipCode><city>Budapest</city><name>Bartók Béla</name><type>út</type></row>
        </root>''')
        self.assertEqual(1, header['count'])
        self.assertEqual(['1111', '1114'], rows[0]['postalCodes'])
        self.assertEqual('XI.', rows[0]['district'])
        self.assertEqual(1, audit['stats']['duplicatePostalRows'])
        self.assertEqual([header, *rows], json.loads(gzip.decompress(compressed)))
        self.assertEqual(64, len(header['datasetVersion']))
        self.assertEqual(compressed, IMPORTER.deterministic_gzip(gzip.decompress(compressed)))

    def test_attribute_schema_and_no_guessed_special_postal_district(self):
        _, rows, _, audit = self.build('''<root>
          <row ZipCode="1007" city="Budapest" name="Teszt" type="sétány"/>
          <row ZipCode="6720" city="Szeged" name="Teszt" type="utca"/>
        </root>''')
        budapest = next(row for row in rows if row['city'] == 'Budapest')
        self.assertIsNone(budapest['district'])
        self.assertEqual([{'postalCode': '1007', 'sourceRows': 1}], audit['unresolvedBudapestPostcodes'])
        for code in ('1000', '1007', '1240', '1280', '1550'):
            self.assertIsNone(IMPORTER.postal_district(code))

    def test_unmapped_cities_are_audited_and_reviewed_alias_preserved(self):
        xml = '<root><row ZipCode="6720" city="Postal alias" name="Teszt" type="utca"/></root>'
        _, rows, _, audit = self.build(xml)
        self.assertEqual([], rows)
        self.assertEqual(1, audit['stats']['unmappedSourceRows'])
        _, rows, _, audit = self.build(xml, overrides={'Postal alias': 'Szeged'})
        self.assertEqual(0, audit['stats']['unmappedSourceRows'])
        self.assertEqual('Szeged', rows[0]['city'])
        self.assertIn('Postal alias, Teszt utca', rows[0]['aliases'])

    def test_source_pin_and_postcode_validation_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            IMPORTER.build(b'<root/>', {'sha256': '0' * 64}, {'Budapest'})
        with self.assertRaisesRegex(ValueError, 'four-digit'):
            self.build('<root><row ZipCode="bad" city="Szeged" name="Teszt" type="utca"/></root>')
        with self.assertRaisesRegex(ValueError, 'four-digit'):
            self.build('<root><row ZipCode="١١١١" city="Szeged" name="Teszt" type="utca"/></root>')

    def test_malformed_records_are_not_silently_dropped(self):
        for invalid in ('<row/>', '<row ZipCode="6720" city="Szeged" name="Teszt"/>'):
            with self.assertRaisesRegex(ValueError, 'missing required'):
                self.build('<root>' + invalid + '<row ZipCode="6720" city="Szeged" name="Teszt" type="utca"/></root>')

    def test_explicit_district_conflict_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.build('<root><row ZipCode="1111" city="Budapest XIII." name="Teszt" type="utca"/></root>')

    def test_actual_pinned_source_has_complete_runtime_postal_coverage(self):
        source_path = ROOT / 'data/streets/sources/StreetNames.xml.gz'
        source = gzip.decompress(source_path.read_bytes())
        self.assertEqual('e6ce188aa0c01399eb31ea8385cebce94292af0890d8d72a663fd5d41f0005ca',
                         hashlib.sha256(source).hexdigest())
        del source
        source_pairs = Counter()
        with gzip.open(source_path, 'rb') as stream:
            for _, element in ET.iterparse(stream, events=('end',)):
                if element.tag == 'street':
                    self.assertEqual(Counter({'ZipCode': 1, 'city': 1, 'name': 1, 'type': 1}),
                                     Counter(child.tag for child in element))
                    raw = {child.tag: child.text or '' for child in element}
                    source_pairs[(raw['city'], raw['name'], raw['type'], raw['ZipCode'])] += 1
                    element.clear()
        self.assertEqual(124188, sum(source_pairs.values()))
        header, *rows = json.loads(gzip.decompress((ROOT / 'dist/data/streets.json.gz').read_bytes()))
        self.assertEqual(123354, len(rows))
        self.assertEqual(123354, header['count'])
        self.assertEqual('e397f60ecfbbd8c0708137d9f87e19bb3f6634917a3cab7b594f6c1d1ff7a0a7',
                         header['datasetVersion'])
        runtime_pairs = Counter((row['city'], row['name'], row['type'], postal_code)
                                for row in rows for postal_code in row['postalCodes'])
        self.assertEqual(source_pairs, runtime_pairs)
        cities = set(json.loads((ROOT / 'dist/data/settlements.json').read_text())['settlements'])
        self.assertEqual(cities, {row['city'] for row in rows})
        self.assertEqual(3155, len(cities))
        self.assertEqual(len(rows), len({row['id'] for row in rows}))
        self.assertTrue(all(set(row) == {'id', 'city', 'district', 'name', 'type', 'streetName',
                                        'label', 'postalCodes', 'aliases'} for row in rows))
        bartok = next(row for row in rows if row['id'] == 'street:cf625e9eb4715d7593eb8de3')
        self.assertEqual(['1111', '1113', '1114', '1115'], bartok['postalCodes'])
        self.assertTrue(all(row['district'] is None for row in rows
                            if any(code in {'1007', '1826', '1836', '1838', '1857', '1871'}
                                   for code in row['postalCodes'])))


if __name__ == '__main__':
    unittest.main()
