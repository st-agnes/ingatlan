/** Real-browser optional attributes: multi-choice persistence and seller tri-state values. */
import {mockMapTiles} from './map-browser-network.mjs';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {editorField,editorSave,editorStep,choosePropertyType,setAttributeChoice,fillRoomBound,setSellerFloor,setBuildingFloors,setEnergyRating,setConstructionAge,assertAddressPrivacyControls,assertNullableAmenities,assertBuildingSelectors,setAtticPreference} from './editor-browser-helpers.mjs';

const modulePath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const screenshots=resolve('.local/browser-tests/screenshots');
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
let visit=0;
const state=page=>page.evaluate(async()=> (await import('/model.js')).model.getState());
async function location(page,interact){await (await editorField(page,'#location-input')).fill('Debrecen');await interact(page.locator('[data-location-id="city:Debrecen"]'));}
async function openNew(page,interact,kind){await page.goto(`${origin}/?attributes-visit=${++visit}#${kind==='search'?'searches':'properties'}`,{waitUntil:'domcontentloaded'});await interact(page.locator(`.page-heading [data-action="new"][data-kind="${kind}"]`));await page.waitForFunction(()=>document.activeElement?.closest('[data-editor-step]')?.dataset.editorStep==='0');}
async function edit(page,interact,kind,id){await page.goto(`${origin}/?attributes-visit=${++visit}#${kind==='search'?'searches':'properties'}`,{waitUntil:'domcontentloaded'});await interact(page.locator(`[data-action="edit"][data-id="${id}"]`));await page.waitForFunction(()=>document.activeElement?.closest('[data-editor-step]')?.dataset.editorStep==='0');}
async function save(page,interact,createdSearch=false){await editorSave(page,interact);if(createdSearch){await page.getByRole('heading',{name:'Elkészült a keresési igényed.',exact:true}).waitFor();await interact(page.locator('.search-created-actions [data-action="close"]'));}await page.locator('#entity-form').waitFor({state:'detached'});}

