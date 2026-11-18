/** Neighborhood search and private address UI with real modules and a mocked geocoding API. */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {editorField,editorSave,editorStep} from './editor-browser-helpers.mjs';
import {searchLocations} from '../dist/locations.js';

const modulePath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const screenshots=resolve('.local/browser-tests/screenshots');
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
const demoState=page=>page.evaluate(async()=>(await import('/model.js')).model.getState());
const apiState=page=>page.evaluate(async()=>(await import('/api.js')).getModel().getState());
async function contextFor(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());
 await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 return context;
}
async function query(page,value){await (await editorField(page,'#location-input')).fill(value);await page.locator('#location-options').waitFor({state:'visible'});await page.waitForFunction(()=>{const list=document.getElementById('location-options');return list&&!list.hidden&&list.getAttribute('aria-busy')!=='true';});}
async function choose(page,interact,id){await interact(page.locator(`#location-options [data-location-id="${id}"]`));assert.equal(await page.locator('#location-input').inputValue(),'');}
async function openNew(page,interact,kind){await page.goto(`${origin}/#${kind==='property'?'properties':'searches'}`,{waitUntil:'domcontentloaded'});await interact(page.locator(`.page-heading [data-action="new"][data-kind="${kind}"]`));await page.waitForFunction(()=>document.activeElement?.id==='f-title');}
async function fits(page){const box=await page.locator('.modal').evaluate(element=>({width:element.clientWidth,scrollWidth:element.scrollWidth}));assert.ok(box.scrollWidth<=box.width+1,'Names and address controls must fit the modal');}
async function closeModal(page,interact){await interact(page.locator('.modal-close'));await page.locator('.modal').waitFor({state:'detached'});}

