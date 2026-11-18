"""Runtime packaging integrity and the synthetic point/geometry contract (stdlib only)."""
import gzip
import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('runtime_neighborhoods', ROOT / 'scripts/import-neighborhoods.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NeighborhoodRuntimeDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_bytes = MODULE.SOURCE.read_bytes()
        cls.source = json.loads(gzip.decompress(cls.source_bytes))
        cls.runtime = json.loads(gzip.decompress((ROOT / 'dist/data/neighborhoods.json.gz').read_bytes()))

    def test_pinned_source_count_and_stable_identities(self):
        self.assertEqual(hashlib.sha256(self.source_bytes).hexdigest(), MODULE.EXPECTED_SOURCE_SHA256)
        header, *boundaries = self.runtime
        self.assertEqual(header['sourceSha256'], MODULE.EXPECTED_SOURCE_SHA256)
        self.assertEqual(header['featureCount'], 4308)
        self.assertEqual(len(header['areas']), 4308)
        self.assertEqual(len(boundaries), 4308)
        self.assertEqual(len({row['id'] for row in boundaries}), 4308)
        self.assertEqual({row['id'] for row in boundaries}, {feature['id'] for feature in self.source['features']})

    def test_all_full_geometries_and_names_survive_without_simplification(self):
        header, *boundaries = self.runtime
        metadata = {row['id']: row for row in header['areas']}
        by_id = {row['id']: row for row in boundaries}
        for feature in self.source['features']:
            identity = feature['id']
            with self.subTest(id=identity):
                self.assertEqual(by_id[identity]['geometry'], feature['geometry'])
                self.assertEqual(by_id[identity]['geometrySha256'], feature['properties']['geometrySha256'])
                self.assertEqual(metadata[identity]['aliases'], feature['properties']['aliases'])
                self.assertEqual(metadata[identity]['label'], feature['properties']['label'])
                self.assertEqual(metadata[identity]['city'], feature['properties']['municipality'])
                self.assertRegex(identity, r'^neighborhood:[0-9a-f]{24}$')

    def test_fixture_points_are_interior_and_do_not_swap_longitude_latitude(self):
        metadata = {row['id']: row for row in self.runtime[0]['areas']}
        for feature in self.source['features']:
            point = metadata[feature['id']]['representativePoint']
            self.assertTrue(MODULE.covers(feature['geometry'], *point, boundary=False), feature['id'])
            self.assertTrue(16 <= point[0] <= 23 and 45 <= point[1] <= 49)

    def test_synthetic_city_fallbacks_are_in_their_own_pinned_municipality(self):
        content = MODULE.MUNICIPALITIES.read_bytes()
        self.assertEqual(hashlib.sha256(content).hexdigest(), MODULE.EXPECTED_MUNICIPALITIES_SHA256)
        source = json.loads(gzip.decompress(content))['features']
        by_city = {}
        for feature in source:
            by_city.setdefault(feature['properties']['name'], []).append(feature['geometry'])
        cities = self.runtime[0]['testCityPoints']
        known = set(json.loads((ROOT / 'dist/data/settlements.json').read_text())['settlements'])
        self.assertEqual(set(cities), known)
        self.assertEqual(len(cities), 3155)
        for city, point in cities.items():
            self.assertTrue(any(MODULE.covers(geometry, *point, boundary=False) for geometry in by_city[city]), city)
        self.assertIn('Hajdúszoboszló', cities)
        self.assertIn('Abádszalók', cities)

    def test_holes_boundaries_and_multipart_membership(self):
        outer = [[18,46],[20,46],[20,48],[18,48],[18,46]]
        hole = [[18.5,46.5],[19.5,46.5],[19.5,47.5],[18.5,47.5],[18.5,46.5]]
        geometry = {'type': 'Polygon', 'coordinates': [outer, hole]}
        self.assertTrue(MODULE.covers(geometry, 18.25, 47))
        self.assertFalse(MODULE.covers(geometry, 19, 47))
        self.assertTrue(MODULE.covers(geometry, 18, 47))
        self.assertTrue(MODULE.covers(geometry, 18.5, 47))
        self.assertFalse(MODULE.covers(geometry, 18.5, 47, boundary=False))
        second = [[21,46],[22,46],[22,47],[21,47],[21,46]]
        multi = {'type': 'MultiPolygon', 'coordinates': [[outer, hole], [second]]}
        self.assertTrue(MODULE.covers(multi, 21.5, 46.5))
        self.assertFalse(MODULE.covers(multi, 20.5, 46.5))
        self.assertTrue(MODULE.covers(multi, *MODULE.representative_point(multi), boundary=False))

    def test_invalid_geometry_rejected_and_tiny_valid_slivers_preserved(self):
        with self.assertRaisesRegex(ValueError, 'longitude,latitude'):
            MODULE.validate_geometry({'type':'Polygon','coordinates':[[[47,19],[47,20],[48,20],[47,19]]]})
        with self.assertRaisesRegex(ValueError, 'not closed'):
            MODULE.validate_geometry({'type':'Polygon','coordinates':[[[18,47],[19,47],[18,48],[18,47.5]]]})
        sliver = {'type':'Polygon','coordinates':[[[20.798422494911033,48.104029387063626],[20.798422498873094,48.10402938700223],
                                                  [20.798422494738166,48.104029381799094],[20.798422494911033,48.104029387063626]]]}
        MODULE.validate_geometry(sliver)

    def test_browser_export_has_only_metadata_and_synthetic_points_are_separate(self):
        text = (ROOT / 'dist/neighborhoods-data.js').read_text()
        match = re.search(r'export const neighborhoods = Object.freeze\((\[.*\])\.map', text)
        self.assertIsNotNone(match)
        rows = json.loads(match.group(1))
        self.assertEqual(len(rows), 4308)
        for row in rows:
            self.assertEqual(set(row), {'id', 'name', 'city', 'label', 'aliases', 'estimated'})
        self.assertNotIn('coordinates', text)
        self.assertNotIn('representativePoint', text)
        fixtures_text = (ROOT / 'dist/neighborhood-demo-points.js').read_text()
        fixtures = json.loads(re.search(r'Object.freeze\((\[.*\])\.map', fixtures_text).group(1))
        self.assertEqual(len(fixtures), 13)
        by_name = {(row['city'],row['name']):row for row in fixtures}
        for row in fixtures:
            self.assertIs(row['synthetic'], True)
            expected = sorted(feature['id'] for feature in self.source['features']
                              if feature['bbox'][0] <= row['longitude'] <= feature['bbox'][2]
                              and feature['bbox'][1] <= row['latitude'] <= feature['bbox'][3]
                              and MODULE.covers(feature['geometry'], row['longitude'], row['latitude']))
            self.assertEqual(row['membershipIds'], expected)
            self.assertIn(row['id'], expected)
        venkert = by_name[('Debrecen','Vénkert')]
        sestakert = by_name[('Debrecen','Sestakert')]
        self.assertNotIn(venkert['id'], sestakert['membershipIds'])
        self.assertNotIn(sestakert['id'], venkert['membershipIds'])


if __name__ == '__main__':
    unittest.main()
