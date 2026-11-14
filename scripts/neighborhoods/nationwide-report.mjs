import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {gunzipSync} from 'node:zlib';
import {normalizeName} from './report.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const order = (a, b) => normalizeName(a).localeCompare(normalizeName(b), 'en') || String(a).localeCompare(String(b), 'en');
const unique = names => [...new Map([...names].sort(order).map(name => [normalizeName(name), name])).values()].sort(order);
const countBy = values => Object.fromEntries([...values.reduce((map, value) => map.set(value, (map.get(value) ?? 0) + 1), new Map())].sort(([a], [b]) => order(a, b)));
const sourceId = feature => String(feature.id ?? feature.properties?.id ?? '');
const nameOf = feature => feature.properties.canonicalName ?? feature.properties.nameAudit?.proposedHungarianName ?? feature.properties.name;
// Hungarian accents distinguish municipality identities: Komló/Kömlő and Komoró/Kömörő.
const municipalityKey = value => String(value ?? '').normalize('NFC').trim();

export function geometryMethod(feature) {
  const source = feature.properties.source ?? {};
  if (source.provider === 'manual-derived') return 'manual_derived';
  if (source.provider === 'openstreetmap') {
    if (source.historical === true) return 'historical_osm_polygon';
    return source.collection === 'country-osm' ? 'country_osm_polygon' : 'city_osm_polygon';
  }
  return source.provider === 'whosonfirst' ? 'whosonfirst_polygon' : 'other_source_polygon';
}

function geometryClass(feature, acceptedNames) {
  const p = feature.properties;
  if (p.boundaryKind === 'district') return 'district';
  if (p.boundaryKind === 'planning_unit') return 'planning_unit';
  if (p.boundaryKind === 'local_area' || p.canonicalNameIsNeighborhood === false) return 'other_local_area';
  return acceptedNames.has(normalizeName(nameOf(feature))) ? 'accepted_quarter' : 'unaccepted_source_area';
}

function geometryRecord(feature, acceptedNames) {
  const p = feature.properties, source = p.source ?? {};
  return {id: sourceId(feature), name: nameOf(feature), sourceName: p.sourceName ?? p.name,
    semanticClass: geometryClass(feature, acceptedNames), boundaryKind: p.boundaryKind ?? 'unknown',
    geometryType: feature.geometry.type, method: geometryMethod(feature),
    constructionMethod: source.method ?? null, provider: source.provider ?? 'unknown',
    sourceUrl: source.url ?? null, sourcePath: source.path ?? null,
    sourceSha256: source.sha256 ?? null, geometrySha256: source.geometrySha256 ?? null,
    sourceCollection: source.collection ?? null, sourceObjectId: source.osmId ?? source.featureId ?? null,
    sourceDate: source.osmTimestamp ?? source.snapshotDate ?? source.sourceCommitDate ?? null,
    license: source.license ?? null, licenseUrl: source.licenseUrl ?? null,
    attribution: source.attribution ?? null, sourceIsOfficial: p.sourceIsOfficial === true,
    geometryVerificationStatus: p.geometryVerificationStatus ?? 'unrecorded',
    usableForAddressAssignment: false};
}

function referenceComparison(reference, city, representedQuarterNames, representedAreaNames) {
  const names = unique(reference.names ?? []), isQuarter = reference.category === 'urban_neighborhood';
  // Existing comparisons retain documented spelling equivalences and same-named distinct identities.
  const existing = isQuarter ? city?.referenceComparisons?.find(row => row.sourceUrl === reference.sourceUrl) : null;
  const represented = isQuarter ? representedQuarterNames : representedAreaNames;
  const missingNames = existing?.missingNames ?? names.filter(name => !represented.has(normalizeName(name)));
  const additionalMissingIdentities = existing?.additionalMissingIdentities ?? [];
  const identityCount = existing?.referenceIdentityCount ?? (Array.isArray(reference.identities) ? reference.identities.length : null);
  return {sourceId: reference.id, title: reference.title, sourceUrl: reference.sourceUrl,
    category: reference.category, sourceIsOfficial: reference.sourceIsOfficial === true,
    referencePeriod: reference.referencePeriod ?? null, license: reference.license ?? null,
    completeForReferencePeriod: reference.completeForReferencePeriod === true,
    currentCompletenessVerified: reference.currentCompletenessVerified === true,
    comparisonBasis: isQuarter ? 'accepted_quarter_names' : 'catalog_area_names_only',
    boundaryAccuracyVerified: false, referenceNameEntryCount: (reference.names ?? []).length,
    referenceUniqueNameCount: names.length, referenceIdentityCount: identityCount,
    names, matchedNameCount: names.length - missingNames.length,
    missingNameCount: missingNames.length, missingNames,
    additionalMissingIdentityCount: additionalMissingIdentities.length, additionalMissingIdentities,
    totalKnownMissingIdentityCount: existing?.totalKnownMissingIdentityCount ??
      (identityCount !== null && unique(reference.names ?? []).length === (reference.names ?? []).length ? missingNames.length : null),
    nameEquivalencesUsed: existing?.nameEquivalencesUsed ?? [],
    note: 'A name match does not verify the boundary or equate planning/statistical units with urban quarters.'};
}

