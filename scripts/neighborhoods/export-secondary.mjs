import {createHash} from 'node:crypto';
import {readFile,writeFile} from 'node:fs/promises';
import {dirname,join,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {gunzipSync,gzipSync} from 'node:zlib';
import {loadManualSources} from './manual-sources.mjs';
import {validateGeometry} from './build.mjs';

const ROOT=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');

/** Research estimates are exported separately and are never admitted to the source-based catalogue. */
export function inferredCandidates(snapshots,municipalities){
  const known=new Set(municipalities),features=[],rejected=[];
  for(const snapshot of snapshots)for(const original of snapshot.document.features){
    const p={...original.properties,...snapshot.entry.propertyOverrides};
    const municipality=p.municipality??snapshot.entry.municipality;
    const validation=validateGeometry(original.geometry,original.bbox);
    if(!known.has(municipality)||!p.name||!validation.valid){
      rejected.push({dataset:snapshot.entry.id,id:original.id??null,name:p.name??null,
        municipality:known.has(municipality)?municipality:null,
        reviewPath:snapshot.entry.admissionReviewPath??snapshot.entry.reviewPath??null,
        reason:!known.has(municipality)?'unknown_municipality':!p.name?'missing_name':validation.reason});
      continue;
    }
    const id=`inferred:${snapshot.entry.id}:${original.id??features.length}`;
    features.push({...original,id,bbox:validation.bbox,properties:{...p,id,municipality,
      municipalityId:`city:${municipality}`,estimated:true,boundaryKind:'inferred_area',
      candidateBoundaryKind:p.candidateBoundaryKind??'local_area',canonicalNameIsNeighborhood:false,
      sourceIsOfficial:false,sourceIsHardBoundary:false,reviewStatus:'estimated_candidate_not_verified',
      geometryVerificationStatus:'inferred_not_verified',
      usableForAddressAssignment:false,
      source:{...p.source,provider:'manual-inference',collection:snapshot.entry.id,
        path:snapshot.path,sha256:snapshot.entry.sha256,
        method:p.method??snapshot.entry.method,evidenceUrls:p.evidenceUrls??snapshot.entry.evidenceUrls??[],
        sourceDocuments:p.sourceDocuments??snapshot.entry.sourceDocuments??[],
        license:p.source?.license??p.license??snapshot.entry.license??'See cited source and construction notes',
        rightsStatus:snapshot.entry.rightsStatus??null,reviewPath:snapshot.entry.reviewPath??null,
        ...(snapshot.entry.admissionReviewPath?{applicationAdmissionReviewPath:snapshot.entry.admissionReviewPath}:{}),
        geometrySha256:digest(JSON.stringify(original.geometry)),geometryUnmodified:true}}});
  }
  return {type:'FeatureCollection',status:'estimated_candidates_only',featureCount:features.length,
    completeNationalCoverage:false,usableForAddressAssignment:false,
    caveat:'Source-specific estimates with documented gaps or georeferencing uncertainty. They are not verified neighbourhood boundaries and do not close the official missing-boundary inventory.',
    rejected,features};
}

export function summarizeInferred(inferred){
  const groups=new Map();
  for(const feature of inferred.features){
    const p=feature.properties;
    if(!groups.has(p.municipality))groups.set(p.municipality,{municipality:p.municipality,
      geometryCount:0,neighbourhoodCandidateCount:0,planningCandidateCount:0,localAreaCandidateCount:0,names:new Set()});
    const row=groups.get(p.municipality);row.geometryCount++;row.names.add(p.name);
    if(p.candidateBoundaryKind==='neighbourhood')row.neighbourhoodCandidateCount++;
    else if(p.candidateBoundaryKind==='planning_unit')row.planningCandidateCount++;
    else row.localAreaCandidateCount++;
  }
  const cities=[...groups.values()].sort((a,b)=>a.municipality.localeCompare(b.municipality,'hu')).map(row=>{
    const names=[...row.names].sort((a,b)=>a.localeCompare(b,'hu'));
    return {...row,names,distinctSourceNameCount:names.length};
  });
  return {schemaVersion:1,status:'estimated_candidates_only',primaryCoverageCredit:false,
    inputInferredSha256:digest(JSON.stringify(inferred)+'\n'),geometryCount:inferred.features.length,
    municipalityCount:cities.length,rejectedSourceRecordCount:inferred.rejected?.length??0,
    rejectedSourceRecords:inferred.rejected??[],
    caveat:'Counts are estimated geometry features, not polygon components or additional verified quarters. Historical alternatives and broader groups remain separate from primary coverage and never close known source gaps.',cities};
}

export async function writeSecondary({root=ROOT,check=false}={}){
  const directory=join(root,'data/neighborhoods');
  const catalogText=gunzipSync(await readFile(join(directory,'catalog.geojson.gz'))).toString('utf8');
  const catalog=JSON.parse(catalogText);
  const municipalities=JSON.parse(await readFile(join(root,'dist/data/settlements.json'),'utf8')).settlements;
  const snapshots=await loadManualSources(root,'inferred-candidate-registry.json');
  const planning={type:'FeatureCollection',status:'planning_units_not_fine_neighborhoods',
    completeNationalCoverage:false,usableForAddressAssignment:false,
    caveat:'Broader planning or regulatory partitions; these are kept separate from individual neighbourhood coverage.',
    features:catalog.features.filter(f=>f.properties.boundaryKind==='planning_unit')};
  planning.featureCount=planning.features.length;
  planning.inputCatalogSha256=digest(catalogText);
  const inferred=inferredCandidates(snapshots,municipalities);
  for(const [name,value] of [['planning-units',planning],['estimated-candidates',inferred]]){
    const content=JSON.stringify(value)+'\n';
    for(const compressed of [false,true]){
      const file=join(directory,`${name}.geojson${compressed?'.gz':''}`);
      if(check){const bytes=await readFile(file);if((compressed?gunzipSync(bytes).toString('utf8'):bytes.toString('utf8'))!==content)throw new Error('Stale secondary export: '+file);}
      else await writeFile(file,compressed?gzipSync(content,{level:9}):content);
    }
  }
  const inferredSummary=summarizeInferred(inferred);
  const rows=[['municipality','estimated_geometry_count','distinct_source_name_count','neighbourhood_candidate_count','planning_candidate_count','local_area_candidate_count','source_names'],
    ...inferredSummary.cities.map(row=>[row.municipality,row.geometryCount,row.distinctSourceNameCount,
      row.neighbourhoodCandidateCount,row.planningCandidateCount,row.localAreaCandidateCount,row.names.join(' | ')])];
  const csv=rows.map(row=>row.map(value=>'"'+String(value).replaceAll('"','""')+'"').join(',')).join('\n')+'\n';
  for(const [name,content] of [['estimated-report.json',JSON.stringify(inferredSummary,null,2)+'\n'],['estimated-report.csv',csv]]){
    const file=join(directory,name);
    if(check){if(await readFile(file,'utf8')!==content)throw new Error('Stale estimated summary: '+file);}
    else await writeFile(file,content);
  }
  return {planning,inferred,inferredSummary};
}

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  if(process.argv.slice(2).some(arg=>arg!=='--check'))throw new Error('Usage: node scripts/neighborhoods/export-secondary.mjs [--check]');
  const result=await writeSecondary({check:process.argv.includes('--check')});
  console.log(`${result.planning.featureCount} planning units and ${result.inferred.featureCount} inferred candidates in separate layers; primary neighbourhood export unchanged.`);
}