async function searchFlow(browser,viewport){
 const context=await contextFor(browser,viewport),page=await context.newPage(),errors=[];
 page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);
 const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await openNew(page,interact,'search');
  assert.equal(await page.locator('.editor-progress li').count(),5);
  const quarters=await page.evaluate(async()=>{
   const {searchLocations}=await import('/locations.js');
   return ['Újlipótváros','Békásmegyer'].map(query=>searchLocations(query,50).find(location=>location.kind==='neighborhood'&&location.city==='Budapest'));
  });
  assert.ok(quarters.every(Boolean),'Both established Budapest quarters must be in the imported catalog');
  for(const quarter of quarters){
   await query(page,quarter.label);
   const option=page.locator(`[data-location-id="${quarter.id}"]`);
   assert.match(await option.innerText(),/Városrész/);
   assert.ok((await option.innerText()).includes(quarter.label));
   await choose(page,interact,quarter.id);
  }
  await query(page,'Solymár');await choose(page,interact,'city:Solymár');
  assert.equal(await page.locator('#location-chips .location-chip').count(),3);
  assert.equal(await page.locator('#location-chips .location-kind-badge').count(),2);
  await query(page,'Debrecen');
  const input=page.locator('#location-input'),list=page.locator('#location-options');
  const geometry=await page.evaluate(()=>({input:document.getElementById('location-input').getBoundingClientRect().toJSON(),list:document.getElementById('location-options').getBoundingClientRect().toJSON()}));
  assert.ok(geometry.list.top>=geometry.input.bottom,'Suggestions must open below the typed query');
  await interact(page.locator('#f-title'));assert.equal(await list.isHidden(),true);assert.equal(await input.inputValue(),'Debrecen');
  assert.equal(await page.locator('#location-chips .location-chip').count(),3,'Outside dismissal must not select');
  await input.focus();await list.waitFor({state:'visible'});await input.press('Escape');assert.equal(await list.isHidden(),true);
  await input.fill('');
  const title=`Városrészek és település – ${viewport.name}`;
  await page.locator('#f-title').fill(title);
  await (await editorField(page,'#f-maxPrice')).fill('130');
  await (await editorField(page,'input[name="heatingTypes"][value="Hőszivattyú"]')).check();
  await fits(page);await editorSave(page,interact);
  await page.getByRole('heading',{name:'Elkészült a keresési igényed.',exact:true}).waitFor();
  let saved=(await demoState(page)).searches.find(item=>item.title===title);assert.ok(saved);
  assert.deepEqual(saved.locationIds,[quarters[0].id,quarters[1].id,'city:Solymár']);
  const previousActive=(await demoState(page)).active;
  await interact(page.locator('.search-created-actions [data-action="close"]'));
  assert.deepEqual((await demoState(page)).active,previousActive);
  await page.reload({waitUntil:'domcontentloaded'});
  await interact(page.locator(`[data-action="edit"][data-kind="search"][data-id="${saved.id}"]`));
  assert.equal(await page.locator('#location-chips .location-kind-badge').count(),2);
  assert.equal(await (await editorField(page,'input[name="heatingTypes"][value="Hőszivattyú"]')).isChecked(),true);
  await editorStep(page,0,interact);await interact(page.locator(`[data-remove-location="${quarters[1].id}"]`));
  await query(page,'Budapest 13');await choose(page,interact,'district:Budapest:13');
  await editorSave(page,interact);await page.locator('#entity-form').waitFor({state:'detached'});
  assert.equal(await page.locator('.search-created-actions').count(),0,'Editing must not reopen creation confirmation');
  saved=(await demoState(page)).searches.find(item=>item.id===saved.id);
  assert.deepEqual(saved.locationIds,[quarters[0].id,'city:Solymár','district:Budapest:13']);
  assert.deepEqual(saved.heatingTypes,['Hőszivattyú']);
  await interact(page.locator(`[data-action="activate-one"][data-kind="search"][data-id="${saved.id}"]`));
  await page.locator('.filter-button').waitFor();await interact(page.locator('.filter-button'));
  assert.equal(await page.locator('[data-summary-field="locationIds"] .location-kind-badge').count(),1);
  assert.ok((await page.locator('[data-summary-field="locationIds"]').innerText()).includes(quarters[0].label));
  await fits(page);assert.deepEqual(errors,[]);
  console.log(`Neighborhood browser ${viewport.name}: multiple quarters + town, dismissal, persisted edit and summary passed.`);
 }catch(error){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`neighborhood-search-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}

async function addressFlow(browser,viewport){
 const context=await contextFor(browser,viewport);
 await context.route(`${origin}/runtime-config.js`,route=>route.fulfill({status:200,contentType:'text/javascript',body:'globalThis.OTTHONRA_CONFIG=Object.freeze({mode:"api",environment:"test"});'}));
 await context.addInitScript(({origin})=>localStorage.setItem('otthonra.api',JSON.stringify({baseUrl:origin,token:'mock-private-address-session'})),{origin});
 let active={kind:'search',id:'mock-search'},attempts=0,releaseFailure;
 const failureGate=new Promise(resolve=>{releaseFailure=resolve;});
 const owner={id:'mock-owner',name:'Teszt Anna',email:'anna@example.test',accountType:'private'};
 const properties=[{id:'legacy-property',ownerId:owner.id,title:'Korábbi című ingatlan',locationId:'city:Debrecen',city:'Debrecen',type:'Lakás',price:65000000,area:60,wholeRooms:2,halfRooms:0,rooms:2,address:'Korábban megadott cím 3.'}];
 const search={id:'mock-search',ownerId:owner.id,title:'Teszt keresési igény',locationIds:['city:Debrecen'],type:'Lakás',maxPrice:130000000,minArea:40,minRooms:2};
 const writes=[];
 await context.route(`${origin}/api/**`,async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname;
  const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(path==='/api/locations')return reply(searchLocations(url.searchParams.get('q'),Number(url.searchParams.get('limit'))||12,{kind:url.searchParams.get('kind')||'search'}));
  if(path==='/api/streets')return reply([]);
  if(path==='/api/me')return reply({...owner,credits:100});
  if(path==='/api/me/entities')return reply({active,properties,searches:[search],decisions:[]});
  if(path==='/api/credits/ledger'||path==='/api/matches')return reply([]);
  if(path==='/api/feedback/pending')return reply({feedbackPrompt:null});
  if(path==='/api/test/feedback-scenario')return reply({available:false});
  if(path==='/api/feed')return reply({active,items:[],stage:'empty'});
  if(path==='/api/me/active'){active=request.postDataJSON();return reply(active);}
  if(path==='/api/properties'&&request.method()==='POST'){
   const data=request.postDataJSON();writes.push(data);attempts++;
   if(attempts===1){await failureGate;return reply({message:'A címellenőrző szolgáltatás átmenetileg nem érhető el. Próbáld újra.'},502);}
   const saved={...data,id:'saved-private-property',ownerId:owner.id,neighborhood:'Újlipótváros',neighborhoodId:'mock-derived-quarter',addressDetails:{street:data.street,houseNumber:data.houseNumber,postalCode:data.postalCode,latitude:47.519,longitude:19.052,geocodedAt:'2026-11-16T12:00:00Z',provider:'google'}};
   properties.push(saved);return reply(saved,201);
  }
  return reply({message:`Unexpected mock endpoint: ${path}`},404);
 });
 const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);
 const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await openNew(page,interact,'property');
  await page.locator('#f-title').fill(`Pontos című otthon – ${viewport.name}`);
  await query(page,'Újlipótváros');assert.equal(await page.locator('[data-location-id^="neighborhood:"]').count(),0,'A property never selects a quarter');
  await query(page,'Budapest 13');await choose(page,interact,'district:Budapest:13');
  assert.equal(await page.locator('input[name="neighborhood"],input[name="latitude"],input[name="longitude"]').count(),0);
  await interact(page.locator('#editor-next'));assert.equal(await page.locator('#editor-step-0').isVisible(),true);assert.equal(await page.locator('#f-street').evaluate(element=>element.validity.valid),false);
  await page.locator('#f-street').fill('Pozsonyi út');await interact(page.locator('#editor-next'));assert.equal(await page.locator('#editor-step-0').isVisible(),true);assert.equal(await page.locator('#f-houseNumber').evaluate(element=>element.validity.valid),false);
  await page.locator('#f-houseNumber').fill('12/A');assert.equal(await page.locator('#f-houseNumber').getAttribute('type'),'text');
  const postal=page.locator('#f-postalCode');assert.equal(await postal.getAttribute('inputmode'),'numeric');
  await postal.fill('113');await interact(page.locator('#editor-next'));assert.equal(await page.locator('#editor-step-0').isVisible(),true);assert.equal(await postal.evaluate(element=>element.validity.valid),false);
  await postal.fill('');await interact(page.locator('#editor-next'));assert.equal(await page.locator('#editor-step-1').isVisible(),true,'Postal code stays optional');
  await editorStep(page,0,interact);await postal.fill('1137');
  const geometry=await page.locator('.property-address-row').evaluate(row=>[...row.querySelectorAll('input')].map(input=>input.getBoundingClientRect().top));
  assert.ok(Math.abs(geometry[0]-geometry[1])<=1,'Address inputs align even when mobile labels wrap');
  await (await editorField(page,'#f-price')).fill('85');await (await editorField(page,'#f-area')).fill('65');await (await editorField(page,'#f-wholeRooms')).fill('2');await (await editorField(page,'#f-halfRooms')).fill('1');
  await (await editorField(page,'#f-insulated')).selectOption('false');
  await fits(page);await editorSave(page,interact);
  await page.locator('#entity-form[aria-busy="true"]').waitFor();assert.equal(await page.locator('#editor-save').isDisabled(),true);assert.match(await page.locator('#editor-save-status').innerText(),/cím ellenőrzése/);
  assert.equal(properties.length,1,'A pending provider response must not announce a saved profile');
  releaseFailure();await page.locator('#editor-save-status.is-error').waitFor();
  assert.match(await page.locator('#editor-save-status').innerText(),/mentés nem sikerült.*címellenőrző/s);assert.equal(await page.locator('#editor-save').isEnabled(),true);
  assert.equal(await page.locator('#f-street').inputValue(),'Pozsonyi út');assert.equal(await page.locator('#f-houseNumber').inputValue(),'12/A');assert.equal(properties.length,1);
  await interact(page.locator('#editor-save'));await page.locator('#entity-form').waitFor({state:'detached'});
  assert.equal(writes.length,2);assert.equal(writes[1].street,'Pozsonyi út');assert.equal(writes[1].houseNumber,'12/A');assert.equal(writes[1].postalCode,'1137');
  for(const key of ['latitude','longitude','neighborhood','neighborhoodId'])assert.equal(Object.hasOwn(writes[1],key),false,`Client must not invent ${key}`);
  const saved=(await apiState(page)).properties.find(item=>item.id==='saved-private-property');assert.ok(saved);assert.equal(saved.insulated,false);
  await interact(page.locator('[data-action="edit"][data-id="saved-private-property"]'));assert.equal(await page.locator('#f-street').inputValue(),'Pozsonyi út');assert.equal(await page.locator('#f-houseNumber').inputValue(),'12/A');assert.equal(await page.locator('#f-postalCode').inputValue(),'1137');assert.match(await page.locator('.derived-neighborhood').innerText(),/Újlipótváros/);await closeModal(page,interact);
  await interact(page.locator('[data-action="activate-one"][data-id="saved-private-property"]'));await page.locator('.filter-button').waitFor();await interact(page.locator('.filter-button'));
  assert.match(await page.locator('[data-summary-field="address"]').innerText(),/1137.*Pozsonyi út 12\/A/);assert.match(await page.locator('[data-summary-field="neighborhood"]').innerText(),/Újlipótváros/);assert.doesNotMatch(await page.locator('.criteria-summary').innerText(),/47\.519|19\.052/);await fits(page);await closeModal(page,interact);
  await page.goto(`${origin}/#properties`,{waitUntil:'domcontentloaded'});await interact(page.locator('[data-action="edit"][data-id="legacy-property"]'));
  assert.equal(await page.locator('#f-street').inputValue(),'');assert.equal(await page.locator('#f-houseNumber').inputValue(),'');assert.match(await page.locator('#address-update-note').innerText(),/egészítsd ki/);await interact(page.locator('#editor-next'));assert.equal(await page.locator('#editor-step-0').isVisible(),true);
  assert.deepEqual(errors,[]);
  console.log(`Address browser ${viewport.name}: required exact address, optional postcode, provider wait/failure/retry, saved owner address and legacy update passed (mock API).`);
 }catch(error){releaseFailure();await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`neighborhood-address-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{releaseFailure();await context.close();}
}

const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports){await searchFlow(browser,viewport);await addressFlow(browser,viewport);}}finally{await browser.close();}
