import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile, mkdtemp, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {gunzipSync} from 'node:zlib';
import {createNationwideReport, nationwideCsv, nationwideMarkdown, writeNationwideReports} from '../scripts/neighborhoods/nationwide-report.mjs';

const municipality = (name, extra = {}) => ({municipality: name, kshCode: name === 'A' ? '00001' : '00002', county: 'County', legalStatus: 'village',
  urbanNeighborhoodInventoryStatus: 'not_reviewed', settlementParts: [{id: name + ':part:1', name: 'Farm', category: 'outlying_area', nameIsGenericLabel: false}], nameReferences: [], ...extra});
const inventory = municipalities => ({referenceDate: '2026-01-01', scope: {countryMunicipalityListComplete: true}, sources: {}, municipalities});
const collection = features => ({type: 'FeatureCollection', features});
const polygon = (id, name, city, extra = {}) => ({type: 'Feature', id, properties: {id, name, municipality: city, boundaryKind: 'neighbourhood', source: {provider: 'openstreetmap'}, ...extra},
  geometry: {type: 'Polygon', coordinates: [[[20, 47], [20.1, 47], [20.1, 47.1], [20, 47]]]}});
const point = (id, name, city) => ({type: 'Feature', id, properties: {name, municipality: city, place: 'quarter', source: {url: 'https://example.test/' + id}}, geometry: {type: 'Point', coordinates: [20, 47]}});
const cityReport = (names = []) => ({cities: [{municipality: 'A', acceptedNeighbourhoodNames: names}]});

test('unknown quarter coverage and KSH categories remain distinct from observed geometry counts', () => {
  const report = createNationwideReport(inventory([municipality('A'), municipality('B')]), collection([]), cityReport());
  assert.equal(report.municipalities.length, 2);
  assert.equal(report.municipalities[0].kshSettlementParts.categoryCounts.outlying_area, 1);
  assert.equal(report.municipalities[0].acceptedQuarterNameCount, 0);
  assert.equal(report.municipalities[0].kshSettlementParts.isUrbanQuarterInventory, false);
  assert.ok(report.municipalities.every(row => row.totalCurrentQuarters === null && row.totalMissingCurrentQuarterBoundaries === null));
  assert.equal(report.municipalities[1].evidenceStatus, 'quarter_boundary_coverage_unknown');
  assert.equal(report.summary.totalMissingQuarterBoundariesNationwide, null);
});

test('manual construction method and planning semantic level are independent, and points deduplicate by city/name', () => {
  const catalog = collection([
    polygon('q', 'Újlak', 'A', {source: {provider: 'openstreetmap', collection: 'country-osm'}}),
    polygon('plan', 'Planning', 'A', {boundaryKind: 'planning_unit', canonicalNameIsNeighborhood: false, source: {provider: 'manual-derived', method: 'source-road-trace'}}),
    polygon('district', 'District', 'A', {boundaryKind: 'district'})]);
  const points = collection([point('p1', 'Ujlak', 'A'), point('p2', 'Kertváros', 'A'), point('p3', 'Kertvaros', 'A'), point('p4', 'Ujlak', 'B'), point('p5', 'Planning', 'A'), point('p6', 'District', 'A'), point('p7', 'Unknown', null)]);
  const report = createNationwideReport(inventory([municipality('A'), municipality('B')]), catalog, cityReport(['Újlak', 'Planning']), points);
  const [a, b] = report.municipalities;
  assert.equal(a.acceptedQuarterGeometryCount, 1); assert.equal(a.planningUnitGeometryCount, 1); assert.equal(a.manualDerivedGeometryCount, 1);
  assert.deepEqual(a.geometryMethodCounts, {city_osm_polygon: 1, country_osm_polygon: 1, manual_derived: 1});
  assert.deepEqual(a.manualConstructionMethodCounts, {'source-road-trace': 1});
  assert.equal(a.pointOnlyNameCount, 2); assert.equal(a.pointOnlyNames.find(row => row.name.startsWith('Kert')).sourceIds.length, 2);
  assert.equal(b.pointOnlyNameCount, 1); assert.equal(b.evidenceStatus, 'points_only');
  assert.equal(report.summary.unassignedPointRecords, 1);
  assert.equal(report.summary.assignedNamedPointRecords, 6);
});

test('accent distinctions in municipality names never merge separate KSH municipalities', () => {
  const report = createNationwideReport(inventory([
    municipality('Komló', {kshCode: '26408'}), municipality('Kömlő', {kshCode: '14535'})]), collection([]), {cities: []},
  collection([point('p1', 'Belváros', 'Komló'), point('p2', 'Kertváros', 'Kömlő')]));
  assert.equal(report.municipalities.length, 2);
  assert.equal(report.municipalities.find(row => row.kshCode === '26408').pointOnlyNames[0].name, 'Belváros');
  assert.equal(report.municipalities.find(row => row.kshCode === '14535').pointOnlyNames[0].name, 'Kertváros');
});

