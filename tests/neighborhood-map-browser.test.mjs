/** Real Leaflet + real picker regressions with deterministic display-only map
 * rectangles. HTTP fixtures never geocode addresses or replace search geometry. */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {getLocation,searchLocations} from '../dist/locations.js';
import {neighborhoods} from '../dist/neighborhoods-data.js';
import {editorField,editorSave,editorStep} from './editor-browser-helpers.mjs';
import {mockMapTiles} from './map-browser-network.mjs';

const modulePath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
const version='a'.repeat(64),city=getLocation('city:Debrecen'),otherCity=getLocation('city:Szeged');
const quarter=(city,name)=>getLocation(neighborhoods.find(item=>item.city===city&&item.name===name).id);
const venkert=quarter('Debrecen','Vénkert'),sestakert=quarter('Debrecen','Sestakert'),tocoskert=quarter('Debrecen','Tócóskert'),szeged=quarter('Szeged','Belváros');
const buda=quarter('Budapest','Buda'),pest=quarter('Budapest','Pest'),budapestWard=quarter('Budapest','V. kerület'),belvaros=quarter('Budapest','Belváros');
const rectangle=(west,south,east,north)=>[[[west,south],[east,south],[east,north],[west,north],[west,south]]];
const makeFeature=(location,bbox)=>({type:'Feature',id:location.id,bbox,properties:{id:location.id,name:location.name,city:location.city,label:location.label,estimated:location.estimated},geometry:{type:'Polygon',coordinates:rectangle(...bbox)}});
const debrecenBounds=[21.59,47.50,21.65,47.56],szegedBounds=[20.12,46.23,20.18,46.29];
const polygons=[makeFeature(venkert,[21.601,47.536,21.624,47.549]),makeFeature(sestakert,[21.60,47.535,21.625,47.55]),makeFeature(tocoskert,[21.63,47.505,21.645,47.52])];
const szegedFeature=makeFeature(szeged,[20.135,46.245,20.155,46.265]);
const budapestBounds=[18.95,47.40,19.25,47.60];
// A deliberately simple hierarchy with real catalogue identities: the two
// city halves are broad, the ward is smaller and its neighborhood smaller yet.
const budapestPolygons=[makeFeature(buda,[18.95,47.40,19.10,47.60]),makeFeature(pest,[19.10,47.40,19.25,47.60]),makeFeature(budapestWard,[19.08,47.48,19.12,47.52]),makeFeature(belvaros,[19.09,47.49,19.11,47.51])];
const manifest={schemaVersion:1,version,count:8,cities:[{city:'Debrecen',bounds:debrecenBounds,file:'city-aaaaaaaaaaaaaaaa.json',count:3},{city:'Szeged',bounds:szegedBounds,file:'city-bbbbbbbbbbbbbbbb.json',count:1},{city:'Budapest',bounds:budapestBounds,file:'city-cccccccccccccccc.json',count:4}],focus:{'city:Debrecen':debrecenBounds,'city:Szeged':szegedBounds,'city:Budapest':budapestBounds,'district:Budapest:5':budapestPolygons[2].bbox,...Object.fromEntries([...polygons,szegedFeature,...budapestPolygons].map(item=>[item.id,item.bbox]))},attribution:['Isolated synthetic map display fixture; not address/search data.']};
const owner={id:'10000000-0000-4000-8000-000000000001',name:'Térképes Anna',email:'map-browser@example.test',phone:'',accountType:'private'};
const searchId='20000000-0000-4000-8000-000000000001';
const propertyId='30000000-0000-4000-8000-000000000001';
const interact=(viewport,locator)=>viewport.touch?locator.tap():locator.click();
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function zoom(map,viewport,direction){
 await interact(viewport,map.locator(`.leaflet-control-zoom-${direction}`));
 // Leaflet ignores another desktop zoom click during its normal 250ms
 // transition. Also let the debounced viewport render settle before observing
 // layer visibility or starting another zoom action.
 await delay(275);const canvas=map.locator('.location-map-canvas');
 for(let attempt=0;attempt<40;attempt++){
  if(!await canvas.evaluate(element=>element.classList.contains('leaflet-zoom-anim')||!!element.querySelector('.leaflet-zoom-anim'))){await delay(225);return;}
  await delay(25);
 }
 assert.equal(await canvas.evaluate(element=>element.classList.contains('leaflet-zoom-anim')||!!element.querySelector('.leaflet-zoom-anim')),false,'The normal map zoom transition must settle');
}
function gate(){let release;const promise=new Promise(resolve=>{release=resolve;});return {promise,release};}

