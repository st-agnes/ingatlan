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
        (self.root / 'dist/data/settlements.json').write_text(json.dumps({'settlements': ['Debrecen', 'Győr', 'Budapest']}))
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

    def test_named_residential_proxy_beats_physical_barrier_cell(self):
        proxy = self.feature('Vénkert', method='named_point_source_footprint_estimate', semanticFootprint=True)
        barrier = self.feature('Vénkert', method='physical_barrier_cell_estimate', semanticFootprint=True, qualityScore=15)
        barrier['geometry']['coordinates'][0][1][0] = 21.64
        path = self.write('expansion-20261114/native/features.geojson', [barrier, proxy]); self.registry([path])
        files, _ = MODULE.build(); selected = json.loads(files['search-areas.geojson'])['features'][0]
        self.assertEqual(selected['geometry'], proxy['geometry'])
        self.assertEqual(MODULE.source_priority(barrier['properties'], 'features.geojson')[0], 50)

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

    def test_district_alias_uses_whole_district_geometry(self):
        quarter = self.feature('Újpest', 'Budapest', method='source_polygon', source={'provider':'openstreetmap','tags':{'boundary':'administrative'}})
        district = self.feature('IV. kerület', 'Budapest', method='source_polygon', sourceRole='district', aliases=['Újpest'])
        district['geometry']['coordinates'][0][1][0] = 21.65
        self.write('neighborhoods.geojson', [quarter])
        path = self.write('expansion-20261114/native/features.geojson', [district]); self.registry([path])
        files, _ = MODULE.build(); rows = json.loads(files['search-areas.geojson'])['features']
        self.assertEqual(len(rows), 1); self.assertEqual(rows[0]['geometry'], district['geometry'])

    def test_hand_inferred_osm_road_partition_is_not_a_native_boundary(self):
        inferred = self.feature('Tettye', method='rough_manual_map_partition', estimated=True, source={'provider':'openstreetmap'})
        path = self.write('expansion-20261114/native/features.geojson', [inferred]); self.registry([path])
        files, _ = MODULE.build(); row = json.loads(files['search-areas.geojson'])['features'][0]
        self.assertEqual(row['properties']['method'], 'map_or_text_estimate')
        self.assertTrue(row['properties']['estimated'])

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

    def persist_identities(self, files):
        (MODULE.DATA / 'search-area-identities.json').write_bytes(files['search-area-identities.json'])

    def test_new_earlier_alias_and_better_geometry_preserve_identity(self):
        self.write('estimated-candidates.geojson', [self.feature('Vénkert', method='map_trace')])
        first, _ = MODULE.build(); self.persist_identities(first)
        before = json.loads(first['search-areas.geojson'])['features'][0]
        better = self.feature('A-kert', method='source_polygon', aliases=['Vénkert'])
        better['geometry']['coordinates'][0][1][0] = 21.64
        self.write('neighborhoods.geojson', [better])
        second, _ = MODULE.build(); after = json.loads(second['search-areas.geojson'])['features'][0]
        self.assertEqual(after['id'], before['id'])
        self.assertEqual(after['properties']['canonicalNameKey'], before['properties']['canonicalNameKey'])
        self.assertEqual(after['geometry'], better['geometry'])
        self.assertEqual(json.loads(second['search-area-identities.json'])['redirects'], [])

    def test_explicit_merge_retires_only_losing_id_and_equivalence_survives(self):
        self.write('neighborhoods.geojson', [self.feature('Jamina'), self.feature('Erzsébethely')])
        first, _ = MODULE.build(); self.persist_identities(first)
        original = json.loads(first['search-areas.geojson'])['features']
        target, retired = sorted(f['id'] for f in original)
        canonical = next(f['properties']['canonicalNameKey'] for f in original if f['id'] == target)
        self.write('neighborhoods.geojson', [self.feature('Jamina', aliases=['Erzsébethely']), self.feature('Erzsébethely')])
        merged, report = MODULE.build(); self.persist_identities(merged)
        features = json.loads(merged['search-areas.geojson'])['features']
        self.assertEqual(len(features), 1); self.assertEqual(features[0]['id'], target)
        self.assertEqual(features[0]['properties']['canonicalNameKey'], canonical)
        redirects = json.loads(merged['search-area-identities.json'])['redirects']
        self.assertEqual(redirects, [{'retiredId': retired, 'targetId': target}])
        self.assertEqual(report['retiredIdentityCount'], 1)
        sql = gzip.decompress(merged['search-areas.mysql.sql.gz']).decode()
        deletion = next(line for line in sql.splitlines() if line.startswith('DELETE '))
        self.assertEqual(deletion, 'DELETE FROM NeighborhoodSearchAreas WHERE Id IN (' + MODULE.sql_text(retired) + ');')
        self.assertNotIn(MODULE.sql_text(target), deletion)
        self.assertLess(sql.index('START TRANSACTION;'), sql.index(deletion))
        self.assertLess(sql.index(deletion), sql.index('INSERT INTO'))
        # A later source no longer supplying the alias must not split the identity.
        self.write('neighborhoods.geojson', [self.feature('Jamina'), self.feature('Erzsébethely')])
        later, _ = MODULE.build(); result = json.loads(later['search-areas.geojson'])['features']
        self.assertEqual([f['id'] for f in result], [target])
        self.assertEqual(later['search-area-identities.json'], merged['search-area-identities.json'])

    def test_redirect_chain_flattens_after_another_explicit_merge(self):
        self.write('neighborhoods.geojson', [self.feature(name) for name in ['A', 'B', 'C']])
        initial, _ = MODULE.build(); self.persist_identities(initial)
        ordered = sorted(json.loads(initial['search-areas.geojson'])['features'], key=lambda f: f['id'])
        names = [f['properties']['name'] for f in ordered]
        self.write('neighborhoods.geojson', [self.feature(names[0]), self.feature(names[1], aliases=[names[2]]), self.feature(names[2])])
        middle, _ = MODULE.build(); self.persist_identities(middle)
        self.write('neighborhoods.geojson', [self.feature(names[0], aliases=[names[1]]), self.feature(names[1]), self.feature(names[2])])
        final, _ = MODULE.build(); redirects = json.loads(final['search-area-identities.json'])['redirects']
        self.assertEqual(len(redirects), 2)
        self.assertEqual({r['targetId'] for r in redirects}, {ordered[0]['id']})

if __name__ == '__main__': unittest.main()
