/** Street picker regressions. Postal rows below are isolated mock API fixtures. */
import {mockMapTiles} from './map-browser-network.mjs';
import assert from 'node:assert/strict';
import {mkdir,readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {editorField,editorSave,editorStep,choosePropertyType,selectedLocationText,fillRoomBound} from './editor-browser-helpers.mjs';
import {getLocation,searchLocations,registerLocations} from '../dist/locations.js';

const street=(digit,streetName,city,postalCodes,district=null)=>({id:`street:${digit.repeat(24)}`,label:`${streetName} (${city}${district?' '+district+' kerület':''})`,city,district,kind:'street',streetName,postalCodes,settlementCount:null});
const csapo=street('a','Csapó utca','Debrecen',['4024','4029']);
const sameName=street('b','Csapó utca','Nyíregyháza',['4400']);
const unique=street('c','Fő utca','Debrecen',['4024']);
const budapest=street('d','Teszt köz','Budapest',['1051'],'V.');
const fixtures=[csapo,sameName,unique,budapest];
const settle=async()=>{for(let index=0;index<24;index++)await Promise.resolve();};

// The offline mode reuses the existing small DOM fixture without running its
// test cases. It verifies races and payloads where a local listener is denied.
async function offline(){
 registerLocations(fixtures);
 const fixtureUrl=new URL('./frontend.test.mjs',import.meta.url);
 let harness=(await readFile(fixtureUrl,'utf8')).split("test('initial app renders")[0];
 harness=harness.replaceAll('import.meta.url',JSON.stringify(fixtureUrl.href)).replace(/from '([^']+)'/g,(match,specifier)=>specifier.startsWith('.')?`from '${new URL(specifier,fixtureUrl).href}'`:match);
 harness+='\nexport {setup,chooseLocation,key,submitEntity,settle};';
 const {setup,chooseLocation,key,submitEntity}=await import('data:text/javascript;base64,'+Buffer.from(harness).toString('base64'));
 const pick=(list,id)=>{const target={dataset:{locationId:id},closest:()=>target};list.handlers.click({target});};
 const type=(input,value)=>{input.value=value;input.handlers.input();};
 const values={title:'Utcaválasztós ingatlan',street:csapo.streetName,houseNumber:'12/A',postalCode:'',type:'Lakás',price:'65',area:'60',wholeRooms:'2',halfRooms:'0',floor:'',images:''};
 let releaseOld,releaseNew,saved;
 const search=await setup({hosted:true,authenticated:true,captureTimers:true,apiOverrides:{findLocations:query=>new Promise(resolve=>{if(query==='régi')releaseOld=resolve;else releaseNew=resolve;}),saveEntity:async(kind,data)=>{saved={kind,...data,id:'saved-street-search'};return saved;}}});
 search.ui.openEditor('search');const input=search.document.getElementById('location-input'),list=search.document.getElementById('location-options');
 type(input,'régi');search.runTimers();await settle();type(input,'Csapó');search.runTimers();await settle();
 releaseOld([unique]);await settle();assert.doesNotMatch(list.innerHTML,/Fő utca/);assert.equal(input.value,'Csapó');
 releaseNew([csapo,sameName]);await settle();assert.match(list.innerHTML,/Csapó utca \(Debrecen\)/);assert.match(list.innerHTML,/Csapó utca \(Nyíregyháza\)/);assert.equal((list.innerHTML.match(/>Utca</g)||[]).length,2);
 key(input,'ArrowDown');key(input,'Enter');type(input,'Csapó');search.runTimers();await settle();releaseNew([csapo,sameName]);await settle();pick(list,sameName.id);
 submitEntity(search,{title:'Két város azonos utcaneve',type:'Lakás',maxPrice:'90',minArea:'40',minRooms:'2'});await settle();assert.deepEqual([...saved.locationIds],[csapo.id,sameName.id]);assert.equal(saved.kind,'search');

 let pending,streetCalls=[];
 const property=await setup({hosted:true,authenticated:true,captureTimers:true,apiOverrides:{findStreets:(query,locationId)=>{streetCalls.push({query,locationId});if(query==='lassú')return new Promise(resolve=>{pending=resolve;});return Promise.resolve(locationId==='city:Debrecen'?[csapo,unique]:[sameName]);},saveEntity:async(kind,data)=>{saved={kind,...data,id:'saved-street-property'};return saved;}}});
 property.ui.openEditor('property');chooseLocation(property,'city:Debrecen');
 const address=property.document.getElementById('f-street'),streets=property.document.getElementById('street-options'),house=property.document.getElementById('f-houseNumber'),postal=property.document.getElementById('f-postalCode');
 house.value='12/A';postal.value='9999';type(address,'Csa');property.runTimers();await settle();pick(streets,csapo.id);assert.equal(address.value,'Csapó utca');assert.equal(house.value,'12/A');assert.equal(postal.value,'9999');
 postal.value='';type(address,'Csa');property.runTimers();await settle();pick(streets,csapo.id);assert.equal(postal.value,'','Multiple postcodes must not fill a guessed code');
 type(address,'Fő');property.runTimers();await settle();pick(streets,unique.id);assert.equal(postal.value,'4024');
 type(address,'lassú');property.runTimers();await settle();chooseLocation(property,'city:Nyíregyháza');pending([csapo]);await settle();assert.equal(streets.hidden,true);assert.equal(address.value,'lassú');assert.equal(house.value,'12/A');assert.equal(postal.value,'4024');
 type(address,'Csapó');property.runTimers();await settle();pick(streets,sameName.id);assert.equal(streetCalls.at(-1).locationId,'city:Nyíregyháza');
 type(address,'Új, szabadon megadott köz');property.document.handlers.focusin({target:house});assert.equal(streets.hidden,true);assert.equal(address.value,'Új, szabadon megadott köz');
 submitEntity(property,{...values,street:address.value,postalCode:'4024'});await settle();assert.equal(saved.streetId,null,'Typing another name must clear the old canonical association');assert.equal(saved.street,'Új, szabadon megadott köz');assert.equal(saved.houseNumber,'12/A');assert.equal(saved.locationId,'city:Nyíregyháza');

 const canonical=await setup({hosted:true,authenticated:true,captureTimers:true,apiOverrides:{findStreets:async()=>[csapo],saveEntity:async(kind,data)=>{saved=data;return {...data,id:'canonical-property'};}}});
 canonical.ui.openEditor('property');chooseLocation(canonical,'city:Debrecen');const canonicalInput=canonical.document.getElementById('f-street');type(canonicalInput,'Csa');canonical.runTimers();await settle();pick(canonical.document.getElementById('street-options'),csapo.id);submitEntity(canonical,values);await settle();assert.equal(saved.streetId,csapo.id);

 const changedCity=await setup({hosted:true,authenticated:true,captureTimers:true,apiOverrides:{findStreets:async()=>[csapo],saveEntity:async(kind,data)=>{saved=data;return {...data,id:'changed-city-property'};}}});
 changedCity.ui.openEditor('property');chooseLocation(changedCity,'city:Debrecen');type(changedCity.document.getElementById('f-street'),'Csa');changedCity.runTimers();await settle();pick(changedCity.document.getElementById('street-options'),csapo.id);chooseLocation(changedCity,'city:Nyíregyháza');submitEntity(changedCity,values);await settle();assert.equal(saved.streetId,null,'Changing only the city must clear the street association even when the street text stays unchanged');assert.equal(saved.street,csapo.streetName);

 const capital=await setup({hosted:true,authenticated:true,captureTimers:true,apiOverrides:{findStreets:async()=>[budapest],saveEntity:async(kind,data)=>{saved=data;return {...data,id:'capital-property'};}}});
 capital.ui.openEditor('property');chooseLocation(capital,'city:Budapest');type(capital.document.getElementById('f-street'),'Teszt');capital.runTimers();await settle();pick(capital.document.getElementById('street-options'),budapest.id);assert.match(capital.document.getElementById('location-chips').innerHTML,/Budapest V\. kerület/);submitEntity(capital,{...values,street:budapest.streetName,postalCode:'1051'});await settle();assert.equal(saved.locationId,'district:Budapest:5');assert.equal(saved.streetId,budapest.id);

 const bounded=await setup({hosted:true,authenticated:true,captureTimers:true,apiOverrides:{findLocations:async query=>[{...csapo,id:`street:${Number(query).toString(16).padStart(24,'0')}`,label:`Teszt ${query} utca (Debrecen)`}]}});
 bounded.ui.openEditor('search');const boundedInput=bounded.document.getElementById('location-input'),boundedList=bounded.document.getElementById('location-options');
 for(let index=1;index<=51;index++){type(boundedInput,String(index));bounded.runTimers();await settle();pick(boundedList,`street:${index.toString(16).padStart(24,'0')}`);}
 assert.equal((bounded.document.getElementById('location-chips').innerHTML.match(/data-remove-location=/g)||[]).length,50);assert.match(bounded.document.getElementById('location-error').textContent,/50/);

 let requests=0,releaseClosed;
 const failure=await setup({hosted:true,authenticated:true,captureTimers:true,apiOverrides:{findLocations:()=>++requests===1?Promise.reject(new Error('offline')):new Promise(resolve=>{releaseClosed=resolve;})}});
 failure.ui.openEditor('search');const failedInput=failure.document.getElementById('location-input'),failedList=failure.document.getElementById('location-options');type(failedInput,'Csapó');failure.runTimers();await settle();assert.match(failedList.innerHTML,/Újrapróbálom/);assert.equal(failedInput.value,'Csapó');assert.doesNotMatch(failedList.innerHTML,/data-location-id/);
 const retry={dataset:{pickerRetry:'true'},closest:()=>retry};failedList.handlers.click({target:retry});failure.runTimers();await settle();failure.ui.closeModal();releaseClosed([csapo]);await settle();assert.equal(failure.document.getElementById('entity-form'),null);assert.equal(failedList.hidden,true);
 console.log('Street UI offline: asynchronous races, multi-city selection, canonical payloads, city changes, free text, postcodes, retry and closed-modal responses passed.');
}

