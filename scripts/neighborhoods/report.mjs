import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {gunzipSync} from 'node:zlib';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
export const normalizeName = value => String(value ?? '').normalize('NFD').replace(/\p{M}/gu, '')
  .toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '');
const order = (a,b) => normalizeName(a) < normalizeName(b) ? -1 : normalizeName(a) > normalizeName(b) ? 1 : a < b ? -1 : a > b ? 1 : 0;
const uniqueNames = values => [...new Map([...values].sort(order).map(name => [normalizeName(name), name])).values()].sort(order);
const fingerprint = value => createHash('sha256').update(value).digest('hex');
const cityOf = item => item?.municipality ?? item?.city ?? null;
const sourceOf = feature => feature.properties.source?.provider ?? 'unknown';
const confirmedStates = new Set(['confirmed', 'confirmed_current', 'current_name_confirmed', 'verified', 'verified_current', 'source_confirmed']);

function auditRows(audit) {
  if (!audit) return [];
  return Array.isArray(audit) ? audit : audit.records ?? audit.items ?? audit.reviews ?? [];
}

const canonicalNameKey=(municipality,name)=>normalizeName(municipality)+'\u0000'+normalizeName(name);
export function createNameEvidenceIndex(audit) {
  const index=new Map();
  for(const row of auditRows(audit)){
    if(row.canonicalNameSupported!==true || !row.actualMunicipality || !row.proposedHungarianName)continue;
    const key=canonicalNameKey(row.actualMunicipality,row.proposedHungarianName);
    const evidence=index.get(key) ?? {canonicalName:row.proposedHungarianName,municipality:row.actualMunicipality,
      scope:'name_only',geometryVerified:false,auditRecordIds:[],evidenceUrls:[]};
    if(row.id && !evidence.auditRecordIds.includes(row.id))evidence.auditRecordIds.push(row.id);
    for(const url of row.evidenceUrls ?? [])if(!evidence.evidenceUrls.includes(url))evidence.evidenceUrls.push(url);
    index.set(key,evidence);
  }
  return index;
}
export function findNameEvidence(properties,index){return index.get(canonicalNameKey(properties.municipality,properties.name)) ?? null;}

function confirmedName(feature, auditById) {
  const p = feature.properties, record = p.nameAudit ?? auditById.get(p.id ?? feature.id);
  const status = p.nameValidation?.status ?? p.nameValidationStatus ?? record?.validationStatus ?? record?.status;
  return (confirmedStates.has(status) || record?.canonicalNameSupported === true || p.canonicalNameSupported === true)
    && record?.exclude !== true && record?.rejected !== true;
}

function acceptedName(feature, auditById) {
  const p=feature.properties, record=p.nameAudit ?? auditById.get(p.id ?? feature.id);
  if(record?.exclude === true || record?.rejected === true) return null;
  if(record?.actualMunicipality && record.actualMunicipality!==p.municipality) return null;
  const explicitlyConfirmed=confirmedName(feature,auditById);
  // Current and historical OSM source names are kept as mapped names, not as independently verified boundaries.
  const mappedOsmName=sourceOf(feature)==='openstreetmap' && !record;
  if(!explicitlyConfirmed && !mappedOsmName) return null;
  const name=record?.proposedHungarianName ?? p.canonicalName ?? p.name;
  return {name,isNeighbourhood:record?.canonicalNameIsNeighborhood ?? p.canonicalNameIsNeighborhood ?? (p.boundaryKind!=='district'),
    basis:explicitlyConfirmed?'name_audit':'osm_source_name'};
}

function sourceNameWithoutGeometry(records, represented) {
  const groups = new Map();
  for (const row of records) {
    if (row.reason !== 'not_polygon' || !['Point','MultiPoint'].includes(row.geometryType)) continue;
    if (typeof row.name !== 'string' || !row.name.trim()) continue;
    const key = normalizeName(row.name);
    if (represented.has(key)) continue;
    const entry = groups.get(key) ?? {name: row.name, sourceIds: [], sourceUrls: [], sourceKind: 'name_or_point_only', currentNameConfirmed: false};
    if (row.id && !entry.sourceIds.includes(row.id)) entry.sourceIds.push(row.id);
    if (row.source?.url && !entry.sourceUrls.includes(row.source.url)) entry.sourceUrls.push(row.source.url);
    groups.set(key, entry);
  }
  return [...groups.values()].sort((a,b)=>order(a.name,b.name));
}

