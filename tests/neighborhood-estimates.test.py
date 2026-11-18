"""Physical source-line cells are research geometry, never guessed legal quarters."""
import importlib.util
from pathlib import Path
import unittest

from shapely.geometry import LineString, MultiPolygon, Point, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('estimate_areas', ROOT / 'scripts/neighborhoods/estimate-areas.py')
prototype = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prototype)


def point(ident, name, x, y):
    return {'id': ident, 'name': name, 'geometry': Point(x, y)}


class PhysicalCellTests(unittest.TestCase):
    def setUp(self):
        self.parent = box(0, 0, 10, 10)
        self.barriers = [
            {'id': 'osm:way:1', 'geometry': LineString([(5, -2), (5, 12)])},
            {'id': 'osm:way:2', 'geometry': LineString([(-2, 5), (12, 5)])}]
        self.cells, self.clipped, self.stats = prototype.physical_cells(self.parent, self.barriers)

    def test_cells_use_only_actual_source_edges_and_stay_hard_inside_parent(self):
        self.assertEqual(len(self.cells), 4)
        source_network = unary_union([self.parent.boundary, *(record['geometry'] for record in self.clipped)])
        self.assertAlmostEqual(sum(cell.area for cell in self.cells), self.parent.area)
        for cell in self.cells:
            self.assertTrue(self.parent.covers(cell))
            self.assertEqual(cell.boundary.difference(source_network).length, 0,
                             'Polygonization cannot invent a closing edge or nearest-centre separator')
        self.assertEqual(self.stats['partitionDifferenceAreaM2'], 0)

    def test_dangling_lines_do_not_gain_fabricated_connections_or_split_the_municipality(self):
        cells, _, stats = prototype.physical_cells(self.parent, [
            {'id': 'osm:way:1', 'geometry': LineString([(5, 2), (5, 8)])}])
        self.assertEqual(len(cells), 1)
        self.assertFalse(stats['hasMeaningfulSplit'])
        groups, _ = prototype.assign_points(cells, [point('p:1', 'Entire town', 2, 2)])
        candidates, unresolved, _, _ = prototype.analyse_assignments('Town', cells, groups, {}, self.parent.area)
        self.assertEqual(candidates, [])
        self.assertEqual(unresolved[0]['reason'], 'no_meaningful_municipal_split')

    def test_boundary_points_and_two_names_in_one_cell_remain_unresolved(self):
        points = [point('p:boundary', 'Boundary', 5, 5),
                  point('p:a', 'First name', 1, 1), point('p:b', 'Second name', 2, 2)]
        groups, unresolved = prototype.assign_points(self.cells, points)
        self.assertEqual(unresolved[0]['reason'], 'point_on_cell_boundary')
        self.assertEqual(len(unresolved[0]['candidateCellIndexes']), 4)
        candidates, shared, _, _ = prototype.analyse_assignments('Town', self.cells, groups, {}, self.parent.area)
        self.assertEqual(candidates, [])
        self.assertEqual({record['id'] for record in shared}, {'p:a', 'p:b'})
        self.assertTrue(all(record['reason'] == 'shared_cell_multiple_names' for record in shared))

    def test_disconnected_municipal_parts_alone_are_not_a_physical_barrier_split(self):
        parent = MultiPolygon([box(0, 0, 2, 2), box(5, 5, 7, 7)])
        cells, _, stats = prototype.physical_cells(parent, [])
        self.assertEqual(len(cells), 2)
        self.assertFalse(stats['hasMeaningfulSplit'])
        groups, _ = prototype.assign_points(cells, [point('p:island', 'Island', 1, 1)])
        candidates, unresolved, _, _ = prototype.analyse_assignments(
            'Town', cells, groups, {}, parent.area, meaningful_split=stats['hasMeaningfulSplit'])
        self.assertEqual(candidates, [])
        self.assertEqual(unresolved[0]['reason'], 'no_meaningful_municipal_split')

    def test_known_quarter_filter_runs_after_benchmark_and_never_creates_an_estimate(self):
        groups, _ = prototype.assign_points(self.cells, [point('p:known', 'Új-Telep', 2, 2)])
        known = {prototype.normalized_name('uj telep'): box(0, 0, 5, 5)}
        candidates, unresolved, benchmarks, excluded = prototype.analyse_assignments(
            'Budapest', self.cells, groups, known, self.parent.area)
        self.assertEqual(candidates, [])
        self.assertEqual(unresolved[0]['reason'], 'known_polygon_available')
        self.assertEqual(len(benchmarks), 1)
        self.assertEqual(benchmarks[0]['iou'], 1)
        self.assertEqual(excluded, [])

    def test_known_name_outside_reference_geometry_is_explicit_benchmark_mismatch(self):
        groups, _ = prototype.assign_points(self.cells, [point('p:homonym', 'Same name', 2, 2)])
        known = {prototype.normalized_name('Same name'): box(5, 5, 10, 10)}
        candidates, _, benchmarks, excluded = prototype.analyse_assignments(
            'Town', self.cells, groups, known, self.parent.area)
        self.assertEqual(candidates, [])
        self.assertEqual(benchmarks, [])
        self.assertEqual(excluded[0]['reason'], 'known_name_geometry_mismatch')

    def test_poor_fit_fails_method_qa_and_is_not_reported_as_a_probability(self):
        records = [{'stratum': label, 'iou': 0.05, 'cellToKnownAreaRatio': 0.05,
                    'sharedDistinctNameCount': 1} for label in ('Budapest', 'outside_Budapest')]
        summary = prototype.benchmark_summary(records)
        self.assertFalse(summary['methodQaPassed'])
        self.assertIn('overall:median_iou_below_0.5', summary['failures'])
        self.assertIn('overall:mostly_tiny_cells', summary['failures'])
        self.assertIn('not probabilities', summary['interpretation'])


if __name__ == '__main__':
    unittest.main()