/** Full municipality denominator, partial evidence. KSH parts never become urban quarters. */
export function createNationwideReport(inventory, catalog, cityReport, points = {type: 'FeatureCollection', features: []}) {
  if (!Array.isArray(inventory?.municipalities) || catalog?.type !== 'FeatureCollection' || !Array.isArray(catalog.features)
      || !Array.isArray(cityReport?.cities) || !Array.isArray(points?.features)) throw new Error('Invalid nationwide report inputs');
  const canonical = new Map(), byGeometry = new Map(), byPoints = new Map();
  for (const municipality of inventory.municipalities) {
    const key = municipalityKey(municipality.municipality);
    if (canonical.has(key) || !municipality.kshCode) throw new Error('Duplicate or missing municipality identity');
    canonical.set(key, municipality);
  }
  const cityByName = new Map(cityReport.cities.map(row => [municipalityKey(row.municipality), row]));
  const unassignedPoints = [], geometryIds = new Set(), pointIds = new Set();
  for (const feature of catalog.features) {
    if (!['Polygon', 'MultiPolygon'].includes(feature.geometry?.type)) throw new Error('Catalogue contains a non-area geometry');
    const id = sourceId(feature), key = municipalityKey(feature.properties?.municipality);
    if (!id || geometryIds.has(id)) throw new Error('Duplicate or missing geometry source identity');
    geometryIds.add(id);
    if (!canonical.has(key)) throw new Error('Catalogue municipality missing from national inventory: ' + feature.properties?.municipality);
    if (!byGeometry.has(key)) byGeometry.set(key, []);
    byGeometry.get(key).push(feature);
  }
  for (const feature of points.features) {
    if (!['Point', 'MultiPoint'].includes(feature.geometry?.type)) throw new Error('Point inventory contains a non-point geometry');
    const id = sourceId(feature), p = feature.properties ?? {}, key = municipalityKey(p.municipality);
    if (!id || pointIds.has(id)) throw new Error('Duplicate or missing point source identity');
    pointIds.add(id);
    if (!canonical.has(key)) { unassignedPoints.push({id, name: p.name, sourceUrl: p.source?.url ?? null, reason: 'unresolved_municipality'}); continue; }
    if (!byPoints.has(key)) byPoints.set(key, []);
    byPoints.get(key).push(feature);
  }
  const municipalities = [...inventory.municipalities].sort((a, b) => order(a.municipality, b.municipality)).map(municipality => {
    const key = municipalityKey(municipality.municipality), city = cityByName.get(key);
    const areas = byGeometry.get(key) ?? [], nodeFeatures = byPoints.get(key) ?? [];
    const acceptedNames = new Set((city?.acceptedNeighbourhoodNames ?? []).map(normalizeName));
    const geometries = areas.map(feature => geometryRecord(feature, acceptedNames)).sort((a, b) => order(a.id, b.id));
    const quarters = geometries.filter(row => row.semanticClass === 'accepted_quarter');
    const quarterNames = unique(quarters.map(row => row.name));
    const areaNames = new Set(areas.filter(feature => feature.properties.boundaryKind !== 'district')
      .flatMap(feature => [nameOf(feature), feature.properties.name, feature.properties.sourceName]).filter(Boolean).map(normalizeName));
    const quarterNameSet = new Set(quarterNames.map(normalizeName));
    const gaps = new Map();
    for (const feature of nodeFeatures) {
      const p = feature.properties, nameKey = normalizeName(p.name);
      if (!nameKey || areaNames.has(nameKey)) continue;
      const gap = gaps.get(nameKey) ?? {name: p.name, sourceIds: [], sourceUrls: [], placeKinds: [], geometryStatus: 'point_only', currentQuarterStatus: 'unverified'};
      gap.sourceIds.push(sourceId(feature));
      if (p.source?.url && !gap.sourceUrls.includes(p.source.url)) gap.sourceUrls.push(p.source.url);
      if (p.place && !gap.placeKinds.includes(p.place)) gap.placeKinds.push(p.place);
      gaps.set(nameKey, gap);
    }
    const pointOnlyNames = [...gaps.values()].sort((a, b) => order(a.name, b.name));
    const references = (municipality.nameReferences ?? []).map(reference => referenceComparison(reference, city, quarterNameSet, areaNames));
    const currentOfficialQuarterReferences = references.filter(row => row.category === 'urban_neighborhood' && row.sourceIsOfficial && row.currentCompletenessVerified && row.completeForReferencePeriod);
    const officialQuarterReferenceGaps = references.filter(row => row.category === 'urban_neighborhood' && row.sourceIsOfficial);
    const currentReference = currentOfficialQuarterReferences.length === 1 ? currentOfficialQuarterReferences[0] : null;
    return {municipality: municipality.municipality, kshCode: municipality.kshCode, county: municipality.county,
      legalStatus: municipality.legalStatus, urbanNeighborhoodInventoryStatus: municipality.urbanNeighborhoodInventoryStatus,
      evidenceStatus: quarters.length ? 'quarter_polygons_collected' : geometries.some(row => ['planning_unit', 'other_local_area'].includes(row.semanticClass))
        ? 'other_area_polygons_collected' : nodeFeatures.length ? 'points_only' : 'quarter_boundary_coverage_unknown',
      completeQuarterBoundaryCoverage: false, totalCurrentQuarters: currentReference?.referenceIdentityCount ?? null,
      totalMissingCurrentQuarterBoundaries: currentReference?.totalKnownMissingIdentityCount ?? null,
      kshSettlementParts: {sourceId: 'ksh-hnt-2026', rowCount: municipality.settlementParts.length,
        categoryCounts: countBy(municipality.settlementParts.map(part => part.category)),
        namedNonGenericCount: municipality.settlementParts.filter(part => !part.nameIsGenericLabel).length,
        sourceIds: municipality.settlementParts.map(part => part.id), isUrbanQuarterInventory: false},
      geometryCount: geometries.length, geometryClassCounts: countBy(geometries.map(row => row.semanticClass)),
      geometryMethodCounts: countBy(geometries.map(row => row.method)),
      manualConstructionMethodCounts: countBy(geometries.filter(row => row.method === 'manual_derived').map(row => row.constructionMethod ?? 'unrecorded')),
      acceptedQuarterGeometryCount: quarters.length, acceptedQuarterNameCount: quarterNames.length, acceptedQuarterNames: quarterNames,
      planningUnitGeometryCount: geometries.filter(row => row.semanticClass === 'planning_unit').length,
      manualDerivedGeometryCount: geometries.filter(row => row.method === 'manual_derived').length,
      districtGeometryCount: geometries.filter(row => row.semanticClass === 'district').length,
      geometries, namedPointRecordCount: nodeFeatures.length, namedPointSourceIds: nodeFeatures.map(sourceId).sort(order), pointOnlyNameCount: pointOnlyNames.length, pointOnlyNames,
      referenceSourceIds: references.map(row => row.sourceId), references, officialQuarterReferenceGaps,
      usableForAddressAssignment: false};
  });
  const allGeometries = municipalities.flatMap(row => row.geometries), allReferences = municipalities.flatMap(row => row.references);
  return {schemaVersion: 1, status: 'partial_quarter_boundary_collection', referenceDate: inventory.referenceDate,
    scope: {country: 'HU', municipalityDenominatorComplete: inventory.scope?.countryMunicipalityListComplete === true,
      urbanQuarterNameInventoryComplete: false, quarterBoundariesComplete: false, usableForAddressAssignment: false},
    countingPolicy: {municipalities: 'One row per KSH municipality; Budapest districts remain within Budapest.',
      geometry: 'One existing Polygon/MultiPolygon feature, preserving semantic level and method as separate axes.',
      quarters: 'Accepted quarter names from the city report, excluding districts, planning units and explicit broader/local-area classifications.',
      points: 'Country named point records deduplicate within each exact canonical municipality by normalized area name; existing non-district polygon names are subtracted. Point-only names are unverified quarter candidates.',
      kshParts: 'Central built-up, other built-up and outlying parts retain KSH categories and never count as urban quarters.',
      missing: 'Known source-reference gaps are partial evidence; unreviewed municipalities have unknown totals, never an inferred absence of quarters.'},
    summary: {municipalities: municipalities.length, citiesIncludingCapital: municipalities.filter(row => ['capital', 'city', 'county_rank_city'].includes(row.legalStatus)).length,
      municipalitiesWithAcceptedQuarterGeometry: municipalities.filter(row => row.acceptedQuarterGeometryCount).length,
      acceptedQuarterGeometryCount: municipalities.reduce((sum, row) => sum + row.acceptedQuarterGeometryCount, 0),
      acceptedQuarterNameCount: municipalities.reduce((sum, row) => sum + row.acceptedQuarterNameCount, 0),
      geometryCount: allGeometries.length, geometryClassCounts: countBy(allGeometries.map(row => row.semanticClass)),
      geometryMethodCounts: countBy(allGeometries.map(row => row.method)),
      manualConstructionMethodCounts: countBy(allGeometries.filter(row => row.method === 'manual_derived').map(row => row.constructionMethod ?? 'unrecorded')),
      municipalitiesByEvidenceStatus: countBy(municipalities.map(row => row.evidenceStatus)),
      municipalitiesByNameInventoryStatus: countBy(municipalities.map(row => row.urbanNeighborhoodInventoryStatus ?? 'unknown')),
      kshSettlementPartRows: municipalities.reduce((sum, row) => sum + row.kshSettlementParts.rowCount, 0),
      kshSettlementPartCategoryCounts: countBy(inventory.municipalities.flatMap(row => row.settlementParts.map(part => part.category))),
      namedPointRecords: points.features.length, assignedNamedPointRecords: points.features.length - unassignedPoints.length,
      municipalitiesWithNamedPoints: municipalities.filter(row => row.namedPointRecordCount).length,
      pointOnlyNameCount: municipalities.reduce((sum, row) => sum + row.pointOnlyNameCount, 0),
      municipalitiesWithPointOnlyNames: municipalities.filter(row => row.pointOnlyNameCount).length,
      unassignedPointRecords: unassignedPoints.length, referenceSources: allReferences.length,
      referenceSourceCategoryCounts: countBy(allReferences.map(row => row.category)),
      referenceNameEntryCount: allReferences.reduce((sum, row) => sum + row.referenceNameEntryCount, 0),
      referenceNameEntryCountsByCategory: countBy(allReferences.flatMap(row => Array(row.referenceNameEntryCount).fill(row.category))),
      officialQuarterReferenceSources: allReferences.filter(row => row.category === 'urban_neighborhood' && row.sourceIsOfficial).length,
      officialQuarterReferenceMissingNames: allReferences.filter(row => row.category === 'urban_neighborhood' && row.sourceIsOfficial).reduce((sum, row) => sum + row.missingNameCount, 0),
      municipalitiesWithCompleteCurrentOfficialQuarterReference: municipalities.filter(row => row.references.some(reference => reference.category === 'urban_neighborhood' && reference.sourceIsOfficial && reference.currentCompletenessVerified && reference.completeForReferencePeriod)).length,
      totalCurrentQuartersNationwide: null, totalMissingQuarterBoundariesNationwide: null, completeNationalCoverage: false},
    sources: {...inventory.sources, countryNamedPoints: {provider: 'openstreetmap',
      sourceId: 'country-osm:named-nodes', license: 'ODbL-1.0', attribution: '© OpenStreetMap contributors',
      attributionUrl: 'https://www.openstreetmap.org/copyright',
      osmTimestamp: points.features[0]?.properties?.source?.osmTimestamp ?? null,
      pbfSha256: points.features[0]?.properties?.source?.pbfSha256 ?? null}}, unassignedPoints, municipalities};
}

