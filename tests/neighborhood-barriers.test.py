"""Selection and actual-PBF regressions for the nationwide source-line extractor."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'extract_barriers', ROOT / 'scripts/neighborhoods/extract-barriers.py')
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)

try:
    import osmium
    HAS_OSMIUM = True
except ImportError:
    HAS_OSMIUM = False


class BarrierSelectionTests(unittest.TestCase):
    def test_major_roads_and_their_links_are_source_lines_without_name_requirements(self):
        road_classes = ('motorway', 'trunk', 'primary', 'secondary', 'tertiary')
        for highway in (*road_classes, *(value + '_link' for value in road_classes)):
            with self.subTest(highway=highway):
                self.assertEqual(extractor.select_barrier({'highway': highway}), ['road'])
        for tags in ({'highway': 'residential', 'name': 'Főút'},
                     {'highway': 'footway'}, {'building': 'yes', 'name': 'Városrész'}):
            with self.subTest(tags=tags):
                self.assertEqual(extractor.select_barrier(tags), [])

    def test_actual_rail_and_river_or_canal_tags_are_selected_and_streams_are_optional(self):
        self.assertEqual(extractor.select_barrier({'railway': 'rail'}), ['railway'])
        self.assertEqual(extractor.select_barrier({'railway': 'tram'}), [])
        for waterway in ('river', 'canal'):
            with self.subTest(waterway=waterway):
                self.assertEqual(extractor.select_barrier({'waterway': waterway}), ['waterway'])
        self.assertEqual(extractor.select_barrier({'waterway': 'stream'}), [])
        self.assertEqual(extractor.select_barrier({'waterway': 'stream'}, include_streams=True), ['waterway'])
        categories = extractor.select_barrier({'highway': 'primary', 'railway': 'rail', 'waterway': 'river'})
        self.assertEqual(set(categories), {'road', 'railway', 'waterway'})
        self.assertEqual(len(categories), 3)


@unittest.skipUnless(HAS_OSMIUM, 'Install pinned osmium for actual-PBF barrier extraction regression')
class BarrierPbfTests(unittest.TestCase):
    def fixture(self, directory):
        xml = ET.Element('osm', version='0.6')
        positions = {}
        # Hundreds of unrelated source nodes must feed only the native location
        # cache. The Python handler receives filtered ways, never these nodes.
        for ident in range(1, 513):
            lon, lat = 19 + ident / 10000, 47 + ident / 10000
            positions[ident] = [lon, lat]
            ET.SubElement(xml, 'node', id=str(ident), lon=str(lon), lat=str(lat), version='1')
        ways = {
            101: ([1, 2, 3], {'highway': 'primary', 'name': 'Főút'}),
            102: ([3, 4, 5], {'highway': 'primary_link'}),
            103: ([6, 7], {'highway': 'residential', 'name': 'Lakó utca'}),
            104: ([8, 9, 10], {'railway': 'rail'}),
            105: ([11, 12], {'railway': 'tram'}),
            106: ([13, 14, 15], {'waterway': 'river'}),
            107: ([16, 17, 18], {'waterway': 'canal'}),
            108: ([19, 20, 21], {'waterway': 'stream'}),
            109: ([100, 101, 102, 103, 100], {'building': 'yes'}),
        }
        for ident, (refs, tags) in ways.items():
            element = ET.SubElement(xml, 'way', id=str(ident), version='3',
                                    timestamp='2026-11-12T12:00:00Z', changeset='20')
            for ref in refs:
                ET.SubElement(element, 'nd', ref=str(ref))
            for key, value in tags.items():
                ET.SubElement(element, 'tag', k=key, v=value)
        xml_path, pbf_path = directory / 'fixture.osm', directory / 'fixture.osm.pbf'
        ET.ElementTree(xml).write(xml_path, encoding='utf-8', xml_declaration=True)
        writer = osmium.SimpleWriter(str(pbf_path))

        class Copy(osmium.SimpleHandler):
            def node(self, obj):
                writer.add_node(obj)

            def way(self, obj):
                writer.add_way(obj)

        Copy().apply_file(str(xml_path))
        writer.close()
        return pbf_path, positions, ways

    def read_output(self, output):
        raw = (output / 'barriers.ndjson').read_bytes()
        features = [json.loads(line) for line in raw.splitlines()]
        manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
        return features, manifest

    def test_filtered_way_callbacks_preserve_exact_complete_source_lines_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            input_path, positions, ways = self.fixture(directory)
            output = directory / 'default'
            extractor.extract(input_path, output)
            features, manifest = self.read_output(output)
            by_id = {feature['properties']['source']['osmId']: feature for feature in features}
            self.assertEqual(set(by_id), {101, 102, 104, 106, 107})
            self.assertEqual(len(features), 5)
            self.assertEqual(manifest['stats']['wayCallbacks'], 8,
                             'Native KeyFilter must skip the unrelated building way and every node')
            self.assertEqual(manifest['stats']['selectedWays'], 5)
            pbf_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()
            expected_kinds = {101: ['road'], 102: ['road'], 104: ['railway'],
                              106: ['waterway'], 107: ['waterway']}
            for ident, feature in by_id.items():
                refs, tags = ways[ident]
                source = feature['properties']['source']
                self.assertEqual(feature['type'], 'Feature')
                self.assertEqual(feature['id'], f'osm:way:{ident}')
                self.assertEqual(feature['properties']['barrierKinds'], expected_kinds[ident])
                self.assertEqual(feature['geometry']['type'], 'LineString')
                self.assertEqual(feature['geometry']['coordinates'], [positions[ref] for ref in refs],
                                 'Every coordinate must be an original source node, in source order')
                self.assertEqual(source['nodeRefs'], refs)
                self.assertEqual(source['tags'], tags)
                self.assertEqual(source['osmType'], 'way')
                self.assertEqual(source['osmId'], ident)
                self.assertEqual(source['objectVersion'], 3)
                self.assertIn('2026-11-12', source['objectTimestamp'])
                self.assertEqual(source['url'], f'https://www.openstreetmap.org/way/{ident}')
                self.assertEqual(source['pbfSha256'], pbf_sha256)

    def test_optional_streams_add_only_actual_stream_ways(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            input_path, positions, ways = self.fixture(directory)
            output = directory / 'streams'
            extractor.extract(input_path, output, include_streams=True, index_type='sparse_file_array')
            features, manifest = self.read_output(output)
            by_id = {feature['properties']['source']['osmId']: feature for feature in features}
            self.assertEqual(set(by_id), {101, 102, 104, 106, 107, 108})
            self.assertEqual(manifest['stats']['wayCallbacks'], 8)
            self.assertEqual(manifest['stats']['selectedWays'], 6)
            refs = ways[108][0]
            self.assertEqual(by_id[108]['geometry']['coordinates'], [positions[ref] for ref in refs])
            self.assertEqual(by_id[108]['properties']['source']['nodeRefs'], refs)


if __name__ == '__main__':
    unittest.main()
