import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname, join} from 'node:path';
import {validateGeometry} from '../../../../scripts/neighborhoods/build.mjs';

const directory = dirname(fileURLToPath(import.meta.url));
const results = [];
for (const file of ['szeged-four-inferred-import.geojson', 'szeged-four-placement-alternative.geojson']) {
  const collection = JSON.parse(await readFile(join(directory, file), 'utf8'));
  for (const feature of collection.features) {
    const result = validateGeometry(feature.geometry);
    results.push({file, sourceUnitNumber: feature.properties.sourceUnitNumber, name: feature.properties.name, ...result});
    if (!result.valid) throw new Error(`${file} unit${feature.properties.sourceUnitNumber}: ${result.reason}`);
  }
}
await writeFile(join(directory, 'henits-four-world-strict-review-working.json'), JSON.stringify({
  schemaVersion: 1,
  status: 'all8_main_and_alternative_world_geometries_pass_unchanged_repository_validator_without_repair',
  validator: 'scripts/neighborhoods/build.mjs validateGeometry',
  results,
  geometryModified: false,
  globalRegistryModified: false
}, null, 2) + '\n');
console.log(JSON.stringify({worldGeometriesChecked: results.length, valid: true}));
