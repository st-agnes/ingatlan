import { readFile, writeFile } from 'node:fs/promises';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createReport, createNameEvidenceIndex, findNameEvidence } from './report.mjs';

const root = fileURLToPath(new URL('../../', import.meta.url));
const catalog = JSON.parse(gunzipSync(await readFile(path.join(root, 'data/neighborhoods/catalog.geojson.gz'))).toString('utf8'));
const coverage = JSON.parse(await readFile(path.join(root, 'data/neighborhoods/coverage.json'), 'utf8'));
const [references,nameAudit]=await Promise.all(['reference-inventories.json','name-audit.json'].map(async name=>{
  try{return JSON.parse(await readFile(path.join(root,'data/neighborhoods',name),'utf8'));}
  catch(error){if(error.code==='ENOENT')return null;throw error;}
}));
const report=createReport(catalog,coverage,{references:references ?? {inventories:[]},nameAudit});
const nameEvidenceIndex=createNameEvidenceIndex(nameAudit);
for(const feature of catalog.features)feature.properties.previewNameEvidence=findNameEvidence(feature.properties,nameEvidenceIndex);
const data = JSON.stringify({ catalog, coverage, report }).replaceAll('<', '\\u003c');
const html = `<!doctype html>
<html lang="hu"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Otthonra – városrészhatárok ellenőrzése</title>
<style>
:root{font:16px/1.5 system-ui,sans-serif;color:#24372d;background:#f5f4ee}*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0}header,main,footer{max-width:1280px;margin:auto;padding:20px}h1{font-size:clamp(24px,4vw,36px);margin:0 0 8px}p{margin:8px 0}select,button,input{font:inherit;padding:10px;border:1px solid #8a9d8e;border-radius:8px;background:white;color:inherit}label{display:grid;gap:5px}a{color:#1d6342}.toolbar{display:flex;gap:16px;align-items:end;flex-wrap:wrap}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:18px;margin-top:18px}.map,.panel{border:1px solid #d0d7cc;border-radius:14px;background:#fff;overflow:hidden}.map{position:relative;min-height:420px}svg{display:block;width:100%;height:65vh;min-height:420px;max-height:780px}.area{fill:#83ac9470;stroke:#244e38;stroke-width:1;vector-effect:non-scaling-stroke;cursor:pointer;fill-rule:evenodd}.area.selected{fill:#d9a54f9c;stroke:#8e5b15;stroke-width:2}.area:hover{fill:#5d9870a0}.panel{padding:16px}.list{max-height:44vh;overflow:auto;margin:12px 0}.list button{display:block;width:100%;margin:4px 0;text-align:left}.list button[aria-pressed=true]{background:#f2dfb7}.note{color:#5d6b60;font-size:14px}.status{padding:10px 14px;background:#fff3d9;border-radius:8px}.empty{position:absolute;inset:0;display:grid;place-items:center;padding:28px;text-align:center}dt{font-weight:600;margin-top:10px}dd{margin:0;overflow-wrap:anywhere}footer{font-size:14px}details{margin-top:16px}summary{cursor:pointer}table{border-collapse:collapse;width:100%;margin-top:12px}th,td{text-align:left;padding:7px;border-bottom:1px solid #ddd}@media(max-width:760px){.workspace{grid-template-columns:1fr}svg{height:48vh;min-height:300px}.map{min-height:300px}.list{max-height:220px}}
</style>
<header><h1>Városrészhatárok ellenőrzése</h1><p>Ingyenes forrásokból összegyűjtött térképi területek az Otthonra számára.</p><p id="summary"></p><p class="status">Mai és korábbi forráskivonatok együtt. Az egyes területeknél külön látható a névellenőrzés és a forrás dátuma; a régi geometria nem jelenti azt, hogy a városrész megszűnt. A meglévő poligonokból nem következik teljes városi lefedettség.</p></header>
<main><div class="toolbar"><label>Település<select id="city"></select></label><label>Városrész keresése<input id="query" type="search" autocomplete="off"></label><button id="all" type="button">Összes terület mutatása</button></div><p id="count" role="status"></p><div class="workspace"><div class="map"><svg id="map" viewBox="0 0 1000 760" role="img" aria-label="A kiválasztott városrészpoligonok térképe"></svg><div id="empty" class="empty" hidden></div></div><aside class="panel"><strong>Összegyűjtött területek</strong><div class="list" id="list"></div><div id="detail"><p>Válassz egy területet az alakja és a forrása ellenőrzéséhez.</p></div></aside></div><details><summary>Városonkénti darabszám és gyűjtési állapot</summary><div style="overflow:auto"><table><thead><tr><th>Város</th><th>Különböző városrésznevek</th><th>Geometriák</th><th>Korábbi OSM</th><th>Friss lekérés</th></tr></thead><tbody id="coverage"></tbody></table></div></details><p class="note">Az ellenőrző oldal önállóan működik: nem tölt be térképcsempéket, külső könyvtárat vagy fizetős API-t. A rajz kizárólag a forrásban szereplő alakzatot mutatja; az üres területeket nem egészíti ki becsléssel. A névszám városonként összevonja az azonos neveket és az ismert történelmi névváltozatokat. A név elfogadása és a határvonal mai pontossága külön kérdés.</p></main>
<footer>Forrás: <a href="https://whosonfirst.org/">Who's On First</a> és az egyes alakzatoknál megjelölt eredeti adatforrások. <a href="https://github.com/whosonfirst-data/whosonfirst-data-admin-hu/blob/master/LICENSE.md">Who's On First licenc és forrásmegjelölések</a>. Quattroshapes geometria esetén: <a href="https://github.com/foursquare/quattroshapes">Includes data from foursquare quattroshapes</a>. Az OpenStreetMapből származó kiegészítésekre <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors, ODbL</a> vonatkozik.</footer>
<script type="application/json" id="data">${data}</script>
<script>
'use strict';
const { catalog, coverage, report } = JSON.parse(document.getElementById('data').textContent);
const byId = id => document.getElementById(id);
const ns = 'http://www.w3.org/2000/svg';
const features = catalog.features;
const municipalities = [...new Set(features.map(f => f.properties.municipality))].filter(Boolean).sort((a,b) => a.localeCompare(b,'hu'));
const targets = (coverage.targetCities || []).map(c => typeof c === 'string' ? c : c.name || c.municipality || c.city).filter(Boolean);
const allCities = [...new Set([...targets, ...municipalities, ...report.cities.map(row=>row.municipality)])].sort((a,b) => a.localeCompare(b,'hu'));
const normalize = value => String(value).normalize('NFD').replace(/\\p{M}/gu,'').toLocaleLowerCase('hu').replace(/[^\\p{L}\\p{N}]+/gu,'');
const queryLabels={downloaded_with_boundaries:'Sikeres, talált határt',downloaded_without_boundaries:'Sikeres, nem adott határt',query_failed:'Sikertelen lekérés',not_requested:'Nem vizsgáltuk',other:'Egyéb'};
byId('summary').textContent=report.summary.acceptedNeighbourhoodNameCount+' különböző városrésznévhez van határ '+report.summary.settlementsWithAcceptedNeighbourhoodNames+' településen; '+report.summary.neighbourhoodGeometryCount+' geometria összesen.';
function sourceLabel(p){return p.source.provider==='openstreetmap' ? p.source.historical ? 'OSM · '+p.source.snapshotDate+' kivonat' : 'OSM · friss lekérés' : 'WOF · korábbi geometria';}
function isBroadArea(p){return p.boundaryKind==='district' || p.nameAudit?.canonicalNameIsNeighborhood===false || p.canonicalNameIsNeighborhood===false;}
function nameState(p){return p.nameAudit?.canonicalNameSupported===true || p.canonicalNameSupported===true || p.previewNameEvidence ? 'Mai magyar név: nyilvános forrással alátámasztva. A geometria és a terület besorolása ettől külön ellenőrizendő.' : p.nameReviewNeeded ? 'A forrásnév vagy a fordítás külön tisztázandó.' : 'A térképi forrás szerinti név; külön, mai névellenőrzés nincs rögzítve.';}
for (const name of allCities) { const option = document.createElement('option'); option.value=name; option.textContent=name; byId('city').append(option); }
byId('city').value = municipalities.includes('Budapest') ? 'Budapest' : municipalities[0] || allCities[0] || '';
let selected = null;
function polygons(feature) { return feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates; }
function render() {
 const city = byId('city').value;
 const query = normalize(byId('query').value);
 const visible = features.filter(f => f.properties.municipality === city && normalize(f.properties.name).includes(query)).sort((a,b)=>a.properties.name.localeCompare(b.properties.name,'hu'));
 if (!visible.some(f => f.properties.id === selected)) selected=null;
 const districts = visible.filter(f => isBroadArea(f.properties)).length;
 const cityReport=report.cities.find(row=>row.municipality===city);
 const accepted=new Set((cityReport?.acceptedNeighbourhoodNames || []).map(normalize));
 const shownNames=new Set(visible.filter(f=>f.properties.boundaryKind!=='district' && accepted.has(normalize(f.properties.name))).map(f=>normalize(f.properties.name)));
 byId('count').textContent = city + ': ' + shownNames.size + ' különböző városrésznév, ' + visible.length + ' geometria' + (districts ? ', ebből ' + districts + ' kerület vagy nagyobb terület' : '') + (query?' a szűrésben.':'.');
 byId('map').replaceChildren(); byId('list').replaceChildren();
 byId('empty').hidden = visible.length > 0;
 byId('empty').textContent = query ? 'Nincs a keresett névhez illeszkedő összegyűjtött terület.' : 'Ehhez a településhez még nincs poligon az összegyűjtött forrásokban. '+(queryLabels[cityReport?.osmQuery.observedResult] || '')+'. Ez nem bizonyítja, hogy a városrészeknek nincs határa.';
 const shown = selected ? visible.filter(f=>f.properties.id===selected) : visible;
 const points = shown.flatMap(f=>polygons(f).flat(2));
 if(points.length) {
  const lat = points.reduce((s,p)=>s+p[1],0)/points.length;
  const ratio = Math.cos(lat*Math.PI/180);
  const xs=points.map(p=>p[0]*ratio), ys=points.map(p=>p[1]);
  const minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(...ys), maxY=Math.max(...ys);
  const scale=Math.min(920/Math.max(maxX-minX,0.000001),680/Math.max(maxY-minY,0.000001));
  const project=p=>[500+(p[0]*ratio-(minX+maxX)/2)*scale,380-(p[1]-(minY+maxY)/2)*scale];
  for(const f of shown) {
   const area=document.createElementNS(ns,'path');
   area.setAttribute('d',polygons(f).flatMap(poly=>poly.map(ring=>ring.map((point,index)=>(index?'L':'M')+project(point).join(',')).join(' ')+' Z')).join(' '));
   area.setAttribute('class','area'+(selected===f.properties.id?' selected':''));
   area.setAttribute('tabindex','0'); area.setAttribute('role','button'); area.setAttribute('aria-label',f.properties.name);
   const title=document.createElementNS(ns,'title'); title.textContent=f.properties.name;area.append(title);
   area.addEventListener('click',()=>choose(f));area.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose(f);}});
   byId('map').append(area);
  }
 }
 for(const f of visible){const b=document.createElement('button');b.type='button';b.textContent=f.properties.name + (isBroadArea(f.properties) ? ' · kerület / nagyobb terület' : '') + ' · ' + sourceLabel(f.properties);b.setAttribute('aria-pressed',String(selected===f.properties.id));b.addEventListener('click',()=>choose(f));byId('list').append(b);}
 if(!selected)byId('detail').replaceChildren(Object.assign(document.createElement('p'),{textContent:'Válassz egy területet az alakja és a forrása ellenőrzéséhez.'}));
}
function safeLink(url,label){const link=document.createElement('a');link.textContent=label;try{const parsed=new URL(url);if(parsed.protocol==='https:'){link.href=parsed.href;link.target='_blank';link.rel='noopener noreferrer';}}catch{}return link;}
function choose(f){selected=f.properties.id;render();const p=f.properties;const dl=document.createElement('dl');const rows=[['Terület neve',p.name],['Település',p.municipality],['Terület típusa',isBroadArea(p) ? 'Kerület vagy nagyobb terület; a fő városrészszámban nem szerepel.' : 'Városrész'],['Név ellenőrzése',nameState(p)],['Forráskivonat dátuma',p.source.snapshotDate || p.source.osmTimestamp || 'A forrásban nincs igazolt adatállapot-dátum'],['Geometria ellenőrzése','A forrásból átvett határvonal; mai pontossága nincs igazolva.'],['Azonosító',p.id],['Geometria forrása',sourceLabel(p)]];if(p.sourceName && p.sourceName!==p.name)rows.splice(1,0,['Eredeti forrásnév',p.sourceName]);for(const [label,value] of rows){const dt=document.createElement('dt');dt.textContent=label;const dd=document.createElement('dd');dd.textContent=value;dl.append(dt,dd);}const contents=[dl,safeLink(p.source.url,'Eredeti adatállomány megnyitása')];const urls=[...new Set([...(p.nameAudit?.evidenceUrls || []),...(p.previewNameEvidence?.evidenceUrls || [])])];for(const [index,url] of urls.entries()){const paragraph=document.createElement('p');paragraph.append(safeLink(url,'Névellenőrzés forrása '+(index+1)));contents.push(paragraph);}byId('detail').replaceChildren(...contents);}
byId('city').addEventListener('change',()=>{selected=null;render();});byId('query').addEventListener('input',render);byId('all').addEventListener('click',()=>{selected=null;render();});
for(const row of report.cities){const tr=document.createElement('tr');for(const value of [row.municipality,row.acceptedNeighbourhoodNameCount,row.neighbourhoodGeometryCount,row.historicalOsmGeometryCount,queryLabels[row.osmQuery.observedResult]]){const cell=document.createElement('td');cell.textContent=String(value);tr.append(cell);}byId('coverage').append(tr);}
render();
</script></html>\n`;
const output = path.join(root, 'data/neighborhoods/review.html');
await writeFile(output, html);
console.log(`Prepared standalone neighborhood review: ${output}`);
