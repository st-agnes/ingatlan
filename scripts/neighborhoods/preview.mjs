import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../../', import.meta.url));
const catalog = JSON.parse(await readFile(path.join(root, 'data/neighborhoods/catalog.geojson'), 'utf8'));
const coverage = JSON.parse(await readFile(path.join(root, 'data/neighborhoods/coverage.json'), 'utf8'));
const data = JSON.stringify({ catalog, coverage }).replaceAll('<', '\\u003c');
const html = `<!doctype html>
<html lang="hu"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Otthonra – városrészhatárok ellenőrzése</title>
<style>
:root{font:16px/1.5 system-ui,sans-serif;color:#24372d;background:#f5f4ee}*{box-sizing:border-box}[hidden]{display:none!important}body{margin:0}header,main,footer{max-width:1280px;margin:auto;padding:20px}h1{font-size:clamp(24px,4vw,36px);margin:0 0 8px}p{margin:8px 0}select,button,input{font:inherit;padding:10px;border:1px solid #8a9d8e;border-radius:8px;background:white;color:inherit}label{display:grid;gap:5px}a{color:#1d6342}.toolbar{display:flex;gap:16px;align-items:end;flex-wrap:wrap}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:18px;margin-top:18px}.map,.panel{border:1px solid #d0d7cc;border-radius:14px;background:#fff;overflow:hidden}.map{position:relative;min-height:420px}svg{display:block;width:100%;height:65vh;min-height:420px;max-height:780px}.area{fill:#83ac9470;stroke:#244e38;stroke-width:1;vector-effect:non-scaling-stroke;cursor:pointer;fill-rule:evenodd}.area.selected{fill:#d9a54f9c;stroke:#8e5b15;stroke-width:2}.area:hover{fill:#5d9870a0}.panel{padding:16px}.list{max-height:44vh;overflow:auto;margin:12px 0}.list button{display:block;width:100%;margin:4px 0;text-align:left}.list button[aria-pressed=true]{background:#f2dfb7}.note{color:#5d6b60;font-size:14px}.status{padding:10px 14px;background:#fff3d9;border-radius:8px}.empty{position:absolute;inset:0;display:grid;place-items:center;padding:28px;text-align:center}dt{font-weight:600;margin-top:10px}dd{margin:0;overflow-wrap:anywhere}footer{font-size:14px}details{margin-top:16px}summary{cursor:pointer}table{border-collapse:collapse;width:100%;margin-top:12px}th,td{text-align:left;padding:7px;border-bottom:1px solid #ddd}@media(max-width:760px){.workspace{grid-template-columns:1fr}svg{height:48vh;min-height:300px}.map{min-height:300px}.list{max-height:220px}}
</style>
<header><h1>Városrészhatárok ellenőrzése</h1><p>Ingyenes forrásokból összegyűjtött térképi területek az Otthonra számára.</p><p class="status">Ellenőrzésre váró adatállomány. A poligonok megléte nem jelent teljes városi lefedettséget vagy igazolt házszintű pontosságot.</p></header>
<main><div class="toolbar"><label>Település<select id="city"></select></label><label>Városrész keresése<input id="query" type="search" autocomplete="off"></label><button id="all" type="button">Összes terület mutatása</button></div><p id="count" role="status"></p><div class="workspace"><div class="map"><svg id="map" viewBox="0 0 1000 760" role="img" aria-label="A kiválasztott városrészpoligonok térképe"></svg><div id="empty" class="empty" hidden></div></div><aside class="panel"><strong>Összegyűjtött területek</strong><div class="list" id="list"></div><div id="detail"><p>Válassz egy területet az alakja és a forrása ellenőrzéséhez.</p></div></aside></div><details><summary>A vizsgált fontosabb városok lefedettsége</summary><table><thead><tr><th>Város</th><th>Poligonjelöltek</th></tr></thead><tbody id="coverage"></tbody></table></details><p class="note">Az ellenőrző oldal önállóan működik: nem tölt be térképcsempéket, külső könyvtárat vagy fizetős API-t. A rajz kizárólag a forrásban szereplő alakzatot mutatja; az üres területeket nem egészíti ki becsléssel.</p></main>
<footer>Forrás: <a href="https://whosonfirst.org/">Who's On First</a> és az egyes alakzatoknál megjelölt eredeti adatforrások. <a href="https://github.com/whosonfirst-data/whosonfirst-data-admin-hu/blob/master/LICENSE.md">Who's On First licenc és forrásmegjelölések</a>. Quattroshapes geometria esetén: <a href="https://github.com/foursquare/quattroshapes">Includes data from foursquare quattroshapes</a>. Az OpenStreetMapből származó kiegészítésekre <a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors, ODbL</a> vonatkozik.</footer>
<script type="application/json" id="data">${data}</script>
<script>
'use strict';
const { catalog, coverage } = JSON.parse(document.getElementById('data').textContent);
const byId = id => document.getElementById(id);
const ns = 'http://www.w3.org/2000/svg';
const features = catalog.features;
const municipalities = [...new Set(features.map(f => f.properties.municipality))].filter(Boolean).sort((a,b) => a.localeCompare(b,'hu'));
const targets = (coverage.targetCities || []).map(c => typeof c === 'string' ? c : c.name || c.municipality || c.city).filter(Boolean);
const allCities = [...new Set([...targets, ...municipalities])].sort((a,b) => a.localeCompare(b,'hu'));
for (const name of allCities) { const option = document.createElement('option'); option.value=name; option.textContent=name; byId('city').append(option); }
byId('city').value = municipalities.includes('Budapest') ? 'Budapest' : municipalities[0] || allCities[0] || '';
let selected = null;
function polygons(feature) { return feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates; }
function render() {
 const city = byId('city').value;
 const query = byId('query').value.toLocaleLowerCase('hu');
 const visible = features.filter(f => f.properties.municipality === city && f.properties.name.toLocaleLowerCase('hu').includes(query)).sort((a,b)=>a.properties.name.localeCompare(b.properties.name,'hu'));
 if (!visible.some(f => f.properties.id === selected)) selected=null;
 const districts = visible.filter(f => f.properties.boundaryKind === 'district').length;
 byId('count').textContent = city + ': ' + (visible.length-districts) + ' városrészjelölt' + (districts ? ', ' + districts + ' kerület vagy egyéb terület' : '');
 byId('map').replaceChildren(); byId('list').replaceChildren();
 byId('empty').hidden = visible.length > 0;
 byId('empty').textContent = 'Ehhez a településhez még nincs használható poligon az összegyűjtött forrásokban. Ez nem bizonyítja, hogy a városrészeknek nincs határa.';
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
 for(const f of visible){const b=document.createElement('button');b.type='button';b.textContent=f.properties.name + (f.properties.boundaryKind === 'district' ? ' · kerület / egyéb terület' : '') + ' · ' + (f.properties.source.provider === 'openstreetmap' ? 'OSM' : 'WOF');b.setAttribute('aria-pressed',String(selected===f.properties.id));b.addEventListener('click',()=>choose(f));byId('list').append(b);}
 if(!selected)byId('detail').replaceChildren(Object.assign(document.createElement('p'),{textContent:'Válassz egy területet az alakja és a forrása ellenőrzéséhez.'}));
}
function choose(f){selected=f.properties.id;render();const p=f.properties;const dl=document.createElement('dl');for(const [label,value] of [['Városrész',p.name],['Település',p.municipality],['Terület típusa',p.boundaryKind === 'district' ? 'Kerület vagy más közigazgatási terület' : 'Városrészjelölt'],['Állapot','Ellenőrzésre vár'],['Név ellenőrzése',p.nameReviewNeeded ? 'Szükséges; eltérő forrásnév vagy fordítás' : 'A forrás szerinti név'],['Adatállapot',p.source.osmTimestamp || 'A forrásban nincs igazolt aktuális dátum'],['Azonosító',p.id],['Geometria forrása',p.source.geometrySource || p.source.provider]]){const dt=document.createElement('dt');dt.textContent=label;const dd=document.createElement('dd');dd.textContent=value;dl.append(dt,dd);}const link=document.createElement('a');link.textContent='Eredeti adatállomány megnyitása';try{const url=new URL(p.source.url);if(url.protocol==='https:'){link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';}}catch{}byId('detail').replaceChildren(dl,link);}
byId('city').addEventListener('change',()=>{selected=null;render();});byId('query').addEventListener('input',render);byId('all').addEventListener('click',()=>{selected=null;render();});
for(const city of allCities){const tr=document.createElement('tr');const a=document.createElement('td');a.textContent=city;const b=document.createElement('td');b.textContent=String(features.filter(f=>f.properties.municipality===city).length);tr.append(a,b);byId('coverage').append(tr);}
render();
</script></html>\n`;
const output = path.join(root, 'data/neighborhoods/review.html');
await writeFile(output, html);
console.log(`Prepared standalone neighborhood review: ${output}`);