async function fixture(browser,viewport,{authenticated=false}={}){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await mockMapTiles(context);
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 await context.route('https://get.geojs.io/**',route=>route.fulfill({status:200,contentType:'application/json',body:'{"country_code":"XX"}'}));
 await context.route(`${origin}/runtime-config.js`,route=>route.fulfill({status:200,contentType:'text/javascript',body:'globalThis.OTTHONRA_CONFIG=Object.freeze({mode:"api",environment:"test"});'}));
 if(authenticated)await context.addInitScript(origin=>localStorage.setItem('otthonra.api',JSON.stringify({baseUrl:origin,token:'map-browser-session'})),origin);
 const server={requests:[],writes:[],errors:[],unhandled:[],failCity:null,holdCity:null,hold:null,searches:[{id:searchId,ownerId:owner.id,title:'Meglévő keresésem',city:'Debrecen',locationIds:['city:Debrecen'],locations:[city],type:'Lakás',maxPrice:90000000,minArea:40,minRooms:1,conditions:[],buildings:[],floors:[],balcony:false,elevator:false}],properties:[{id:propertyId,ownerId:owner.id,title:'Meglévő otthonom',city:'Debrecen',locationId:'city:Debrecen',type:'Lakás',price:60000000,area:60,rooms:2,wholeRooms:2,halfRooms:0,images:[],addressDetails:{street:'Fiktív tesztutca',houseNumber:'1',postalCode:'4028'}}],active:{kind:'search',id:searchId}};
 await context.route(`${origin}/data/map/**`,async route=>{
  const path=new URL(route.request().url()).pathname;server.requests.push(path);
  const reply=async(value,status=200)=>{try{await route.fulfill({status,contentType:'application/json',body:JSON.stringify(value)});}catch(error){if(!/closed|handled|abort|intercept|disposed/i.test(String(error)))throw error;}};
  if(path==='/data/map/index.json')return reply(manifest);
  const selected=path.endsWith('city-aaaaaaaaaaaaaaaa.json')?'Debrecen':path.endsWith('city-bbbbbbbbbbbbbbbb.json')?'Szeged':path.endsWith('city-cccccccccccccccc.json')?'Budapest':null;
  if(!selected){server.unhandled.push(path);return reply({message:'Unknown map fixture'},404);}
  if(server.holdCity===selected&&server.hold)await server.hold.promise;
  if(server.failCity===selected){server.failCity=null;return reply({message:'Temporary map fixture failure'},503);}
  return reply({type:'FeatureCollection',version,city:selected,features:selected==='Debrecen'?polygons:selected==='Budapest'?budapestPolygons:[szegedFeature]});
 });
 await context.route(`${origin}/api/**`,async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname.slice(4),method=request.method();
  const json=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  if(path==='/public/landing')return json({regions:[],region:null,scope:'national',searches:[],properties:[]});
  if(path==='/locations')return json({items:searchLocations(url.searchParams.get('q')||'',12,{kind:url.searchParams.get('kind')||'search'})});
  if(path==='/streets')return json({items:[]});
  if(path==='/me')return json({...owner,credits:100,unreadNotificationCount:0});
  if(path==='/me/entities')return json({properties:server.properties,searchRequests:server.searches,active:server.active,decisions:[],reportedOwnerIds:[],reportedEntities:[]});
  if(path==='/credits/ledger'||path==='/matches')return json([]);
  if(path==='/feedback/pending')return json({feedbackPrompt:null});
  if(path==='/test/feedback-scenario')return json({available:false});
  if(path==='/feed')return json({active:server.active,items:[],stage:'empty',hasApproximate:false});
  if(path==='/me/active'&&method==='PUT'){server.active=request.postDataJSON();return json(server.active);}
  if(path==='/searches'&&method==='POST'){
   const body=request.postDataJSON(),saved={...body,id:'20000000-0000-4000-8000-000000000002',ownerId:owner.id,locations:body.locationIds.map(getLocation).filter(Boolean)};
   server.writes.push(body);server.searches.push(saved);return json(saved,201);
  }
  server.unhandled.push(method+' '+path);return json({message:'Unexpected map browser fixture API route'},404);
 });
 const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',error=>server.errors.push(error.message));
 page.on('request',request=>{const path=new URL(request.url()).pathname;if(path.endsWith('neighborhoods.json.gz'))server.errors.push('The map requested the complete search geometry dataset.');});
 return {context,page,server};
}
async function inspect(f,viewport,name,run){try{await run();assert.deepEqual(f.server.unhandled,[]);assert.deepEqual(f.server.errors,[]);}catch(error){await mkdir(resolve('.local/browser-tests/screenshots'),{recursive:true});await f.page.screenshot({path:resolve('.local/browser-tests/screenshots',`neighborhood-map-${name}-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}finally{f.server.hold?.release();await f.context.close();}}
async function assertOverlay(map){
 const svg=map.locator('.leaflet-overlay-pane > svg');await svg.waitFor();const box=await svg.boundingBox();
 assert.ok(box&&box.width>100&&box.height>100,'The real Leaflet SVG overlay must retain its viewport size instead of the global 20px icon size');
}
async function readyMap(page,id){const map=page.locator(id);await map.locator('.location-map-canvas.leaflet-container').waitFor();if(await map.locator('.leaflet-overlay-pane > svg').count())await assertOverlay(map);return map;}
const pathFor=(map,id)=>map.locator(`path.leaflet-interactive[data-map-neighborhood-id="${id}"]`);
async function chooseText(page,viewport,id,value,{landing=false}={}){
 const prefix=landing?'landing-location':'location';await page.locator(`#${prefix}-input`).fill(value);const item=page.locator(`#${prefix}-options [data-location-id="${id}"]`);await item.waitFor();await interact(viewport,item);
}
async function clickPolygon(map,id,viewport){
 const path=pathFor(map,id),canvas=map.locator('.location-map-canvas');await path.waitFor();await assertOverlay(map);await canvas.scrollIntoViewIfNeeded();
 const shape=await path.boundingBox(),box=await canvas.boundingBox();assert.ok(shape&&box);
 const position={x:shape.x+shape.width/2-box.x,y:shape.y+shape.height/2-box.y};
 // Click the actual screen point, allowing either overlapping SVG shape to
 // receive the pointer before the common map containment picker runs.
 await (viewport.touch?canvas.tap({position}):canvas.click({position}));
}
async function removeChip(page,viewport,id,{landing=false}={}){await interact(viewport,page.locator(`${landing?'#landing-location-chips':'#location-chips'} [data-remove-location="${id}"]`));}
async function openEditor(page,viewport,kind='search'){
 await page.goto(`${origin}/#${kind==='property'?'properties':'searches'}`,{waitUntil:'domcontentloaded'});await interact(viewport,page.locator(`.page-heading [data-action="new"][data-kind="${kind}"]`));await page.locator('#entity-form').waitFor();
}

async function landingSelection(browser,viewport){
 const f=await fixture(browser,viewport),{page,server}=f;
 await inspect(f,viewport,'landing',async()=>{
  await page.goto(`${origin}/#landing`,{waitUntil:'domcontentloaded'});const map=await readyMap(page,'#landing-location-map');await delay(350);
  assert.equal(server.requests.filter(path=>path!=='/data/map/index.json').length,0,'A country-level view must not download every city polygon');
  assert.match(await map.locator('.leaflet-control-attribution').innerText(),/OpenStreetMap/);
  await chooseText(page,viewport,city.id,'Debrecen',{landing:true});await pathFor(map,venkert.id).waitFor();assert.equal(await map.locator('path.leaflet-interactive').count(),3);
  await clickPolygon(map,venkert.id,viewport);
  await page.locator(`#landing-location-chips [data-remove-location="${venkert.id}"]`).waitFor();
  assert.equal(await page.locator(`#landing-location-chips [data-remove-location="${sestakert.id}"]`).count(),0,'One map tap must immediately select the smaller of the two visible overlapping polygons');
  assert.equal(await map.locator('.leaflet-popup-content,.location-map-overlap').count(),0,'Overlap selection must not require a second choice from a popup');
  assert.equal(await page.locator(`#landing-location-chips [data-remove-location="${city.id}"]`).count(),0,'A map quarter narrows and replaces its covering whole-city filter');
  await chooseText(page,viewport,city.id,'Debrecen',{landing:true});await pathFor(map,tocoskert.id).waitFor();
  await clickPolygon(map,tocoskert.id,viewport);await clickPolygon(map,tocoskert.id,viewport);assert.equal(await page.locator(`#landing-location-chips [data-remove-location="${tocoskert.id}"]`).count(),1,'Repeated map selection must not create duplicate locations');
  assert.equal(await pathFor(map,tocoskert.id).getAttribute('aria-pressed'),'true');await removeChip(page,viewport,venkert.id,{landing:true});assert.equal(await pathFor(map,venkert.id).getAttribute('aria-pressed'),'false');
  await chooseText(page,viewport,otherCity.id,'Szeged',{landing:true});await pathFor(map,szeged.id).waitFor();assert.equal(await pathFor(map,venkert.id).count(),0,'A new textual location must focus and render the new city');
  const mapBox=await map.boundingBox(),inputBox=await page.locator('#landing-location-input').boundingBox();assert.ok(mapBox.y>=inputBox.y+inputBox.height,'The map belongs below the location input');
  for(let index=0;index<8;index++){const out=map.locator('.leaflet-control-zoom-out');if(await out.getAttribute('aria-disabled')==='true'||await map.locator('path.leaflet-interactive').count()===0)break;await zoom(map,viewport,'out');}
  await page.waitForFunction(()=>document.querySelectorAll('#landing-location-map path.leaflet-interactive').length===0);assert.equal(new Set(server.requests.filter(path=>path!=='/data/map/index.json')).size,2,'Only visited city files are loaded');
  console.log(`Neighborhood map landing ${viewport.name}: lazy city loading, auto focus, one-tap smallest overlapping polygon, canonical chips, selected styling and zoom-out limits passed.`);
 });
}

async function budapestZoomLevels(browser,viewport){
 const f=await fixture(browser,viewport),{page,server}=f;
 await inspect(f,viewport,'budapest-levels',async()=>{
  await page.goto(`${origin}/#landing`,{waitUntil:'domcontentloaded'});const map=await readyMap(page,'#landing-location-map');
  await chooseText(page,viewport,'city:Budapest','Budapest',{landing:true});await pathFor(map,buda.id).waitFor();await pathFor(map,pest.id).waitFor();
  const visibleIds=()=>map.locator('path.leaflet-interactive').evaluateAll(paths=>paths.map(path=>path.dataset.mapNeighborhoodId).sort());
  assert.deepEqual(await visibleIds(),[buda.id,pest.id].sort(),'A distant Budapest view must show only Buda and Pest, without smaller overlapping regions');
  await clickPolygon(map,buda.id,viewport);await page.locator(`#landing-location-chips [data-remove-location="${buda.id}"]`).waitFor();
  assert.equal(await page.locator('#landing-location-chips [data-remove-location="city:Budapest"]').count(),0,'A broad city half must also narrow the whole-city search in one tap');
  assert.equal(await map.locator('.leaflet-popup-content').count(),0);
  for(let step=0;step<6&&!await pathFor(map,budapestWard.id).count();step++)await zoom(map,viewport,'in');
  await pathFor(map,budapestWard.id).waitFor();assert.deepEqual(await visibleIds(),[budapestWard.id],'Closer zoom must replace broad city halves with the smaller ward level');
  await clickPolygon(map,budapestWard.id,viewport);await page.locator(`#landing-location-chips [data-remove-location="${budapestWard.id}"]`).waitFor();
  for(let step=0;step<6&&!await pathFor(map,belvaros.id).count();step++)await zoom(map,viewport,'in');
  await pathFor(map,belvaros.id).waitFor();assert.deepEqual(await visibleIds(),[belvaros.id],'The finest zoom must expose the small neighborhood without rendering its broader parent on top');
  await clickPolygon(map,belvaros.id,viewport);await page.locator(`#landing-location-chips [data-remove-location="${belvaros.id}"]`).waitFor();
  assert.equal(await map.locator('.leaflet-popup-content,.location-map-overlap').count(),0,'Each zoom level must select directly without an overlap chooser');
  assert.equal(new Set(server.requests.filter(path=>path!=='/data/map/index.json')).size,1,'Changing detail levels must reuse the one cached city chunk');
  await removeChip(page,viewport,buda.id,{landing:true});await chooseText(page,viewport,buda.id,'Buda (Budapest)',{landing:true});await pathFor(map,buda.id).waitFor();
  assert.deepEqual(await visibleIds(),[buda.id,pest.id].sort(),'Text focus on a broad area must return to its own selectable zoom level');
  await chooseText(page,viewport,'district:Budapest:5','Budapest V. kerület',{landing:true});await pathFor(map,budapestWard.id).waitFor();
  assert.deepEqual(await visibleIds(),[budapestWard.id],'A Budapest district alias must focus the matching canonical ward detail level');
  await removeChip(page,viewport,belvaros.id,{landing:true});await chooseText(page,viewport,belvaros.id,'Belváros (Budapest)',{landing:true});await pathFor(map,belvaros.id).waitFor();
  assert.deepEqual(await visibleIds(),[belvaros.id],'Text focus on a fine neighborhood must show its detail level immediately');
  assert.equal(await pathFor(map,belvaros.id).getAttribute('aria-pressed'),'true');
  console.log(`Neighborhood map Budapest ${viewport.name}: Buda/Pest, progressively smaller levels, direct selection, cached geometry and textual focus passed.`);
 });
}

async function ownedWizard(browser,viewport){
 const f=await fixture(browser,viewport,{authenticated:true}),{page,server}=f;
 await inspect(f,viewport,'owned',async()=>{
  await openEditor(page,viewport);await page.locator('#f-type').selectOption('Lakás');const map=await readyMap(page,'#search-location-map');await chooseText(page,viewport,'city:Solymár','Solymár');await chooseText(page,viewport,city.id,'Debrecen');await pathFor(map,tocoskert.id).waitFor();await clickPolygon(map,tocoskert.id,viewport);
  assert.equal(await page.locator(`#location-chips [data-remove-location="${tocoskert.id}"]`).count(),1);assert.equal(await page.locator(`#location-chips [data-remove-location="${city.id}"]`).count(),0);assert.equal(await page.locator('#location-chips [data-remove-location="city:Solymár"]').count(),1,'Narrowing Debrecen must retain another selected town');assert.equal(await page.locator('#location-chips .location-chip').count(),2);
  assert.notEqual(await page.evaluate(()=>document.activeElement?.id),'location-input','A map tap must not summon the mobile keyboard');
  await page.evaluate(()=>{globalThis.__mapEditorNode=document.getElementById('search-location-map');});
  await (await editorField(page,'#f-maxPrice')).fill('90');await (await editorField(page,'#f-minArea')).fill('40');await (await editorField(page,'#f-minRooms')).fill('1');await editorStep(page,0);
  assert.equal(await page.evaluate(()=>globalThis.__mapEditorNode===document.getElementById('search-location-map')),true,'Wizard navigation must preserve the mounted picker/map');await pathFor(map,tocoskert.id).waitFor();assert.equal(await pathFor(map,tocoskert.id).getAttribute('aria-pressed'),'true');
  await editorSave(page,locator=>interact(viewport,locator));await page.getByRole('heading',{name:'Elkészült a keresési igényed.',exact:true}).waitFor();assert.deepEqual(server.writes[0].locationIds,['city:Solymár',tocoskert.id]);assert.equal(server.writes[0].maxPrice,90000000);assert.equal(server.writes.length,1);assert.deepEqual(server.active,{kind:'search',id:searchId});
  await interact(viewport,page.locator('.search-created-actions [data-action="close"]'));await openEditor(page,viewport,'property');assert.equal(await page.locator('#search-location-map,.location-map-canvas').count(),0,'Exact property-address forms must not offer search-only neighborhood polygons');await interact(viewport,page.locator('.modal-close'));
  console.log(`Neighborhood map wizard ${viewport.name}: canonical search save, mobile focus, persistent backward steps, cleanup and property-side exclusion passed.`);
 });
}

async function anonymousDraft(browser,viewport){
 const f=await fixture(browser,viewport),{page}=f;
 await inspect(f,viewport,'draft',async()=>{
  await page.goto(`${origin}/#landing`,{waitUntil:'domcontentloaded'});const landing=await readyMap(page,'#landing-location-map');await chooseText(page,viewport,city.id,'Debrecen',{landing:true});await pathFor(landing,tocoskert.id).waitFor();await clickPolygon(landing,tocoskert.id,viewport);assert.equal(await page.locator(`#landing-location-chips [data-remove-location="${city.id}"]`).count(),0);await interact(viewport,page.locator('#landing-search-form button[type="submit"]'));
  await page.locator('#onboarding-page #entity-form').waitFor();await page.locator('#f-type').selectOption('Lakás');const map=await readyMap(page,'#search-location-map');await pathFor(map,tocoskert.id).waitFor();assert.equal(await pathFor(map,tocoskert.id).getAttribute('aria-pressed'),'true');
  await chooseText(page,viewport,sestakert.id,'Sestakert');await pathFor(map,sestakert.id).waitFor();assert.equal(await pathFor(map,sestakert.id).getAttribute('aria-pressed'),'true');
  await page.waitForFunction(async ids=>{const draft=(await import('/onboarding.js')).loadDraft();return ids.every(id=>draft?.data?.locationIds?.includes(id));},[tocoskert.id,sestakert.id]);
  await page.reload({waitUntil:'domcontentloaded'});await readyMap(page,'#search-location-map');assert.equal(await page.locator('#location-chips .location-chip').count(),2);assert.equal(await page.locator('#f-type').inputValue(),'Lakás');
  await interact(viewport,page.locator('[data-action="landing"]').first());await readyMap(page,'#landing-location-map');assert.equal(await page.locator('#landing-location-chips .location-chip').count(),0,'Completed handoff must clear the transient landing query');assert.equal(await page.locator('#search-location-map').count(),0);
  console.log(`Neighborhood map draft ${viewport.name}: map choices enter anonymous onboarding, textual neighborhood focus, draft reload and picker lifetime cleanup passed.`);
 });
}

async function failuresAndStaleReads(browser,viewport){
 const f=await fixture(browser,viewport),{page,server}=f;
 await inspect(f,viewport,'network',async()=>{
  server.failCity='Debrecen';await page.goto(`${origin}/#landing`,{waitUntil:'domcontentloaded'});const map=await readyMap(page,'#landing-location-map');await chooseText(page,viewport,city.id,'Debrecen',{landing:true});const retry=map.locator('.location-map-retry');await retry.waitFor();assert.equal(await page.locator('#landing-location-chips .location-chip').count(),1,'A geometry failure must not erase text selections');
  await interact(viewport,retry);await pathFor(map,tocoskert.id).waitFor();await assertOverlay(map);assert.equal(await retry.isVisible(),false);
  // A new map instance avoids a legitimately cached Debrecen display chunk.
  await page.reload({waitUntil:'domcontentloaded'});await readyMap(page,'#landing-location-map');server.holdCity='Debrecen';server.hold=gate();const before=server.requests.length;
  await chooseText(page,viewport,city.id,'Debrecen',{landing:true});await page.waitForFunction(()=>document.querySelector('#landing-location-map .location-map-status')?.textContent.length>0);for(let index=0;index<40&&!server.requests.slice(before).some(path=>path.endsWith('city-aaaaaaaaaaaaaaaa.json'));index++)await delay(25);assert.ok(server.requests.slice(before).some(path=>path.endsWith('city-aaaaaaaaaaaaaaaa.json')));
  await chooseText(page,viewport,otherCity.id,'Szeged',{landing:true});await pathFor(map,szeged.id).waitFor();server.hold.release();server.hold=null;await delay(350);assert.equal(await pathFor(map,venkert.id).count(),0,'An older city response cannot paint over the newly focused map');assert.equal(await pathFor(map,szeged.id).count(),1);
  await page.locator('#landing-location-input').fill('Debrecen');await page.locator('#landing-location-options [data-location-id]').first().waitFor();await interact(viewport,map.locator('.location-map-status'));assert.equal(await page.locator('#landing-location-options').isHidden(),true,'A visible map-area click dismisses the suggestion popup');assert.equal(await page.locator('#landing-location-input').inputValue(),'Debrecen','Dismissing suggestions must retain the typed query');await zoom(map,viewport,'in');
  await f.context.route('https://tile.openstreetmap.org/**',route=>route.fulfill({status:503,contentType:'text/plain',body:'Isolated tile outage'}));await zoom(map,viewport,'in');
  await page.waitForFunction(()=>document.querySelector('#landing-location-map .location-map-status')?.textContent.includes('háttértérkép'));
  await pathFor(map,szeged.id).waitFor();await pathFor(map,szeged.id).press('Enter');assert.equal(await page.locator(`#landing-location-chips [data-remove-location="${szeged.id}"]`).count(),1,'Background tile failures must not block keyboard selection of public polygons');
  console.log('Neighborhood map network desktop: failed geometry retry, preserved text search, stale city responses, outside dismissal and polygon selection during a tile outage passed.');
 });
}

async function narrowingAtLimit(browser,viewport){
 const f=await fixture(browser,viewport,{authenticated:true}),{page,server}=f;
 await inspect(f,viewport,'limit',async()=>{
  const others=neighborhoods.filter(item=>item.city==='Debrecen'&&![venkert.id,sestakert.id,tocoskert.id].includes(item.id)).slice(0,49).map(item=>item.id);assert.equal(others.length,49,'The canonical city supplies a full selection-limit fixture');
  server.searches[0].locationIds=[city.id,...others];server.searches[0].locations=server.searches[0].locationIds.map(getLocation);
  await page.goto(`${origin}/#searches`,{waitUntil:'domcontentloaded'});await interact(viewport,page.locator(`[data-action="edit"][data-kind="search"][data-id="${searchId}"]`));const map=await readyMap(page,'#search-location-map');await pathFor(map,tocoskert.id).waitFor();assert.equal(await page.locator('#location-chips .location-chip').count(),50);
  await clickPolygon(map,tocoskert.id,viewport);assert.equal(await page.locator('#location-chips .location-chip').count(),50,'Replacing the covering city must succeed even at the 50-location limit');assert.equal(await page.locator(`#location-chips [data-remove-location="${city.id}"]`).count(),0);assert.equal(await page.locator(`#location-chips [data-remove-location="${tocoskert.id}"]`).count(),1);assert.equal(await page.locator('#location-error').innerText(),'');
  await removeChip(page,viewport,others[0]);await chooseText(page,viewport,city.id,'Debrecen');assert.equal(await page.locator('#location-chips .location-chip').count(),50);await clickPolygon(map,tocoskert.id,viewport);assert.equal(await page.locator('#location-chips .location-chip').count(),49,'Clicking an already selected quarter still removes a re-added whole-city filter');assert.equal(await page.locator(`#location-chips [data-remove-location="${tocoskert.id}"]`).count(),1);assert.equal(await page.locator(`#location-chips [data-remove-location="${others[1]}"]`).count(),1,'Other selected quarters remain unchanged');
  console.log('Neighborhood map limit desktop: covering city replacement at50, retained other quarters and existing-quarter narrowing without duplicates passed.');
 });
}

const browser=await chromium.launch({headless:true});let failed=0;
try{for(const viewport of viewports)for(const test of [landingSelection,budapestZoomLevels,ownedWizard,anonymousDraft])try{await test(browser,viewport);}catch(error){failed++;console.error(`${test.name} ${viewport.name}: ${error.stack||error}`);}for(const test of [failuresAndStaleReads,narrowingAtLimit])try{await test(browser,viewports[0]);}catch(error){failed++;console.error(`${test.name} desktop: ${error.stack||error}`);}}finally{await browser.close();}
if(failed)process.exitCode=1;
