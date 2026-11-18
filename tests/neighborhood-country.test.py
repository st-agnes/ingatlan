"""Country collector checks, including real PBF assembly when dependencies exist."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts/neighborhoods' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


fetcher = module('fetch-country')
extractor = module('extract-country')
try:
    import osmium
    from shapely.geometry import box
    from shapely.strtree import STRtree
    HAS_GEOMETRY = True
except ImportError:
    HAS_GEOMETRY = False


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, headers=None, url=fetcher.URL):
        super().__init__(data)
        self.headers, self.url = headers or {}, url

    def geturl(self):
        return self.url


class CountryDownloadTests(unittest.TestCase):
    def test_source_and_redirects_are_restricted_to_official_hungary_extracts(self):
        for url in (fetcher.URL, fetcher.URL + '.md5', 'https://download.geofabrik.de/europe/hungary-261112.osm.pbf'):
            self.assertEqual(fetcher.validate_url(url), url)
        for url in ('http://download.geofabrik.de/europe/hungary-latest.osm.pbf',
                    'https://download.geofabrik.de.evil.example/europe/hungary-latest.osm.pbf',
                    'https://token@download.geofabrik.de/europe/hungary-latest.osm.pbf',
                    'https://download.geofabrik.de/europe/austria-latest.osm.pbf',
                    'https://download.geofabrik.de/europe/hungary-latest.osm.pbf?token=a',
                    'https://download.geofabrik.de:444/europe/hungary-latest.osm.pbf'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetcher.validate_url(url)
        with self.assertRaises(ValueError):
            fetcher.ValidatedRedirects().redirect_request(None, None, 302, '', {}, 'https://evil.example/pbf')

    def test_checksum_parser_requires_a_hungary_pbf_filename(self):
        checksum = 'a' * 32
        self.assertEqual(fetcher.parse_checksum((checksum + '  hungary-latest.osm.pbf\n').encode()),
                         (checksum, 'hungary-latest.osm.pbf'))
        for value in (checksum, checksum + '  austria-latest.osm.pbf', checksum + '  ../../hungary-latest.osm.pbf'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fetcher.parse_checksum(value.encode())

    def test_streaming_verifies_checksum_length_and_hard_limit(self):
        data = b'actual bounded source fixture'
        checksum = hashlib.md5(data).hexdigest()
        target = io.BytesIO()
        with patch.object(fetcher, 'CHUNK_BYTES', 3):
            result = fetcher.copy_verified(Response(data, {'Content-Length': str(len(data))}), target, checksum)
        self.assertEqual(target.getvalue(), data)
        self.assertEqual(result['sha256'], hashlib.sha256(data).hexdigest())
        with self.assertRaisesRegex(ValueError, 'MD5'):
            fetcher.copy_verified(Response(data), io.BytesIO(), '0' * 32)
        with self.assertRaisesRegex(ValueError, 'byte count'):
            fetcher.copy_verified(Response(data, {'Content-Length': str(len(data) + 1)}), io.BytesIO(), checksum)
        with patch.object(fetcher, 'MAX_BYTES', 3), self.assertRaisesRegex(ValueError, 'limit'):
            fetcher.copy_verified(Response(data), io.BytesIO(), checksum)

    def test_existing_output_is_refused_before_network(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(fetcher, 'build_opener') as opener:
            path = Path(directory) / 'hungary.osm.pbf'
            path.write_bytes(b'existing')
            with self.assertRaises(FileExistsError):
                fetcher.fetch(path)
            opener.assert_not_called()


class CountrySelectionTests(unittest.TestCase):
    def test_residential_name_alone_is_not_a_quarter_and_all_three_levels_are_selected(self):
        self.assertIsNone(extractor.classification({'name': 'Housing', 'landuse': 'residential'}))
        self.assertIsNotNone(extractor.classification({'name': 'Housing', 'landuse': 'residential', 'place': 'quarter'}))
        for level in ('9', '10', '11'):
            self.assertIsNotNone(extractor.classification({'boundary': 'administrative', 'admin_level': level}))
        self.assertTrue(extractor.municipality_tags({'boundary': 'administrative', 'admin_level': '6', 'name': 'Budapest'}))
        self.assertFalse(extractor.municipality_tags({'boundary': 'administrative', 'admin_level': '6', 'name': 'Pest'}))

    @unittest.skipUnless(HAS_GEOMETRY, 'Install pinned osmium/shapely for actual geometry regression')
    def test_partial_overlap_never_assigns_neighbouring_municipality(self):
        shapes = [box(0, 0, 4, 4), box(4, 0, 8, 4)]
        records = [{'key': 'osm:relation:1', 'canonicalName': 'Esztergom'},
                   {'key': 'osm:relation:2', 'canonicalName': 'Dorog'}]
        index = STRtree(shapes)
        def associate(shape, parents=None):
            return extractor.associate(shape, 'osm:relation:3', index, shapes, records, parents or {})
        self.assertEqual(associate(box(1, 1, 3, 3))['municipality'], 'Esztergom')
        self.assertIsNone(associate(box(3.9, 1, 4.1, 2))['municipality'])
        conflict = associate(box(1, 1, 3, 3), {'osm:relation:3': {'osm:relation:2'}})
        self.assertEqual(conflict['municipalityEvidence'], 'hierarchy_geometry_conflict')
        self.assertIsNone(conflict['municipality'])

    @unittest.skipUnless(HAS_GEOMETRY, 'Install pinned osmium/shapely for actual geometry regression')
    def test_municipality_aliases_do_not_create_budapest_ambiguity_or_foreign_pat_identity(self):
        def record(key, name, level='8', kind='relation', **tags):
            return {'key': key, 'canonicalName': name,
                    'source': {'osmType': kind, 'tags': {'name': name, 'admin_level': level, **tags}}}
        records = [record('bp6', 'Budapest', '6'), record('bp8', 'Budapest'),
                   record('pat-hu', 'Pat'), record('pat-sk', 'Patince', **{'name:hu': 'Pat'}),
                   record('gadacs-relation', 'Gadács'), record('gadacs-way', 'Gadács', kind='way')]
        polygons = {item['key']: box(0, 0, 1, 1) for item in records}
        selected, audit = extractor.select_municipality_boundaries(records, polygons, {'Budapest', 'Pat', 'Gadács'})
        self.assertEqual({item['key'] for item in selected}, {'bp6', 'pat-hu', 'gadacs-relation'})
        by_id = {item['id']: item for item in audit}
        self.assertEqual(by_id['bp8']['reason'], 'budapest_admin6_preferred')
        self.assertEqual(by_id['pat-sk']['reason'], 'primary_name_not_canonical_hungarian_municipality')
        self.assertEqual(by_id['gadacs-way']['aliasOf'], 'gadacs-relation')
        conflicting = [record('dorog-a', 'Dorog'), record('dorog-b', 'Dorog')]
        selected, audit = extractor.select_municipality_boundaries(conflicting,
            {'dorog-a': box(0, 0, 1, 1), 'dorog-b': box(0, 0, 2, 2)}, {'Dorog'})
        self.assertEqual(selected, [])
        self.assertTrue(all(item['reason'] == 'conflicting_same_name_municipality_boundaries' for item in audit))

    @unittest.skipUnless(HAS_GEOMETRY, 'Install pinned osmium/shapely for actual PBF regression')
    def test_real_pbf_relation_hole_node_inventory_and_construction_vertices(self):
        # Two adjacent municipality boundaries, a split-way quarter with a hole,
        # a cross-boundary quarter, one named point and one ordinary housing area.
        nodes, ways, relations = [], [], []
        next_node = 1
        def way(ident, points, tags=None):
            nonlocal next_node
            refs = []
            for lon, lat in points:
                refs.append(next_node)
                nodes.append(f'<node id="{next_node}" lat="{lat}" lon="{lon}" version="1"/>')
                next_node += 1
            if points[0] == points[-1]:
                # Closed OSM ways must share node identities, not only positions.
                refs[-1] = refs[0]
                nodes.pop()
                next_node -= 1
            content = ''.join(f'<nd ref="{ref}"/>' for ref in refs)
            content += ''.join(f'<tag k="{key}" v="{value}"/>' for key, value in (tags or {}).items())
            ways.append(f'<way id="{ident}" version="1">{content}</way>')
            return refs
        def relation(ident, members, tags):
            content = ''.join(f'<member type="{kind}" ref="{ref}" role="{role}"/>' for kind, ref, role in members)
            content += ''.join(f'<tag k="{key}" v="{value}"/>' for key, value in tags.items())
            relations.append(f'<relation id="{ident}" version="1">{content}</relation>')
        way(10, [(10, 10), (14, 10), (14, 14), (10, 14), (10, 10)])
        way(11, [(14, 10), (18, 10), (18, 14), (14, 14), (14, 10)])
        relation(100, [('way', 10, 'outer'), ('relation', 200, 'subarea')],
                 {'type': 'boundary', 'boundary': 'administrative', 'admin_level': '8', 'name': 'Esztergom'})
        relation(101, [('way', 11, 'outer')],
                 {'type': 'boundary', 'boundary': 'administrative', 'admin_level': '8', 'name': 'Dorog'})
        way(20, [(11, 11), (13, 11), (13, 13), (11, 13), (11, 11)])
        way(21, [(11.5, 11.5), (12, 11.5), (12, 12), (11.5, 12), (11.5, 11.5)])
        relation(200, [('way', 20, 'outer'), ('way', 21, 'inner')],
                 {'type': 'multipolygon', 'place': 'quarter', 'name': 'Várnegyed'})
        way(30, [(13.5, 11), (14.5, 11), (14.5, 12), (13.5, 12), (13.5, 11)],
            {'place': 'quarter', 'name': 'Across border'})
        way(31, [(15, 11), (16, 11), (16, 12), (15, 12), (15, 11)],
            {'landuse': 'residential', 'name': 'Ordinary housing'})
        road_refs = way(40, [(9, 11), (12, 11), (19, 11)], {'highway': 'residential', 'name': 'Határ út'})
        nodes.append('<node id="1000" lat="11.1" lon="15.1" version="1"><tag k="place" v="neighbourhood"/><tag k="name" v="Point only"/></node>')
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            xml_path, pbf_path = directory / 'fixture.osm', directory / 'fixture.osm.pbf'
            xml_path.write_text('<osm version="0.6">' + ''.join(nodes + ways + relations) + '</osm>', encoding='utf-8')
            writer = osmium.SimpleWriter(str(pbf_path))
            class Copy(osmium.SimpleHandler):
                def node(self, obj): writer.add_node(obj)
                def way(self, obj): writer.add_way(obj)
                def relation(self, obj): writer.add_relation(obj)
            Copy().apply_file(str(xml_path))
            writer.close()
            canonical = directory / 'settlements.json'
            canonical.write_text(json.dumps({'settlements': ['Esztergom', 'Dorog']}))
            output = directory / 'result'
            extractor.extract(pbf_path, output, canonical, [10, 10, 18, 14])
            polygons = json.loads((output / 'polygons.geojson').read_text())['features']
            by_name = {feature['properties']['name']: feature for feature in polygons}
            self.assertEqual(set(by_name), {'Várnegyed', 'Across border'})
            quarter = by_name['Várnegyed']
            self.assertEqual(quarter['properties']['municipality'], 'Esztergom')
            self.assertEqual(quarter['properties']['municipalityEvidence'], 'source_subarea_hierarchy_and_full_containment')
            self.assertEqual(len(quarter['geometry']['coordinates'][0]), 2)
            self.assertEqual(quarter['properties']['source']['members'][1]['role'], 'inner')
            self.assertIsNone(by_name['Across border']['properties']['municipality'])
            points = json.loads((output / 'named-nodes.geojson').read_text())['features']
            self.assertEqual(len(points), 1)
            self.assertEqual(points[0]['geometry']['type'], 'Point')
            self.assertEqual(points[0]['properties']['municipality'], 'Dorog')
            lines = json.loads((output / 'construction-lines.geojson').read_text())['features']
            road = next(feature for feature in lines if feature['id'] == 'osm:way:40')
            self.assertEqual(road['geometry']['coordinates'], [[9.0, 11.0], [12.0, 11.0], [19.0, 11.0]])
            self.assertEqual(road['properties']['source']['nodeRefs'], road_refs)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['counts']['polygons'], 2)
            self.assertEqual(manifest['input']['sha256'], extractor.file_hash(pbf_path))


if __name__ == '__main__':
    unittest.main()
