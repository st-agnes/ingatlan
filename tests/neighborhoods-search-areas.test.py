"""Release regression: aliases, alternative geometry selection and spatial export."""
import gzip, hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('search_areas', Path(__file__).resolve().parents[1] / 'scripts/neighborhoods/build-search-areas.py')
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)

class SearchAreaReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.old = MODULE.ROOT, MODULE.DATA, MODULE.EXPANSION
        MODULE.ROOT = self.root; MODULE.DATA = self.root / 'data/neighborhoods'
        MODULE.EXPANSION = MODULE.DATA / 'expansion-20261114'
        MODULE.EXPANSION.mkdir(parents=True); (self.root / 'dist/data').mkdir(parents=True)
        (self.root / 'dist/data/settlements.json').write_text(json.dumps({'settlements': ['Debrecen', 'Győr']}))
        for file in ('neighborhoods.geojson', 'estimated-candidates.geojson', 'planning-units.geojson'):
            self.write(file, [])
        self.registry([])

    def tearDown(self):
        MODULE.ROOT, MODULE.DATA, MODULE.EXPANSION = self.old; self.temp.cleanup()

    def write(self, filename, features):
        path = MODULE.DATA / filename; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'type': 'FeatureCollection', 'features': features}))
        return path

    def registry(self, paths):
        entries = [{'path': p.relative_to(self.root).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
        (MODULE.EXPANSION / 'input-registry.json').write_text(json.dumps({'datasets': entries}))

    def feature(self, name, city='Debrecen', **properties):
        return {'type': 'Feature', 'properties': {'name': name, 'municipality': city, **properties},
                'geometry': {'type': 'Polygon', 'coordinates': [[[21.60,47.55],[21.62,47.55],[21.62,47.57],[21.60,47.57],[21.60,47.55]]]}}

    def test_aliases_keep_one_best_boundary_and_all_evidence(self):
        self.write('estimated-candidates.geojson', [self.feature('József Attila-telep', aliases=['József Attila telep'])])
        native = self.feature('József Attila telep', method='source_polygon', source={'provider':'openstreetmap','tags':{'boundary':'administrative'}})
        native['geometry']['coordinates'][0][1][0] = 21.63
        self.write('neighborhoods.geojson', [native])
        files, report = MODULE.build(); features = json.loads(files['search-areas.geojson'])['features']
        self.assertEqual(len(features), 1); self.assertEqual(features[0]['geometry'], native['geometry'])
        self.assertEqual(len(features[0]['properties']['sourceAlternatives']), 2)
        self.assertEqual(report['duplicateVariantsPreserved'], 1)
        self.assertIn('József Attila-telep', features[0]['properties']['aliases'])

    def test_overlapping_parent_names_and_same_name_other_town_survive(self):
        self.write('neighborhoods.geojson', [self.feature('Belváros'), self.feature('Vénkert'), self.feature('Belváros', 'Győr')])
        files, report = MODULE.build(); features = json.loads(files['search-areas.geojson'])['features']
        self.assertEqual(report['featureCount'], 3); self.assertEqual(len({f['id'] for f in features}), 3)
        self.assertEqual(len({json.dumps(f['geometry']) for f in features}), 1)

    def test_complete_map_boundary_beats_named_landuse_footprint(self):
        self.write('estimated-candidates.geojson', [self.feature('Vénkert', method='rough_map_trace')])
        path = self.write('expansion-20261114/native/features.geojson', [self.feature('Vénkert', method='source_polygon', semanticFootprint=True)])
        self.registry([path]); files, _ = MODULE.build()
        self.assertEqual(json.loads(files['search-areas.geojson'])['features'][0]['properties']['method'], 'map_or_text_estimate')

    def test_registered_source_cannot_change_silently(self):
        path = self.write('expansion-20261114/native/features.geojson', [self.feature('Vénkert')])
        self.registry([path]); path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'Changed registered source'): MODULE.build()

    def test_whole_quarter_selected_over_same_name_core(self):
        core = self.feature('Nádorváros', 'Győr', method='source_vector', sourceSubdivisionKind='circuit')
        parent = self.feature('Nádorváros', 'Győr', method='source_vector', sourceSubdivisionKind='parent_quarter')
        parent['geometry']['coordinates'][0][1][0] = 21.64
        path = self.write('expansion-20261114/native/features.geojson', [core, parent]); self.registry([path])
        files, _ = MODULE.build(); features = json.loads(files['search-areas.geojson'])['features']
        self.assertEqual(features[0]['geometry'], parent['geometry'])

    def test_low_quality_new_estimate_does_not_replace_existing_map(self):
        baseline = self.feature('Vénkert', method='map_trace')
        rough = self.feature('Vénkert', method='rough_map_trace', qualityScore=20)
        rough['geometry']['coordinates'][0][1][0] = 21.64
        self.write('estimated-candidates.geojson', [baseline])
        path = self.write('expansion-20261114/native/features.geojson', [rough]); self.registry([path])
        files, _ = MODULE.build()
        self.assertEqual(json.loads(files['search-areas.geojson'])['features'][0]['geometry'], baseline['geometry'])

    def test_invalid_coordinates_rejected_and_holes_preserved_in_mysql(self):
        feature = self.feature('Vénkert'); hole = [[21.605,47.555],[21.605,47.56],[21.61,47.56],[21.61,47.555],[21.605,47.555]]
        feature['geometry']['coordinates'].append(hole)
        wrong = self.feature('Pixel coordinates'); wrong['geometry']['coordinates'][0][0] = [1500,900]
        self.write('neighborhoods.geojson', [feature, wrong]); files, report = MODULE.build()
        self.assertEqual(report['featureCount'], 1); self.assertEqual(len(report['rejectedTechnicalRecords']), 1)
        sql = gzip.decompress(files['search-areas.mysql.sql.gz']).decode()
        self.assertIn(MODULE.packed(feature['geometry']).encode().hex(), sql)
        self.assertIn('SPATIAL INDEX', sql); self.assertIn('SRID 4326', sql)
        self.assertIn('ST_Intersects', sql); self.assertNotIn('DROP TABLE', sql)

if __name__ == '__main__': unittest.main()