async function browserTests(){
 const modulePath=process.env.PLAYWRIGHT_MODULE;
 const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
 const {chromium}=await import(playwrightUrl),origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
 const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
 const browser=await chromium.launch({headless:true});
 try{for(const viewport of viewports){
  const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
  await mockMapTiles(context);
  await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
  await context.route(`${origin}/runtime-config.js`,route=>route.fulfill({status:200,contentType:'text/javascript',body:'globalThis.OTTHONRA_CONFIG=Object.freeze({mode:"api",environment:"test"});'}));
  await context.addInitScript(({origin})=>localStorage.setItem('otthonra.api',JSON.stringify({baseUrl:origin,token:'mock-street-session'})),{origin});
  const owner={id:'street-owner',name:'Teszt Anna',email:'anna@example.test',accountType:'private'},properties=[],searches=[{id:'existing-search',ownerId:'street-owner',title:'Aktív keresés',locationIds:['city:Debrecen'],type:'Lakás',maxPrice:100000000,minArea:40,minRooms:2}],writes=[],lookupCalls=[],pending=[];
  let active={kind:'search',id:'existing-search'},failNext=true;
  const selectedMetadata=ids=>ids.map(id=>fixtures.find(item=>item.id===id)||getLocation(id)).filter(Boolean);
  await context.route(`${origin}/api/**`,async route=>{
   const request=route.request(),url=new URL(request.url()),path=url.pathname;
   const reply=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
   if(path==='/api/me')return reply({...owner,credits:100});
   if(path==='/api/me/entities')return reply({active,properties,searches,decisions:[]});
   if(path==='/api/credits/ledger'||path==='/api/matches')return reply([]);
   if(path==='/api/feedback/pending')return reply({feedbackPrompt:null});
   if(path==='/api/test/feedback-scenario')return reply({available:false});
   if(path==='/api/feed')return reply({active,items:[],stage:'empty'});
   if(path==='/api/locations'||path==='/api/streets'){
    const query=url.searchParams.get('q')||'',scope=url.searchParams.get('locationId'),kind=url.searchParams.get('kind');lookupCalls.push({path,query,scope,kind});
    if(query==='lassú')return new Promise(resolve=>pending.push(async()=>{await reply([csapo]);resolve();}));
    if(query==='hiba'&&failNext){failNext=false;return reply({message:'Átmeneti teszthiba'},503);}
    if(path==='/api/locations')return reply(/csap|hiba/i.test(query)?[csapo,sameName]:searchLocations(query,12,{kind:kind||'search'}));
    const location=getLocation(scope),candidates=fixtures.filter(item=>item.city===location?.city&&(!location.district||item.district===location.district));
    return reply(candidates.filter(item=>item.streetName.toLocaleLowerCase('hu').includes(query.toLocaleLowerCase('hu'))));
   }
   if(path==='/api/me/active'){active=request.postDataJSON();return reply(active);}
   if((path==='/api/searches'||path==='/api/properties'||path.startsWith('/api/properties/'))&&['POST','PUT'].includes(request.method())){
    const data=request.postDataJSON(),property=path.startsWith('/api/properties');writes.push({kind:property?'property':'search',...data});
    const saved={...data,id:property?(path.split('/')[3]||`property-${properties.length+1}`):`search-${searches.length+1}`,ownerId:owner.id};
    if(property){saved.addressDetails={street:data.street,streetId:data.streetId,houseNumber:data.houseNumber,postalCode:data.postalCode};const old=properties.findIndex(item=>item.id===saved.id);if(old>=0)properties[old]=saved;else properties.push(saved);}else{saved.locations=selectedMetadata(data.locationIds);searches.push(saved);}return reply(saved,request.method()==='POST'?201:200);
   }
   return reply({message:`Unexpected mock endpoint: ${path}`},404);
  });
  const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);
  const interact=locator=>viewport.touch?locator.tap():locator.click();
  const query=async(value,street=false)=>{await page.locator(street?'#f-street':'#location-input').fill(value);await page.locator(street?'#street-options':'#location-options').waitFor({state:'visible'});};
  const choose=async(id,street=false)=>interact(page.locator(`${street?'#street-options':'#location-options'} [data-location-id="${id}"]`));
  const open=async kind=>{await page.goto(`${origin}/#${kind==='property'?'properties':'searches'}`,{waitUntil:'domcontentloaded'});await interact(page.locator(`.page-heading [data-action="new"][data-kind="${kind}"]`));await page.waitForFunction(()=>document.activeElement?.closest('[data-editor-step]')?.dataset.editorStep==='0');};
  const close=async()=>{await interact(page.locator('.modal-close'));await page.locator('#entity-form').waitFor({state:'detached'});};
  try{
   await open('search');assert.equal(lookupCalls.length,0,'Opening an editor must not download the street catalogue');
   await query('Csapó');await page.locator(`#location-options [data-location-id="${sameName.id}"]`).waitFor();assert.equal(await page.locator('#location-options .location-kind-badge').count(),2);
   const geometry=await page.evaluate(()=>({input:document.getElementById('location-input').getBoundingClientRect().toJSON(),list:document.getElementById('location-options').getBoundingClientRect().toJSON()}));assert.ok(geometry.list.top>=geometry.input.bottom,'The visible query must remain above its suggestions');
   await page.locator('#location-input').press('ArrowDown');await page.locator('#location-input').press('Enter');await query('Csapó');await choose(sameName.id);await query('Debrecen');await choose('city:Debrecen');
   await choosePropertyType(page,'Lakás',interact);await (await editorField(page,'#f-maxPrice')).fill('100');await (await editorField(page,'#f-minArea')).fill('40');await fillRoomBound(page,'minRooms','1',interact);await (await editorField(page,'#f-title')).fill(`Utcák két városban – ${viewport.name}`);await editorSave(page,interact);await page.getByRole('heading',{name:'Elkészült a keresési igényed.',exact:true}).waitFor();assert.deepEqual(writes.at(-1).locationIds,[csapo.id,sameName.id,'city:Debrecen']);assert.deepEqual(active,{kind:'search',id:'existing-search'});
   await interact(page.locator('.search-created-actions [data-action="close"]'));await page.reload({waitUntil:'domcontentloaded'});await interact(page.locator('[data-action="edit"][data-kind="search"][data-id="search-2"]'));assert.equal(await page.locator('#location-chips .location-kind-badge').count(),2);assert.match(await selectedLocationText(page,interact),/Nyíregyháza/);await close();
   await open('search');await query('lassú');await page.waitForFunction(()=>document.getElementById('location-options')?.getAttribute('aria-busy')==='true');await page.waitForTimeout(250);await query('Debrecen');await page.locator('[data-location-id="city:Debrecen"]').waitFor();for(const release of pending.splice(0))await release();assert.equal(await page.locator('#location-options [data-location-id^="street:"]').count(),0);assert.equal(await page.locator('#location-input').inputValue(),'Debrecen');
   await interact(page.locator('#editor-heading-0'));assert.equal(await page.locator('#location-options').isHidden(),true);assert.equal(await page.locator('#location-input').inputValue(),'Debrecen');await page.locator('#location-input').focus();await page.locator('#location-options').waitFor({state:'visible'});await page.locator('#location-input').press('Escape');assert.equal(await page.locator('#location-options').isHidden(),true);assert.equal(await page.locator('#entity-form').isVisible(),true);
   await query('hiba');await page.getByRole('button',{name:'Újrapróbálom',exact:true}).waitFor();assert.equal(await page.locator('#location-input').inputValue(),'hiba');await interact(page.getByRole('button',{name:'Újrapróbálom',exact:true}));await page.locator(`[data-location-id="${csapo.id}"]`).waitFor();await close();

   await open('property');await query('Csapó');await page.waitForTimeout(300);assert.equal(await page.locator('#location-options [data-location-id^="street:"]').count(),0,'A street cannot become the property city');await query('Debrecen');await choose('city:Debrecen');
   await page.locator('#f-houseNumber').fill('12/A');await page.locator('#f-postalCode').fill('9999');await query('Csapó',true);await choose(csapo.id,true);assert.equal(await page.locator('#f-houseNumber').inputValue(),'12/A');assert.equal(await page.locator('#f-postalCode').inputValue(),'9999');
   await page.locator('#f-postalCode').fill('');await query('Csa',true);await choose(csapo.id,true);assert.equal(await page.locator('#f-postalCode').inputValue(),'');await query('Fő',true);await page.locator('#f-street').press('ArrowDown');await page.locator(`#street-options [data-location-id="${unique.id}"]`).waitFor();await page.locator('#f-street').press('ArrowDown');await page.locator('#f-street').press('Enter');assert.equal(await page.locator('#f-postalCode').inputValue(),'4024');
   await choosePropertyType(page,'Lakás',interact);await (await editorField(page,'#f-price')).fill('65');await (await editorField(page,'#f-area')).fill('60');await (await editorField(page,'#f-wholeRooms')).fill('2');await (await editorField(page,'#f-halfRooms')).fill('0');await (await editorField(page,'#f-title')).fill(`Utcajavaslatos otthon – ${viewport.name}`);await editorSave(page,interact);await page.locator('#entity-form').waitFor({state:'detached'});assert.equal(writes.at(-1).streetId,unique.id);assert.equal(writes.at(-1).street,'Fő utca');assert.equal(writes.at(-1).houseNumber,'12/A');
   await interact(page.locator('[data-action="edit"][data-kind="property"][data-id="property-1"]'));assert.equal(await page.locator('#f-street').inputValue(),'Fő utca');await query('lassú',true);await page.waitForTimeout(250);await query('Nyíregyháza');await choose('city:Nyíregyháza');for(const release of pending.splice(0))await release();assert.equal(await page.locator('#street-options').isHidden(),true);assert.equal(await page.locator('#f-street').inputValue(),'lassú');assert.equal(await page.locator('#f-houseNumber').inputValue(),'12/A');
   await query('Csapó',true);await choose(sameName.id,true);await query('Szabadon megadott új köz',true);await page.locator('#f-street').press('Escape');assert.equal(await page.locator('#street-options').isHidden(),true);await editorSave(page,interact);await page.locator('#entity-form').waitFor({state:'detached'});assert.equal(writes.at(-1).streetId??null,null);assert.equal(writes.at(-1).street,'Szabadon megadott új köz');assert.equal(writes.at(-1).locationId,'city:Nyíregyháza');
   await open('property');await query('Budapest');await choose('city:Budapest');await query('Teszt',true);await choose(budapest.id,true);assert.match(await page.locator('#location-chips').innerText(),/Budapest V\. kerület/);assert.equal(await page.locator('#f-postalCode').inputValue(),'1051');await query('lassú',true);await page.waitForTimeout(250);await close();for(const release of pending.splice(0))await release();assert.equal(await page.locator('#entity-form').count(),0);
   assert.ok(lookupCalls.filter(call=>call.path==='/api/streets').every(call=>call.scope),'Every street request must have an exact selected location scope');assert.deepEqual(errors,[]);console.log(`Street browser ${viewport.name}: search selection/hydration, races/retry, canonical/private address payloads, city and Budapest district scope, postcodes and free text passed.`);
  }catch(error){await mkdir(resolve('.local/browser-tests/screenshots'),{recursive:true});await page.screenshot({path:resolve(`.local/browser-tests/screenshots/street-search-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
  finally{for(const release of pending.splice(0))await release().catch(()=>{});await context.close();}
 }}finally{await browser.close();}
}

if(process.argv.includes('--offline'))await offline();else await browserTests();
