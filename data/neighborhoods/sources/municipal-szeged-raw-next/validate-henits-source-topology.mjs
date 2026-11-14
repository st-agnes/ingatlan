import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname, join} from 'node:path';
import {validateGeometry} from '../../../../scripts/neighborhoods/build.mjs';

const directory = dirname(fileURLToPath(import.meta.url));
const rows = [];
for (const cutoff of [50, 60, 70]) {
  const file = `henits-five-black${cutoff}-source-pixels-working.geojson`;
  const collection = JSON.parse(await readFile(join(directory, file), 'utf8'));
  for (const feature of collection.features) {
    // This is an in-memory topological scale change, not a geographic placement.
    // No normalized coordinates are persisted or presented as world geometry.
    const normalized = {
      type: feature.geometry.type,
      coordinates: feature.geometry.coordinates.map(ring => ring.map(([x, y]) => [x / 100, y / 100]))
    };
    const rawResult = validateGeometry(feature.geometry);
    const normalizedResult = validateGeometry(normalized);
    rows.push({file, sourceUnitNumber: feature.properties.number,
      rawPixelSpaceResult: rawResult,
      topologyOnlyNormalizedResult: normalizedResult});
    if (!normalizedResult.valid) throw new Error(`${file} unit${feature.properties.number}: ${normalizedResult.reason}`);
  }
}
const result = {
  schemaVersion: 1,
  status: 'all12_closed_source_rings_pass_topology_only_normalized_check; world_admission_pending',
  validator: 'scripts/neighborhoods/build.mjs validateGeometry, unmodified',
  normalizationMeaning: 'Divide native source-pixel coordinates by100 in an ephemeral validation copy only, to satisfy validator numeric-domain gates while checking identical topology. No world coordinates or georeferencing are produced.',
  rawPixelCoordinateFailureMeaning: 'Expected invalid_coordinate because native pixels exceed WGS84 bounds; not a geographic import attempt.',
  results: rows,
  worldGeometryProduced: false,
  sourceGeometryModified: false,
  globalRegistryModified: false
};
await writeFile(join(directory, 'henits-five-strict-topology-working.json'), JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify({status: result.status, checkedRings: rows.length}));