/** Counts describe only known source records. No missing-source city becomes "complete". */
export function createReport(catalog, coverage, {references = {inventories: []}, nameAudit = null} = {}) {
  if (catalog?.type !== 'FeatureCollection' || !Array.isArray(catalog.features)) throw new Error('Expected a GeoJSON FeatureCollection');
  for (const f of catalog.features) if (!['Polygon','MultiPolygon'].includes(f.geometry?.type)) throw new Error('Catalogue contains a non-area geometry');
  const audit = auditRows(nameAudit);
  const auditById = new Map(audit.map(row => [row.id ?? row.catalogId ?? row.originalId, row]));
  const nameEvidenceIndex=createNameEvidenceIndex(nameAudit);
  const inventories = references.inventories ?? [];
  const features = catalog.features;
  const sourceRows = [...(coverage.municipalities ?? []), ...(coverage.targetCities ?? [])];
  const names = new Set([
    ...features.map(f=>cityOf(f.properties)), ...sourceRows.map(cityOf),
    ...(coverage.excluded ?? []).map(cityOf), ...inventories.map(cityOf)
  ].filter(name=>typeof name==='string' && name));
  const cities = [...names].sort(order).map(municipality => {
    const areas = features.filter(f=>cityOf(f.properties)===municipality);
    const quarters = areas.filter(f=>f.properties.boundaryKind !== 'district');
    const districts = areas.filter(f=>f.properties.boundaryKind === 'district');
    const neighborhoodNames = uniqueNames(quarters.map(f=>f.properties.sourceName ?? f.properties.name));
    const accepted=quarters.map(f=>acceptedName(f,auditById)).filter(Boolean);
    const acceptedCurrentAreaNames=uniqueNames(accepted.map(row=>row.name));
    const acceptedNeighbourhoodNames=uniqueNames(accepted.filter(row=>row.isNeighbourhood).map(row=>row.name));
    const represented = new Set(acceptedNeighbourhoodNames.map(normalizeName));
    const excluded = (coverage.excluded ?? []).filter(row=>cityOf(row)===municipality);
    const sourceRepresented = new Set([...neighborhoodNames,...quarters.map(f=>f.properties.name),...acceptedCurrentAreaNames].map(normalizeName));
    const knownNamesWithoutGeometry = sourceNameWithoutGeometry(excluded,sourceRepresented);
    const query = sourceRows.find(row=>cityOf(row)===municipality && row.osmQuery?.status && row.osmQuery.status!=='not_requested')?.osmQuery ?? {status:'not_requested'};
    const osm = quarters.filter(f=>sourceOf(f)==='openstreetmap');
    const currentOsm = osm.filter(f=>f.properties.source?.historical!==true && !f.properties.source?.snapshotDate);
    const observedQueryResult = query.status==='downloaded'
      ? (currentOsm.length ? 'downloaded_with_boundaries' : 'downloaded_without_boundaries')
      : query.status==='failed' ? 'query_failed' : query.status==='not_requested' ? 'not_requested' : 'other';
    const referenceComparisons = inventories.filter(row=>cityOf(row)===municipality).map(reference => {
      const expected = uniqueNames(reference.names ?? []);
      const equivalences=reference.nameEquivalences ?? [];
      for(const row of equivalences)if(!row.referenceName || !row.equivalentName || !row.reason || !row.evidenceUrls?.length){
        throw new Error('Reference name equivalences require explicit names, reason and evidence URLs');
      }
      const equivalencesFor=name=>equivalences.filter(row=>normalizeName(row.referenceName)===normalizeName(name));
      const matches=name=>represented.has(normalizeName(name)) || equivalencesFor(name).some(row=>represented.has(normalizeName(row.equivalentName)));
      const matched = expected.filter(matches);
      const missing = expected.filter(name=>!matches(name));
      const nameEquivalencesUsed=equivalences.filter(row=>expected.some(name=>normalizeName(name)===normalizeName(row.referenceName))
        && !represented.has(normalizeName(row.referenceName)) && represented.has(normalizeName(row.equivalentName)));
      const additionalMissingIdentities=reference.additionalMissingIdentities ?? [];
      return {title:reference.title,referencePeriod:reference.referencePeriod,sourceUrl:reference.sourceUrl,
        printedPage:reference.printedPage ?? null,completeForReferencePeriod:reference.completeForReferencePeriod===true,
        currentCompletenessVerified:reference.currentCompletenessVerified===true,
        transcriptionNote:reference.transcriptionNote ?? null,
        referenceNameCount:expected.length,matchedNameCount:matched.length,missingNameCount:missing.length,
        matchedNames:matched,missingNames:missing,nameEquivalencesUsed,
        referenceIdentityCount:reference.distinctNeighborhoodIdentityCount ?? null,
        additionalMissingIdentityCount:additionalMissingIdentities.length,additionalMissingIdentities,
        totalKnownMissingIdentityCount:reference.missingNamesEachRepresentOneIdentity===true
          ?missing.length+additionalMissingIdentities.length:null,
        countingNotes:reference.countingNotes ?? [],referenceInventoryFile:reference.referenceInventoryFile ?? null};
    });
    const providerCounts = {};
    for(const f of quarters) providerCounts[sourceOf(f)] = (providerCounts[sourceOf(f)] ?? 0) + 1;
    const nameValidationStatusCounts={},excludedSourceReasonCounts={};
    for(const f of quarters){
      const p=f.properties,record=p.nameAudit ?? auditById.get(p.id ?? f.id);
      const status=p.nameValidation?.status ?? p.nameValidationStatus ?? record?.validationStatus ?? record?.status ?? 'not_individually_checked';
      nameValidationStatusCounts[status]=(nameValidationStatusCounts[status] ?? 0)+1;
    }
    for(const row of excluded)excludedSourceReasonCounts[row.reason ?? 'unknown']=(excludedSourceReasonCounts[row.reason ?? 'unknown'] ?? 0)+1;
    const hasNameEvidence=f=>confirmedName(f,auditById) || Boolean(findNameEvidence(f.properties,nameEvidenceIndex));
    const nameConfirmedCount = uniqueNames(quarters.filter(hasNameEvidence).map(f=>acceptedName(f,auditById)?.name).filter(Boolean)).length;
    const unverifiedSourceNames=uniqueNames(quarters.filter(f=>!acceptedName(f,auditById)).map(f=>f.properties.sourceName ?? f.properties.name));
    return {municipality,isTargetCity:(coverage.targetCities ?? []).some(row=>cityOf(row)===municipality),
      neighbourhoodGeometryCount:quarters.length,uniqueSourceNameCount:neighborhoodNames.length,
      acceptedNeighbourhoodNameCount:acceptedNeighbourhoodNames.length,acceptedNeighbourhoodNames,
      acceptedCurrentAreaNameCount:acceptedCurrentAreaNames.length,acceptedCurrentAreaNames,
      districtFallbackGeometryCount:districts.length,currentOsmGeometryCount:currentOsm.length,
      osmGeometryCount:osm.length,historicalOsmGeometryCount:osm.length-currentOsm.length,
      legacyOrOtherGeometryCount:quarters.length-osm.length,nameConfirmedUniqueCount:nameConfirmedCount,
      nameConfirmationUnrecordedCount:uniqueNames(quarters.filter(f=>!hasNameEvidence(f)).map(f=>f.properties.sourceName ?? f.properties.name)).length,
      unverifiedSourceNameCount:unverifiedSourceNames.length,unverifiedSourceNames,
      providerCounts,nameValidationStatusCounts,excludedSourceReasonCounts,neighborhoodNames,knownNamesWithoutGeometryCount:knownNamesWithoutGeometry.length,
      knownNamesWithoutGeometry,referenceComparisons,
      completeCoverage:false,totalCurrentNeighbourhoods:null,totalMissingCurrentNeighbourhoods:null,
      osmQuery:{...query,observedResult:observedQueryResult},
      caveat:'Counts cover collected source geometries and source names only; current complete city coverage is not established.'};
  });
  const total = key => cities.reduce((sum,row)=>sum+row[key],0);
  return {schemaVersion:1,status:'partial_collection',countingPolicy:{
      geometry:'Each Polygon or MultiPolygon feature is one geometry; separate parts of a MultiPolygon are not additional neighborhoods.',
      uniqueNames:'Names deduplicate by city after case, accent, punctuation and whitespace normalization. This does not establish that every source name is a current distinct neighborhood.',
      acceptedNames:'The main neighborhood count uses mapped OSM neighborhood names or explicitly supported canonical names in the name audit. Historical aliases deduplicate to the canonical name; district/large-area names are excluded from that main count. Name acceptance does not verify the boundary.',
      missing:'Point-only names without a matching collected polygon are known source gaps. Other missing names are listed only against an explicitly cited reference inventory.',
      query:'Failed, successful-empty and unrequested lookups remain separate. A failed lookup is not evidence that boundaries do not exist.',
      verification:'Current OSM origin and recorded human name confirmation are separate counts. Exact normalized canonical city/name matches may reuse existing name-audit evidence across data sources; this confirms the name only, not the feature classification or geometry. No Google verification is inferred from source age or an unvisited search link.'},
    summary:{settlementsInReport:cities.length,settlementsWithNeighbourhoodGeometry:cities.filter(row=>row.neighbourhoodGeometryCount>0).length,
      settlementsWithAcceptedNeighbourhoodNames:cities.filter(row=>row.acceptedNeighbourhoodNameCount>0).length,
      targetCities:(coverage.targetCities ?? []).length,neighbourhoodGeometryCount:total('neighbourhoodGeometryCount'),
      uniqueSourceNamesAcrossSettlements:total('uniqueSourceNameCount'),districtFallbackGeometryCount:total('districtFallbackGeometryCount'),
      acceptedNeighbourhoodNameCount:total('acceptedNeighbourhoodNameCount'),acceptedCurrentAreaNameCount:total('acceptedCurrentAreaNameCount'),
      unverifiedSourceNameCount:total('unverifiedSourceNameCount'),osmGeometryCount:total('osmGeometryCount'),historicalOsmGeometryCount:total('historicalOsmGeometryCount'),
      currentOsmGeometryCount:total('currentOsmGeometryCount'),legacyOrOtherGeometryCount:total('legacyOrOtherGeometryCount'),
      nameConfirmedUniqueCount:total('nameConfirmedUniqueCount'),knownNamesWithoutGeometryCount:total('knownNamesWithoutGeometryCount'),
      failedQueries:cities.filter(row=>row.osmQuery.observedResult==='query_failed').length,
      successfulEmptyQueries:cities.filter(row=>row.osmQuery.observedResult==='downloaded_without_boundaries').length,
      unrequestedCities:cities.filter(row=>row.osmQuery.observedResult==='not_requested').length,
      totalMissingCurrentNeighbourhoods:null,completeNationalCoverage:false},
    cities,unassignedSourceRecords:(coverage.excluded ?? []).filter(row=>!cityOf(row)).map(row=>({id:row.id,name:row.name,
      geometryType:row.geometryType,reason:row.reason,sourceUrl:row.source?.url ?? null})),
    referenceSources:inventories.map(row=>({municipality:row.municipality,title:row.title,referencePeriod:row.referencePeriod,
      sourceUrl:row.sourceUrl,printedPage:row.printedPage ?? null})),
    audit:{present:Boolean(nameAudit),recordCount:audit.length}};
}

