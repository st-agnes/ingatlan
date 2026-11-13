import {createHash} from 'node:crypto';
import {readFile,writeFile} from 'node:fs/promises';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {gunzipSync,gzipSync} from 'node:zlib';
import {createNameEvidenceIndex,findNameEvidence,normalizeName} from './report.mjs';

const ROOT=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const key=(municipality,name)=>normalizeName(municipality)+'\u0000'+normalizeName(name);
const sourceRank=feature=>feature.properties.source?.provider==='openstreetmap'
  ? feature.properties.source.historical===true?1:0:2;
const featureName=feature=>feature.properties.canonicalName ?? feature.properties.nameAudit?.proposedHungarianName ?? feature.properties.name;

/** Select existing features only. No geometry is created, merged, buffered, simplified or changed. */
export function createNeighborhoodExport(catalog,report,{nameAudit=null}={}){
  if(catalog?.type!=='FeatureCollection' || !Array.isArray(catalog.features))throw new Error('Expected a GeoJSON FeatureCollection');
  if(!Array.isArray(report?.cities))throw new Error('Expected a city report with accepted neighborhood names');
  const desired=new Map();
  for(const city of report.cities)for(const name of city.acceptedNeighbourhoodNames ?? []){
    const identity=key(city.municipality,name);
    if(desired.has(identity))throw new Error('Duplicate accepted city/name in report: '+city.municipality+' / '+name);
    desired.set(identity,{municipality:city.municipality,name});
  }
  if(report.summary?.acceptedNeighbourhoodNameCount!==undefined && report.summary.acceptedNeighbourhoodNameCount!==desired.size){
    throw new Error('Accepted-name summary does not match the report inventory');
  }
  const evidenceIndex=createNameEvidenceIndex(nameAudit);
  const candidates=[...catalog.features].sort((a,b)=>sourceRank(a)-sourceRank(b)
    || String(b.properties.source?.snapshotDate ?? '').localeCompare(String(a.properties.source?.snapshotDate ?? ''))
    || String(a.properties.id ?? a.id).localeCompare(String(b.properties.id ?? b.id)));
  const selected=new Map();
  for(const feature of candidates){
    const p=feature.properties ?? {};
    if(p.boundaryKind==='district')continue;
    const identity=key(p.municipality,featureName(feature));
    if(!desired.has(identity) || selected.has(identity))continue;
    if(!['Polygon','MultiPolygon'].includes(feature.geometry?.type))throw new Error('Accepted neighborhood has no real polygon: '+p.name);
    const accepted=desired.get(identity);
    const properties={...p,name:accepted.name,municipality:accepted.municipality,
      sourceName:p.sourceName ?? p.name,
      exportSelection:'accepted_neighbourhood_name',
      nameEvidence:findNameEvidence({municipality:accepted.municipality,name:accepted.name},evidenceIndex)};
    if(p.name!==accepted.name)properties.originalCatalogName=p.name;
    // Geometry and bbox remain the exact original values, including holes and separate polygon parts.
    selected.set(identity,{...feature,properties});
  }
  const missing=[...desired].filter(([identity])=>!selected.has(identity)).map(([,row])=>row.municipality+' / '+row.name);
  if(missing.length)throw new Error('Accepted names have no matching source geometry: '+missing.join(', '));
  const features=[...desired.keys()].sort().map(identity=>selected.get(identity));
  if(new Set(features.map(feature=>feature.properties.id ?? feature.id)).size!==features.length)throw new Error('Duplicate source feature selected for different neighborhood names');
  return {type:'FeatureCollection',name:'Hungarian neighborhood boundary collection',schemaVersion:1,
    status:'partial_collection',coordinateReferenceSystem:'EPSG:4326',featureCount:features.length,
    countingPolicy:'One existing source feature per normalized municipality and accepted neighborhood name; district and broader-area-only entries are excluded by the report.',
    geometryProcessing:'Selection only. All geometry coordinates, holes, polygon parts and bounding boxes are preserved from the candidate catalogue.',
    verificationPolicy:'Existing source, name-audit and geometry-verification fields are retained. Cross-source name evidence refers to the exact canonical municipality/name only; it does not verify geometry or present-day boundary accuracy.',
    completeNationalCoverage:false,usableForAddressAssignment:false,
    attribution:'See each feature source for original attribution, license, dates and processing history. Includes © OpenStreetMap contributors (ODbL-1.0) and preserved WOF source credits.',features};
}

export async function writeExport({root=ROOT,check=false}={}){
  const directory=join(root,'data/neighborhoods');
  let catalogText;
  try{catalogText=gunzipSync(await readFile(join(directory,'catalog.geojson.gz'))).toString('utf8');}
  catch(error){if(error.code!=='ENOENT')throw error;catalogText=await readFile(join(directory,'catalog.geojson'),'utf8');}
  const reportText=await readFile(join(directory,'report.json'),'utf8'),report=JSON.parse(reportText);
  if(report.inputFingerprints?.catalogSha256!==digest(catalogText))throw new Error('City report is stale; run node scripts/neighborhoods/report.mjs first');
  const coverageText=await readFile(join(directory,'coverage.json'),'utf8');
  if(report.inputFingerprints?.coverageSha256!==digest(coverageText))throw new Error('Coverage changed; regenerate the city report first');
  let referencesText=null;
  try{referencesText=await readFile(join(directory,'reference-inventories.json'),'utf8');}catch(error){if(error.code!=='ENOENT')throw error;}
  if(report.inputFingerprints?.referencesSha256!==(referencesText?digest(referencesText):null))throw new Error('Reference inventories changed; regenerate the city report first');
  let nameAuditText=null;
  try{nameAuditText=await readFile(join(directory,'name-audit.json'),'utf8');}catch(error){if(error.code!=='ENOENT')throw error;}
  if(report.inputFingerprints?.nameAuditSha256!==(nameAuditText?digest(nameAuditText):null))throw new Error('Name audit changed; regenerate the city report first');
  const collection=createNeighborhoodExport(JSON.parse(catalogText),report,{nameAudit:nameAuditText?JSON.parse(nameAuditText):null});
  collection.inputFingerprints={catalogSha256:digest(catalogText),reportSha256:digest(reportText),nameAuditSha256:nameAuditText?digest(nameAuditText):null};
  const plain=JSON.stringify(collection)+'\n',compressed=gzipSync(plain,{level:9});
  for(const [name,bytes] of [['neighborhoods.geojson',Buffer.from(plain)],['neighborhoods.geojson.gz',compressed]]){
    const file=join(directory,name);
    if(check){if(!(await readFile(file)).equals(bytes))throw new Error(name+' is stale; run node scripts/neighborhoods/export.mjs');}
    else await writeFile(file,bytes);
  }
  return collection;
}

if(process.argv[1] && import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  const args=process.argv.slice(2);
  if(args.some(arg=>arg!=='--check'))throw new Error('Usage: node scripts/neighborhoods/export.mjs [--check]');
  const collection=await writeExport({check:args.includes('--check')});
  console.log((args.includes('--check')?'Verified':'Wrote')+' unified neighborhood export: '+collection.featureCount+' accepted city/name boundaries.');
}