const csvCell = value => '"' + String(value ?? '').replaceAll('"', '""') + '"';
export function nationwideCsv(report) {
  const rows = [['municipality', 'ksh_code', 'county', 'legal_status', 'evidence_status', 'quarter_geometry_count', 'quarter_name_count', 'planning_unit_geometry_count', 'manual_derived_geometry_count', 'district_geometry_count', 'point_only_name_count', 'ksh_central_built_up', 'ksh_other_built_up', 'ksh_outlying', 'name_inventory_status', 'known_current_quarter_total', 'known_current_missing_boundaries', 'geometry_methods', 'reference_source_ids']];
  for (const row of report.municipalities) rows.push([row.municipality, row.kshCode, row.county, row.legalStatus, row.evidenceStatus,
    row.acceptedQuarterGeometryCount, row.acceptedQuarterNameCount, row.planningUnitGeometryCount, row.manualDerivedGeometryCount, row.districtGeometryCount, row.pointOnlyNameCount,
    row.kshSettlementParts.categoryCounts.central_built_up_area ?? 0, row.kshSettlementParts.categoryCounts.other_built_up_area ?? 0, row.kshSettlementParts.categoryCounts.outlying_area ?? 0,
    row.urbanNeighborhoodInventoryStatus, row.totalCurrentQuarters, row.totalMissingCurrentQuarterBoundaries, JSON.stringify(row.geometryMethodCounts), row.referenceSourceIds.join(', ')]);
  return '\uFEFF' + rows.map(row => row.map(csvCell).join(';')).join('\r\n') + '\r\n';
}
const md = value => String(value ?? '').replaceAll('|', '\\|').replaceAll('\n', ' ');
export function nationwideMarkdown(report) {
  const s = report.summary, lines = ['# Országos települési városrészhatár-lefedettség', '',
    `A jelentés mind a ${s.municipalities} KSH-települést tartalmazza. ${s.acceptedQuarterNameCount} elfogadott térképi városrésznévhez ${s.acceptedQuarterGeometryCount} geometria tartozik ${s.municipalitiesWithAcceptedQuarterGeometry} településen. Az országos városrésznévjegyzék és a határállomány továbbra sem teljes; az összes jelenlegi városrész és a hiányzó határok országos száma ismeretlen.`, '',
    `A ${s.kshSettlementPartRows} KSH-településrészrekord központi belterület, egyéb belterület vagy külterület marad; ezek nem városrészpoligonok. A pontforrás ${s.namedPointRecords} rekordjából ${s.unassignedPointRecords} településhez nem rendelhető. A már ismert poligonnevek levonása és névegyeztetés után ${s.pointOnlyNameCount} további pontnévhez nincs összegyűjtött határ; ezek mai városrészi státusza nincs igazolva.`, '',
    'A geometria szemantikai szintje (városrész, tervezési egység, helyi terület, kerület) és készítési módja külön adat. A kézzel származtatott geometriák sem jelentik a határ jogi vagy címhozzárendelési ellenőrzését.', '',
    '| Geometriai módszer | Darab |', '|---|---:|', ...Object.entries(s.geometryMethodCounts).map(([method, count]) => `| ${md(method)} | ${count} |`), '',
    '## Hivatalos városrésznév-referenciák ismert hiányai', '',
    'A hiány kizárólag az adott névjegyzékhez képest értendő. A történeti és részleges listák nem bizonyítják a mai összes városrész számát. Az azonos nevű külön területek azonosítói külön maradnak.'];
  for (const row of report.municipalities) for (const reference of row.officialQuarterReferenceGaps) {
    lines.push('', `**${md(row.municipality)} — [${md(reference.title)}](${reference.sourceUrl})** (${md(reference.sourceId)}; ${md(reference.referencePeriod)}). ${reference.referenceUniqueNameCount} különböző névből ${reference.missingNameCount} névhez nincs elfogadott városrészgeometria${reference.totalKnownMissingIdentityCount !== null ? '; ismert hiányzó területi azonosság: ' + reference.totalKnownMissingIdentityCount : ''}.`, '',
      reference.missingNames.length ? reference.missingNames.map(md).join(', ') + '.' : 'A név szerinti összehasonlításban nincs hiány.',
      ...reference.additionalMissingIdentities.map(identity => `- További azonos nevű terület: ${md(identity.name)} (${(identity.districts ?? []).join(', ')}. kerület). ${md(identity.note ?? '')}`));
  }
  lines.push('', `## Mind a ${s.municipalities} település`, '', 'Az „ismeretlen” állapot nem jelenti a városrészek hiányát. A teljes forrásazonosítók, módszerek, kategóriák és hiányzó nevek a JSON-fájlban vannak.', '',
    '| Település | KSH | Városrésznév / geometria | Tervezési geometria | Kézzel származtatott | Pontnév határ nélkül | Névjegyzék állapota |', '|---|---|---:|---:|---:|---:|---|');
  for (const row of report.municipalities) lines.push(`| ${md(row.municipality)} | ${row.kshCode} | ${row.acceptedQuarterNameCount} / ${row.acceptedQuarterGeometryCount} | ${row.planningUnitGeometryCount} | ${row.manualDerivedGeometryCount} | ${row.pointOnlyNameCount} | ${md(row.urbanNeighborhoodInventoryStatus)} |`);
  return lines.join('\n') + '\n';
}

