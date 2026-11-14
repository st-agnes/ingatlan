import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
import {validateGeometry} from '../../../../scripts/neighborhoods/build.mjs';
const P=dirname(fileURLToPath(import.meta.url));
const rows=[];
for(const file of ['szeged-four-inferred-import.geojson','szeged-four-placement-alternative.geojson']){
 const d=JSON.parse(await readFile(join(P,file),'utf8'));
 if(d.features.length!==4)throw new Error('Expected four source contours per placement');
 for(const f of d.features){const result=validateGeometry(f.geometry);rows.push({file,id:f.id,name:f.properties.name,estimated:f.properties.estimated,...result});if(!result.valid)throw new Error(`${file}: ${result.reason}`);}
}
await writeFile(join(P,'strict-world-validator-review.json'),JSON.stringify({validator:'scripts/neighborhoods/build.mjs validateGeometry, no repair',results:rows},null,2)+'\n');
console.log(JSON.stringify(rows));