async function verify(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await mockMapTiles(context);
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 const page=await context.newPage();page.setDefaultTimeout(8000);page.setDefaultNavigationTimeout(15000);
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await openNew(page,interact,'search');await location(page,interact);
  const searchTitle=`Opcionális keresési szempontok – ${viewport.name}`;await choosePropertyType(page,'Lakás',interact);assert.equal(await page.locator('#f-sharedGarden').count(),0,'Shared garden is no longer an available form criterion');
  await (await editorField(page,'#f-maxPrice')).fill('100');await (await editorField(page,'#f-minArea')).fill('40');await mkdir(screenshots,{recursive:true});await page.locator('#f-publicMaxPrice').fill('70');await page.locator('.search-budget-row').screenshot({path:resolve(screenshots,`budget-fields-${viewport.name}.png`)});await page.locator('#f-publicMaxPrice').fill('100');await fillRoomBound(page,'minRooms','1',interact);
  for(const [name,values] of Object.entries({conditions:['Jó','Új/felújított'],buildings:['Tégla','Panel'],constructionAges:['10 évnél fiatalabb','10–30 év közötti'],views:['Kertre néző','Panorámás'],floors:['-1','0','0.5','9']})){
   for(const value of values)await (await editorField(page,`input[name="${name}"][value="${value}"]`)).check();
  }
  await setAttributeChoice(page,'ceilingHeight','3 m feletti',interact);await setAtticPreference(page,'exclude',interact);await setAtticPreference(page,'only',interact);await setEnergyRating(page,'B',interact,{search:true});
  await editorStep(page,4,interact);for(const name of ['balcony','airConditioning','privateGarden'])assert.equal(await page.locator('#f-'+name).isVisible(),true,'Every flat-search comfort option must be visible together');
  for(const name of ['balcony','excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden'])await (await editorField(page,`#f-${name}`)).check();
  const geometry=await page.locator('.modal').evaluate(element=>({width:element.clientWidth,scrollWidth:element.scrollWidth}));
  assert.ok(geometry.scrollWidth<=geometry.width+1,'Attribute choices must fit the modal without horizontal scrolling');
  await (await editorField(page,'#f-title')).fill(searchTitle);await save(page,interact,true);
  let saved=(await state(page)).searches.find(value=>value.title===searchTitle);assert.ok(saved);
  assert.equal(saved.atticPreference,'only');assert.equal(saved.minEnergyRating,'B');assert.deepEqual(saved.conditions,['Jó','Új/felújított']);assert.deepEqual(saved.buildings,['Tégla','Panel']);assert.deepEqual(saved.views,['Kertre néző','Panorámás']);assert.deepEqual(saved.floors,[-1,0,0.5,9]);assert.equal(saved.ceilingHeight,'3 m feletti');assert.equal(saved.sharedGarden,false,'A retired criterion cannot silently constrain the saved search');for(const name of ['balcony','excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden'])assert.equal(saved[name],true);
  await edit(page,interact,'search',saved.id);
  assert.equal(await page.locator('input[name="conditions"][value="Jó"]').isChecked(),true);
  assert.equal(await page.locator('input[name="floors"][value="-1"]').isChecked(),true);
  assert.equal(await page.locator('#f-ceilingHeight').inputValue(),'3 m feletti');
  for(const input of await page.locator('.attribute-group input[type="checkbox"]').all())await (await editorField(page,`#${await input.getAttribute('id')}`)).uncheck();
  await setAtticPreference(page,'',interact);await setEnergyRating(page,'',interact,{search:true});await setAttributeChoice(page,'ceilingHeight','',interact);for(const name of ['balcony','excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden'])await (await editorField(page,`#f-${name}`)).uncheck();await save(page,interact);
  saved=(await state(page)).searches.find(value=>value.id===saved.id);
  for(const name of ['conditions','buildings','constructionAges','views','floors'])assert.deepEqual(saved[name],[]);
  assert.equal(saved.atticPreference,'');assert.equal(saved.minEnergyRating,'');assert.equal(saved.ceilingHeight,'');for(const name of ['balcony','excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden'])assert.equal(saved[name],false);
  await openNew(page,interact,'property');await location(page,interact);await page.locator('#f-street').fill('Teszt utca');await page.locator('#f-houseNumber').fill('12/A');await assertAddressPrivacyControls(page,interact);
  const propertyTitle=`Opcionális ingatlanadatok – ${viewport.name}`;await choosePropertyType(page,'Lakás',interact);assert.equal(await page.locator('#f-sharedGarden').count(),0,'Shared garden is no longer an available form criterion');
  await (await editorField(page,'#f-price')).fill('85');await (await editorField(page,'#f-area')).fill('65');await (await editorField(page,'#f-wholeRooms')).fill('3');await (await editorField(page,'#f-halfRooms')).fill('0');
  for(const name of ['condition','building','constructionAge','view','ceilingHeight','floor','buildingFloors','insulated','airConditioning','solarPanels','privateGarden'])assert.equal(await page.locator(`#f-${name}`).inputValue(),'');
  await assertBuildingSelectors(page,interact);await mkdir(screenshots,{recursive:true});await setSellerFloor(page,'3',interact);await setBuildingFloors(page,'6',interact);await page.locator('#property-floor-field').screenshot({path:resolve(screenshots,`building-selector-selected-${viewport.name}.png`),style:'.modal-backdrop{position:absolute!important;inset:auto!important;display:block!important;padding:0!important}.modal{max-height:none!important;overflow:visible!important}html,body{overflow:visible!important}'});await setSellerFloor(page,'',interact);await setBuildingFloors(page,'',interact);await page.locator('#property-floor-field').screenshot({path:resolve(screenshots,`building-selector-${viewport.name}.png`)});await (await editorField(page,'#f-title')).fill(propertyTitle);await save(page,interact);
  let property=(await state(page)).properties.find(value=>value.title===propertyTitle);assert.ok(property);
  for(const name of ['floor','buildingFloors','insulated','airConditioning','solarPanels','privateGarden','balcony'])assert.equal(property[name],null);
  await page.evaluate(async id=>{const {STORAGE_KEY}=await import('/model.js'),raw=JSON.parse(localStorage.getItem(STORAGE_KEY));Object.assign(raw.properties.find(item=>item.id===id),{secondaryHeatingType:'Klíma',isAttic:null,energyRating:'AA',energyRatingScheme:''});localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));},property.id);
  await edit(page,interact,'property',property.id);assert.equal(await page.locator('#f-energyRating-slider').inputValue(),'0');assert.match(await page.locator('#energyRating-legacy').innerText(),/AA/);await setAttributeChoice(page,'condition','Jó',interact);await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.equal(property.isAttic,null,'An unrelated edit must not turn an unverified old attic value into No');assert.equal(property.energyRating,'AA');assert.equal(property.energyRatingScheme,'','An old certificate cannot be silently reclassified under the current scheme');
  await edit(page,interact,'property',property.id);
  await assertNullableAmenities(page,interact);await (await editorField(page,'#f-isAttic',interact)).check();
  for(const [name,value] of Object.entries({condition:'Új/felújított',building:'Csúsztatott zsalu',view:'Kertre néző',ceilingHeight:'3 m alatti'}))await setAttributeChoice(page,name,value,interact);
  await setConstructionAge(page,'10–30 év közötti',interact);await setSellerFloor(page,'-1',interact);
  for(const [name,value] of Object.entries({insulated:'false',airConditioning:'true',solarPanels:'',privateGarden:'true'}))await setAttributeChoice(page,name,value,interact);
  await setBuildingFloors(page,'4',interact);
  await setAttributeChoice(page,'heatingType','Hőszivattyú',interact);assert.equal(await page.locator('#f-secondaryHeatingType').count(),0,'Retired secondary heating has no editor control');await setEnergyRating(page,'A+',interact);await (await editorField(page,'input[name="parkingTypes"][value="Udvari beálló"]')).check();await (await editorField(page,'input[name="parkingTypes"][value="Garázs"]')).check();
  await save(page,interact);
  property=(await state(page)).properties.find(value=>value.id===property.id);
  assert.equal(property.isAttic,true);assert.equal(property.floor,-1);assert.equal(property.insulated,false);assert.equal(property.airConditioning,true);assert.equal(property.solarPanels,null);assert.equal(property.heatingType,'Hőszivattyú');assert.equal(property.secondaryHeatingType,'Klíma');assert.equal(property.energyRating,'A+');assert.equal(property.energyRatingScheme,'2023');assert.deepEqual(property.parkingTypes,['Udvari beálló','Garázs']);assert.equal(property.wholeRooms,3);assert.equal(property.halfRooms,0);assert.equal(property.rooms,3);assert.equal(property.buildingFloors,4);assert.equal(property.privateGarden,true);assert.equal(property.sharedGarden,null);
  await edit(page,interact,'property',property.id);
  assert.equal(await page.locator('#f-floor').inputValue(),'-1');assert.equal(await page.locator('#f-insulated').inputValue(),'false');assert.equal(await page.locator('#f-airConditioning').inputValue(),'true');assert.equal(await page.locator('#f-solarPanels').inputValue(),'');
  assert.equal(await page.locator('#f-building').inputValue(),'Csúsztatott zsalu');assert.equal(await page.locator('#f-heatingType').inputValue(),'Hőszivattyú');assert.equal(await page.locator('#f-secondaryHeatingType').count(),0);assert.equal(await page.locator('input[name="parkingTypes"][value="Udvari beálló"]').isChecked(),true);assert.equal(await page.locator('input[name="parkingTypes"][value="Garázs"]').isChecked(),true);assert.equal(await page.locator('#f-wholeRooms').inputValue(),'3');assert.equal(await page.locator('#f-halfRooms').inputValue(),'0');
  assert.equal(await page.locator('#f-buildingFloors').inputValue(),'4');assert.equal(await page.locator('#f-privateGarden').inputValue(),'true');assert.equal(await page.locator('#f-sharedGarden').count(),0);
  const floor=await editorField(page,'#f-floor',interact);
  assert.equal(await floor.getAttribute('type'),'hidden');
  assert.deepEqual((await page.locator('.building-floor-row[data-building-number="floor"]').evaluateAll(buttons=>buttons.map(button=>button.dataset.buildingNumberValue))).sort(),['-1','0','0.5','1','2','3','4','5','6','7','8','9','10','other'].sort());
  assert.match(await page.locator('.building-floor-row[data-building-number="floor"][data-building-number-value="0.5"]').innerText(),/Magasföldszint/);assert.match(await page.locator('.building-floor-row[data-building-number="floor"][data-building-number-value="10"]').innerText(),/10/);
  await setSellerFloor(page,'0.5',interact);await setBuildingFloors(page,'0',interact);await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.equal(property.floor,0.5);assert.equal(property.floorIsUpperRange,false);assert.equal(property.buildingFloors,0,'A raised ground-only building remains valid');
  await edit(page,interact,'property',property.id);assert.equal(await page.locator('#f-floor').inputValue(),'0.5');await setSellerFloor(page,'9',interact);await setBuildingFloors(page,'12',interact);await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.equal(property.floor,9);assert.equal(property.floorIsUpperRange,false,'A new ninth-floor card denotes the exact ninth floor');
  // An older unknown upper-floor record remains uncertain until the seller explicitly replaces it.
  await page.evaluate(async id=>{const {STORAGE_KEY}=await import('/model.js'),raw=JSON.parse(localStorage.getItem(STORAGE_KEY)),legacy=raw.properties.find(item=>item.id===id);Object.assign(legacy,{floor:9,buildingFloors:12,floorIsUpperRange:true});localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));},property.id);
  await edit(page,interact,'property',property.id);await setEnergyRating(page,'A++',interact);await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.equal(property.floor,9);assert.equal(property.floorIsUpperRange,true,'Changing an unrelated field must preserve an old unknown 9+ floor');
  await edit(page,interact,'property',property.id);await setSellerFloor(page,'12',interact);assert.equal(await page.locator('#f-floorOther').inputValue(),'12');assert.equal(await page.locator('#f-floorIsUpperRange').inputValue(),'false');await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.equal(property.floor,12,'The Other control saves the actual exact higher floor');assert.equal(property.floorIsUpperRange,false);
  await edit(page,interact,'property',property.id);assert.equal(await page.locator('#f-floor').inputValue(),'12');assert.equal(await page.locator('#f-buildingFloors').inputValue(),'12');assert.equal(await page.locator('#f-privateGarden').inputValue(),'true');assert.equal(await page.locator('#f-sharedGarden').count(),0);
  await editorStep(page,3,interact);const wallBefore=await page.locator('#f-building').inputValue();await interact(page.locator('#building-help-property-2'));await page.locator('#building-help-panel').waitFor();assert.match(await page.locator('#building-help-title').innerText(),/Csúsztatott zsalu/);assert.ok((await page.locator('#building-help-content').innerText()).trim().length>20);assert.equal(await page.locator('#f-building').inputValue(),wallBefore,'Reading masonry information must not choose or clear an option');await interact(page.locator('#building-help-close'));await page.locator('#building-help-panel').waitFor({state:'hidden'});
  for(const name of ['condition','building','view','ceilingHeight']){const value=await page.locator(`#f-${name}`).inputValue();const card=await editorField(page,`[data-attribute-name="${name}"][data-attribute-value="${value}"]`,interact);assert.equal(await card.getAttribute('aria-pressed'),'true');await interact(card);assert.equal(await page.locator(`#f-${name}`).inputValue(),'','Clicking the selected optional card must clear its value');assert.equal(await card.getAttribute('aria-pressed'),'false');}
  await setBuildingFloors(page,'',interact);for(const name of ['privateGarden'])await setAttributeChoice(page,name,'',interact);await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);for(const name of ['condition','building','view','ceilingHeight'])assert.equal(property[name],'');for(const name of ['buildingFloors','privateGarden'])assert.equal(property[name],null);
  assert.deepEqual(errors,[],'Optional attribute forms must not emit frontend errors');
  console.log(`Attributes browser ${viewport.name}: optional defaults, multiple selections, reload/edit persistence, clearing, basement and true/false/unknown amenities passed.`);
 }catch(error){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`attributes-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports)await verify(browser,viewport);}finally{await browser.close();}
