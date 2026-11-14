import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {validateGeometry} from '../../../../scripts/neighborhoods/build.mjs';

const files = process.argv.slice(2);
const records = [];
for (const file of files) {
  const source = JSON.parse(await readFile(fileURLToPath(new URL(file, import.meta.url)), 'utf8'));
  for (const feature of source.features) {
    records.push({file, name: feature.properties.name,
      sourceUnitNumber: feature.properties.sourceUnitNumber,
      ...validateGeometry(feature.geometry, feature.bbox)});
  }
}
process.stdout.write(JSON.stringify({validator: 'scripts/neighborhoods/build.mjs:validateGeometry', records}));