test('official quarter gaps retain distinct identities and documented equivalences, and planning units cannot fill them', () => {
  const reference = {id: 'official', title: 'Official', sourceUrl: 'https://example.test/list', category: 'urban_neighborhood', sourceIsOfficial: true,
    names: ['Gerce', 'Orbánhegy', 'Orbánhegy', 'Planning'], identities: [{}, {}, {}, {}], completeForReferencePeriod: true, currentCompletenessVerified: true};
  const report = createNationwideReport(inventory([municipality('A', {nameReferences: [reference]})]), collection([
    polygon('q', 'Gercse', 'A'), polygon('plan', 'Planning', 'A', {boundaryKind: 'planning_unit'})]), {
    cities: [{municipality: 'A', acceptedNeighbourhoodNames: ['Gercse'], referenceComparisons: [{sourceUrl: reference.sourceUrl,
      referenceIdentityCount: 4, missingNames: ['Orbánhegy', 'Planning'], totalKnownMissingIdentityCount: 3,
      additionalMissingIdentities: [{name: 'Orbánhegy', districts: [23]}], nameEquivalencesUsed: [{referenceName: 'Gerce', equivalentName: 'Gercse'}]}]}]});
  const row = report.municipalities[0], comparison = row.officialQuarterReferenceGaps[0];
  assert.equal(row.totalCurrentQuarters, 4); assert.equal(row.totalMissingCurrentQuarterBoundaries, 3);
  assert.equal(comparison.referenceNameEntryCount, 4); assert.equal(comparison.referenceUniqueNameCount, 3);
  assert.equal(comparison.additionalMissingIdentityCount, 1); assert.equal(comparison.nameEquivalencesUsed.length, 1);
  assert.equal(comparison.sourceId, 'official'); assert.equal(report.summary.completeNationalCoverage, false);
  assert.match(nationwideMarkdown(report), /Orbánhegy/);
  assert.equal(nationwideCsv(report).split('\r\n').filter(Boolean).length, 2);
});

test('all 3155 real municipality rows retain exact KSH part categories and unknown unreviewed totals', async () => {
  const actual = JSON.parse(await readFile(new URL('../data/neighborhoods/nationwide-inventory.json', import.meta.url), 'utf8'));
  const nodes = JSON.parse(gunzipSync(await readFile(new URL('../data/neighborhoods/sources/country-osm/named-nodes.geojson.gz', import.meta.url))));
  const report = createNationwideReport(actual, collection([]), {cities: []}, nodes);
  assert.equal(report.municipalities.length, 3155);
  assert.equal(new Set(report.municipalities.map(row => row.kshCode)).size, 3155);
  assert.equal(report.summary.kshSettlementPartRows, 13721);
  assert.deepEqual(report.summary.kshSettlementPartCategoryCounts, {central_built_up_area: 3178, other_built_up_area: 1054, outlying_area: 9489});
  assert.equal(report.summary.namedPointRecords, 3516); assert.equal(report.summary.unassignedPointRecords, 2);
  assert.equal(report.summary.municipalitiesWithNamedPoints, 485);
  assert.ok(report.municipalities.filter(row => row.urbanNeighborhoodInventoryStatus === 'not_reviewed').every(row => row.totalCurrentQuarters === null));
  assert.equal(nationwideCsv(report).split('\r\n').filter(Boolean).length, 3156);
});

test('custom-file CLI writer rejects stale city catalog references and detects stale generated outputs', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nationwide-report-'));
  try {
    const paths = {inventoryPath: join(directory, 'inventory.json'), catalogPath: join(directory, 'catalog.json'), cityReportPath: join(directory, 'city.json'), pointsPath: join(directory, 'points.json'), outputPrefix: join(directory, 'result')};
    await Promise.all([writeFile(paths.inventoryPath, JSON.stringify(inventory([municipality('A')]))), writeFile(paths.catalogPath, JSON.stringify(collection([]))),
      writeFile(paths.cityReportPath, JSON.stringify({...cityReport(), inputFingerprints: {catalogSha256: 'stale'}})), writeFile(paths.pointsPath, JSON.stringify(collection([])))]);
    await assert.rejects(writeNationwideReports(paths), /City report is stale/);
    await writeFile(paths.cityReportPath, JSON.stringify(cityReport()));
    await writeNationwideReports(paths); await writeNationwideReports({...paths, check: true});
    await writeFile(paths.outputPrefix + '.csv', 'stale');
    await assert.rejects(writeNationwideReports({...paths, check: true}), /is stale/);
  } finally { await rm(directory, {recursive: true, force: true}); }
});
