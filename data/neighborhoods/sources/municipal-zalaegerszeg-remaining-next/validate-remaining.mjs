import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
import {validateGeometry} from '../../../../scripts/neighborhoods/build.mjs';
const P=dirname(fileURLToPath(import.meta.url));
const rows=[];const passed={type:'FeatureCollection',features:[]};const held={type:'FeatureCollection',features:[]};
for (const file of ['remaining-literal-world.geojson','remaining-manual-world.geojson','remaining-iparterulet-one-pixel-inferred-world.geojson']) {
 const d=JSON.parse(await readFile(join(P,file),'utf8'));
 for (const f of d.features) {
  const v=validateGeometry(f.geometry); rows.push({name:f.properties.name,file,estimated:f.properties.estimated,...v});
  f.properties.localStrictImportStatus=v.valid?'passes_existing_js_geometry_validator':'quarantined';
  f.properties.localStrictQuarantineReason=v.reason??null;
  (v.valid?passed:held).features.push(f);
 }
}
await writeFile(join(P,'remaining-strict-validator-review.json'),JSON.stringify({validator:'scripts/neighborhoods/build.mjs validateGeometry, called without repair',results:rows},null,2)+'\n');
await writeFile(join(P,'remaining-validator-passing.geojson'),JSON.stringify(passed,null,2)+'\n');
await writeFile(join(P,'remaining-validator-quarantine.geojson'),JSON.stringify(held,null,2)+'\n');
console.log(JSON.stringify(rows,null,2));