const csvCell = value => {const s=String(value ?? '');return /[;"\r\n]/.test(s)?`"${s.replaceAll('"','""')}"`:s;};
export function csvReport(report) {
  const rows=[['Település','Elfogadott városrésznevek','Összes elfogadott területi név','Határgeometriák','Egyedi forrásnevek','Friss OSM-geometriák','Korábbi OSM-geometriák','Régebbi/egyéb geometriák','Névként megerősített','Nem elfogadott forrásnevek','Ismert határ nélküli nevek','Referencialista hiányzó nevei','További azonos nevű hiányzó területek','Ismert hiányzó területek összesen','Lekérdezési állapot','Lekérdezési hiba']];
  for(const row of report.cities) rows.push([row.municipality,row.acceptedNeighbourhoodNameCount,row.acceptedCurrentAreaNameCount,row.neighbourhoodGeometryCount,row.uniqueSourceNameCount,
    row.currentOsmGeometryCount,row.historicalOsmGeometryCount,row.legacyOrOtherGeometryCount,row.nameConfirmedUniqueCount,row.unverifiedSourceNameCount,row.knownNamesWithoutGeometryCount,
    row.referenceComparisons.length?row.referenceComparisons.map(x=>x.missingNameCount).join(' / '):'',
    row.referenceComparisons.length?row.referenceComparisons.map(x=>x.additionalMissingIdentityCount).join(' / '):'',
    row.referenceComparisons.length?row.referenceComparisons.map(x=>x.totalKnownMissingIdentityCount ?? '').join(' / '):'',
    row.osmQuery.observedResult,row.osmQuery.reason ?? '']);
  return '\uFEFF'+rows.map(row=>row.map(csvCell).join(';')).join('\r\n')+'\r\n';
}
const md = value => String(value).replaceAll('|','\\|').replaceAll('\n',' ');
const queryLabels = {downloaded_with_boundaries:'Sikeres, talált határt',downloaded_without_boundaries:'Sikeres, nem talált határt',query_failed:'Sikertelen',not_requested:'Nem vizsgáltuk',other:'Egyéb'};
export function markdownReport(report) {
  const s=report.summary;
  const lines=['# Összegyűjtött városrészhatárok és ismert hiányok','',
    `${s.acceptedNeighbourhoodNameCount} különböző elfogadott városrésznévhez tartozik határ, ${s.settlementsWithAcceptedNeighbourhoodNames} településen. A katalógus összesen ${s.neighbourhoodGeometryCount} határgeometriát és ${s.uniqueSourceNamesAcrossSettlements} eredeti forrásnevet tartalmaz. Ebből ${s.currentOsmGeometryCount} geometria friss OSM-lekérésből, ${s.historicalOsmGeometryCount} korábbi OSM-adatkivonatból származik.`,
    '', 'A fő névszám az OSM-ben városrészként jelölt neveket és a külön névauditban támogatott mai városrészneveket számolja, városonként összevonva az azonos neveket és történelmi változatokat. A kerület/nagyterületi neveket nem adja hozzá. Ez nem teljes városi lefedettség és nem határvonal-ellenőrzés. A névként megerősített oszlop kizárólag rögzített névauditot számol; a nullás érték nem jelenti, hogy a nevek megszűntek.',
    '', '| Település | Elfogadott városrésznevek | Geometriák | Egyedi forrásnevek | Friss OSM | Korábbi OSM | Névként megerősített | Ismert név határ nélkül | Lekérés |',
    '|---|---:|---:|---:|---:|---:|---:|---:|---|'];
  for(const row of report.cities) lines.push(`| ${md(row.municipality)} | ${row.acceptedNeighbourhoodNameCount} | ${row.neighbourhoodGeometryCount} | ${row.uniqueSourceNameCount} | ${row.currentOsmGeometryCount} | ${row.historicalOsmGeometryCount} | ${row.nameConfirmedUniqueCount} | ${row.knownNamesWithoutGeometryCount} | ${queryLabels[row.osmQuery.observedResult]}${row.osmQuery.reason?' ('+md(row.osmQuery.reason)+')':''} |`);
  if(s.unverifiedSourceNameCount)lines.push('',`${s.unverifiedSourceNameCount} további forrásnévhez van geometria, de a név nincs elfogadott mai városrészként besorolva; ezeket a fő névszám nem tartalmazza. A névlisták és az összes elfogadott területi név (a kerület/nagyterületi nevekkel) a JSON-jelentésben szerepelnek.`);
  lines.push('', '## Hiányok a név szerint ismert referencialistákhoz képest','',
    'Ezek az összehasonlítások a megjelölt forrás időállapotára vonatkoznak. Más városoknál teljes referencialista nélkül nem adunk kitalált összes vagy hiányzó darabszámot.');
  for(const row of report.cities) for(const reference of row.referenceComparisons) {
    lines.push('', `### ${md(row.municipality)}`, '',
      `[${md(reference.title)}](${reference.sourceUrl}), ${md(reference.referencePeriod)}${reference.printedPage?', nyomtatott '+reference.printedPage+'. oldal':''}.`,
      '', `A lista ${reference.referenceNameCount} nevéből ${reference.matchedNameCount} névhez van összegyűjtött határ; ${reference.missingNameCount} névhez még nincs:`,
      '', reference.missingNames.map(name=>md(name)).join(', ')+'.');
    if(reference.nameEquivalencesUsed.length)for(const equivalence of reference.nameEquivalencesUsed){
      lines.push('',`Dokumentált névváltozatként megfeleltetve: **${md(equivalence.referenceName)} = ${md(equivalence.equivalentName)}**. ${md(equivalence.reason)} Forrás: ${equivalence.evidenceUrls.map((url,index)=>`[${index+1}](${url})`).join(', ')}.`);
    }
    if(reference.additionalMissingIdentityCount){
      lines.push('',`További ${reference.additionalMissingIdentityCount} külön területi azonossághoz nincs határ, bár azonos nevű másik városrész már szerepel a gyűjteményben:`);
      for(const identity of reference.additionalMissingIdentities)lines.push('',`- **${md(identity.name)}${identity.districts?.length?' ('+identity.districts.map(n=>n+'. kerület').join(', ')+')':''}:** ${md(identity.note ?? identity.reason)}${identity.sourceUrl?' [Forrás]('+identity.sourceUrl+').':''}`);
      if(reference.totalKnownMissingIdentityCount!==null)lines.push('',`Ez összesen ${reference.totalKnownMissingIdentityCount} ismert hiányzó városrészterület: ${reference.missingNameCount} hiányzó név és ${reference.additionalMissingIdentityCount} további, azonos nevű külön terület. A referenciában ${reference.referenceIdentityCount} külön városrészterület szerepel.`);
    }
    for(const note of reference.countingNotes)lines.push('',md(note));
    if(reference.transcriptionNote)lines.push('',md(reference.transcriptionNote));
  }
  lines.push('', '## További, forrásban névként vagy pontként ismert tételek határ nélkül','',
    'Ez a lista az átvett források hiányait mutatja, nem ellenőrzött, teljes jelenlegi városrészjegyzék. A kerületszintű vagy történelmi megnevezések is külön tisztázásra szorulhatnak.');
  for(const row of report.cities) if(row.knownNamesWithoutGeometry.length)lines.push('',`**${md(row.municipality)} (${row.knownNamesWithoutGeometryCount}):** ${row.knownNamesWithoutGeometry.map(item=>md(item.name)).join(', ')}.`);
  lines.push('', '## Lekérdezési és besorolási korlátok','',
    `${s.failedQueries} település legutóbbi lekérése sikertelen, ${s.successfulEmptyQueries} esetben a használt lekérdezés sikeres volt, de nem adott határgeometriát; ${s.unrequestedCities} ismert forrástelepülést nem vizsgáltunk ezzel az OSM-lekéréssel.`,
    '', 'Az időtúllépés nem jelenti a határvonal hiányát. A sikeres üres eredmény sem zárja ki más adatforrás vagy más térképi címkézés létezését. A teljes országos vagy jelenlegi városi hiány száma ezért ismeretlen.',
    '', `${report.unassignedSourceRecords.length} forrásrekord települési hozzárendelése nem oldódott fel; a részletek a JSON-jelentésben szerepelnek.`,'');
  return lines.join('\n');
}

async function optionalJson(file) {try{return {text:await readFile(file,'utf8')};}catch(error){if(error.code==='ENOENT')return null;throw error;}}
export async function writeReports({root=ROOT,check=false}={}) {
  const directory=join(root,'data/neighborhoods');
  let catalogText;
  try{catalogText=gunzipSync(await readFile(join(directory,'catalog.geojson.gz'))).toString('utf8');}
  catch(error){if(error.code!=='ENOENT')throw error;catalogText=await readFile(join(directory,'catalog.geojson'),'utf8');}
  const coverageText=await readFile(join(directory,'coverage.json'),'utf8');
  const references=await optionalJson(join(directory,'reference-inventories.json'));
  const audit=await optionalJson(join(directory,'name-audit.json'));
  const report=createReport(JSON.parse(catalogText),JSON.parse(coverageText),{
    references:references?JSON.parse(references.text):undefined,nameAudit:audit?JSON.parse(audit.text):null});
  report.inputFingerprints={catalogSha256:fingerprint(catalogText),coverageSha256:fingerprint(coverageText),
    referencesSha256:references?fingerprint(references.text):null,nameAuditSha256:audit?fingerprint(audit.text):null};
  for(const [name,content] of [['report.json',JSON.stringify(report,null,2)+'\n'],['report.csv',csvReport(report)],['report.md',markdownReport(report)]]) {
    const output=join(directory,name);
    if(check){if(await readFile(output,'utf8')!==content)throw new Error(`${name} is stale; run node scripts/neighborhoods/report.mjs`);}
    else await writeFile(output,content);
  }
  return report;
}
if(process.argv[1] && import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  const args=process.argv.slice(2);if(args.some(arg=>arg!=='--check'))throw new Error('Usage: node scripts/neighborhoods/report.mjs [--check]');
  const report=await writeReports({check:args.includes('--check')});
  console.log(`${args.includes('--check')?'Verified':'Wrote'} city statistics: ${report.summary.acceptedNeighbourhoodNameCount} accepted neighborhood names across ${report.summary.settlementsWithAcceptedNeighbourhoodNames} settlements (${report.summary.neighbourhoodGeometryCount} geometries); unknown full coverage remains explicit.`);
}