async function jsonInput(path) {
  const stored = await readFile(path), bytes = path.endsWith('.gz') ? gunzipSync(stored) : stored;
  return {document: JSON.parse(bytes.toString('utf8')), sha256: digest(bytes)};
}
export async function writeNationwideReports({root = ROOT, check = false, inventoryPath, catalogPath, cityReportPath, pointsPath, outputPrefix} = {}) {
  const directory = join(root, 'data/neighborhoods');
  const paths = {inventory: inventoryPath ?? join(directory, 'nationwide-inventory.json'), catalog: catalogPath ?? join(directory, 'catalog.geojson.gz'),
    cityReport: cityReportPath ?? join(directory, 'report.json'), points: pointsPath ?? join(directory, 'sources/country-osm/named-nodes.geojson.gz')};
  const [inventory, catalog, cityReport, points] = await Promise.all(Object.values(paths).map(jsonInput));
  if (cityReport.document.inputFingerprints?.catalogSha256 && cityReport.document.inputFingerprints.catalogSha256 !== catalog.sha256) throw new Error('City report is stale for the supplied catalog; regenerate the city report first');
  const report = createNationwideReport(inventory.document, catalog.document, cityReport.document, points.document);
  report.inputFingerprints = Object.fromEntries(Object.keys(paths).map((key, index) => [key + 'Sha256', [inventory, catalog, cityReport, points][index].sha256]));
  const prefix = outputPrefix ?? join(directory, 'nationwide-report');
  for (const [extension, content] of [['json', JSON.stringify(report, null, 2) + '\n'], ['csv', nationwideCsv(report)], ['md', nationwideMarkdown(report)]]) {
    const path = prefix + '.' + extension;
    if (check) { if (await readFile(path, 'utf8') !== content) throw new Error(path + ' is stale; run node scripts/neighborhoods/nationwide-report.mjs'); }
    else await writeFile(path, content);
  }
  return report;
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const options = {}, args = process.argv.slice(2), parameters = {'--root': 'root', '--inventory': 'inventoryPath', '--catalog': 'catalogPath', '--city-report': 'cityReportPath', '--points': 'pointsPath', '--output-prefix': 'outputPrefix'};
  for (let index = 0; index < args.length; index++) {
    if (args[index] === '--check') options.check = true;
    else if (parameters[args[index]] && args[index + 1] && !args[index + 1].startsWith('--')) options[parameters[args[index]]] = resolve(args[++index]);
    else throw new Error('Usage: node scripts/neighborhoods/nationwide-report.mjs [--check] [--root PATH] [--inventory FILE] [--catalog FILE] [--city-report FILE] [--points FILE] [--output-prefix PATH]');
  }
  const report = await writeNationwideReports(options);
  console.log(`${options.check ? 'Verified' : 'Wrote'} ${report.summary.municipalities} municipality rows; ${report.summary.acceptedQuarterNameCount} accepted quarter names, ${report.summary.pointOnlyNameCount} point-only name gaps; national quarter totals remain unknown.`);
}
