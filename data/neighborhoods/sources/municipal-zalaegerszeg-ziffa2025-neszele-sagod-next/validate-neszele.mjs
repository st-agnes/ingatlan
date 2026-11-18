import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
import {validateGeometry} from '../../../../scripts/neighborhoods/build.mjs';
const P=dirname(fileURLToPath(import.meta.url));
const rows=[];
for(const file of ['neszele-inferred-import.geojson','neszele-placement-alternative.geojson']){
 const d=JSON.parse(await readFile(join(P,file),'utf8'));
 for(const f of d.features){
  const v=validateGeometry(f.geometry);
  rows.push({file,id:f.id,name:f.properties.name,estimated:f.properties.estimated,...v});
  if(!v.valid)throw new Error(`${file}: ${v.reason}`);
 }
}
await writeFile(join(P,'strict-validator-review.json'),JSON.stringify({validator:'scripts/neighborhoods/build.mjs validateGeometry, without repair',results:rows},null,2)+'\n');
console.log(JSON.stringify(rows));
