/** Real-browser optional attributes: multi-choice persistence and seller tri-state values. */
import {mockMapTiles} from './map-browser-network.mjs';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {editorField,editorSave,editorStep,choosePropertyType,setAttributeChoice,fillRoomBound} from './editor-browser-helpers.mjs';

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
  await (await editorField(page,'#f-maxPrice')).fill('100');await (await editorField(page,'#f-minArea')).fill('40');await fillRoomBound(page,'minRooms','1',interact);
  for(const [name,values] of Object.entries({conditions:['Jó','Új/felújított'],buildings:['Tégla','Panel'],constructionAges:['10 évnél fiatalabb','10–30 év közötti'],views:['Kertre néző','Panorámás'],floors:['-1','0','0.5','9']})){
   for(const value of values)await (await editorField(page,`input[name="${name}"][value="${value}"]`)).check();
  }
  await setAttributeChoice(page,'ceilingHeight','3 m feletti',interact);
  for(const name of ['excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden'])await (await editorField(page,`#f-${name}`)).check();
  const geometry=await page.locator('.modal').evaluate(element=>({width:element.clientWidth,scrollWidth:element.scrollWidth}));
  assert.ok(geometry.scrollWidth<=geometry.width+1,'Attribute choices must fit the modal without horizontal scrolling');
  await (await editorField(page,'#f-title')).fill(searchTitle);await save(page,interact,true);
  let saved=(await state(page)).searches.find(value=>value.title===searchTitle);assert.ok(saved);
  assert.deepEqual(saved.conditions,['Jó','Új/felújított']);assert.deepEqual(saved.buildings,['Tégla','Panel']);assert.deepEqual(saved.views,['Kertre néző','Panorámás']);assert.deepEqual(saved.floors,[-1,0,0.5,9]);assert.equal(saved.ceilingHeight,'3 m feletti');assert.equal(saved.sharedGarden,false,'A retired criterion cannot silently constrain the saved search');for(const name of ['excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden'])assert.equal(saved[name],true);
  await edit(page,interact,'search',saved.id);
  assert.equal(await page.locator('input[name="conditions"][value="Jó"]').isChecked(),true);
  assert.equal(await page.locator('input[name="floors"][value="-1"]').isChecked(),true);
  assert.equal(await page.locator('#f-ceilingHeight').inputValue(),'3 m feletti');
  for(const input of await page.locator('.attribute-group input[type="checkbox"]').all())await (await editorField(page,`#${await input.getAttribute('id')}`)).uncheck();
  await setAttributeChoice(page,'ceilingHeight','',interact);for(const name of ['excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden'])await (await editorField(page,`#f-${name}`)).uncheck();await save(page,interact);
  saved=(await state(page)).searches.find(value=>value.id===saved.id);
  for(const name of ['conditions','buildings','constructionAges','views','floors'])assert.deepEqual(saved[name],[]);
  assert.equal(saved.ceilingHeight,'');for(const name of ['excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden'])assert.equal(saved[name],false);
  await openNew(page,interact,'property');await location(page,interact);await page.locator('#f-street').fill('Teszt utca');await page.locator('#f-houseNumber').fill('12/A');
  const propertyTitle=`Opcionális ingatlanadatok – ${viewport.name}`;await choosePropertyType(page,'Lakás',interact);assert.equal(await page.locator('#f-sharedGarden').count(),0,'Shared garden is no longer an available form criterion');
  await (await editorField(page,'#f-price')).fill('85');await (await editorField(page,'#f-area')).fill('65');await (await editorField(page,'#f-wholeRooms')).fill('3');await (await editorField(page,'#f-halfRooms')).fill('0');
  for(const name of ['condition','building','constructionAge','view','ceilingHeight','floor','buildingFloors','insulated','airConditioning','solarPanels','privateGarden'])assert.equal(await page.locator(`#f-${name}`).inputValue(),'');
  await (await editorField(page,'#f-title')).fill(propertyTitle);await save(page,interact);
  let property=(await state(page)).properties.find(value=>value.title===propertyTitle);assert.ok(property);
  for(const name of ['floor','buildingFloors','insulated','airConditioning','solarPanels','privateGarden'])assert.equal(property[name],null);
  await edit(page,interact,'property',property.id);
  for(const [name,value] of Object.entries({condition:'Új/felújított',building:'Csúsztatott zsalu',view:'Kertre néző',ceilingHeight:'3 m alatti'}))await setAttributeChoice(page,name,value,interact);
  for(const [name,value] of Object.entries({constructionAge:'10–30 év közötti',floor:'-1',insulated:'false',airConditioning:'true',solarPanels:'',privateGarden:'true'}))await (await editorField(page,`#f-${name}`)).selectOption(value);
  await (await editorField(page,'#f-buildingFloors')).fill('4');
  await (await editorField(page,'#f-heatingType')).selectOption('Hőszivattyú');await (await editorField(page,'#f-secondaryHeatingType')).selectOption('Klíma');await (await editorField(page,'#f-energyRating')).fill('A+');await (await editorField(page,'input[name="parkingTypes"][value="Udvari beálló"]')).check();await (await editorField(page,'input[name="parkingTypes"][value="Garázs"]')).check();
  await save(page,interact);
  property=(await state(page)).properties.find(value=>value.id===property.id);
  assert.equal(property.floor,-1);assert.equal(property.insulated,false);assert.equal(property.airConditioning,true);assert.equal(property.solarPanels,null);assert.equal(property.heatingType,'Hőszivattyú');assert.equal(property.secondaryHeatingType,'Klíma');assert.equal(property.energyRating,'A+');assert.deepEqual(property.parkingTypes,['Udvari beálló','Garázs']);assert.equal(property.wholeRooms,3);assert.equal(property.halfRooms,0);assert.equal(property.rooms,3);assert.equal(property.buildingFloors,4);assert.equal(property.privateGarden,true);assert.equal(property.sharedGarden,null);
  await edit(page,interact,'property',property.id);
  assert.equal(await page.locator('#f-floor').inputValue(),'-1');assert.equal(await page.locator('#f-insulated').inputValue(),'false');assert.equal(await page.locator('#f-airConditioning').inputValue(),'true');assert.equal(await page.locator('#f-solarPanels').inputValue(),'');
  assert.equal(await page.locator('#f-building').inputValue(),'Csúsztatott zsalu');assert.equal(await page.locator('#f-heatingType').inputValue(),'Hőszivattyú');assert.equal(await page.locator('#f-secondaryHeatingType').inputValue(),'Klíma');assert.equal(await page.locator('input[name="parkingTypes"][value="Udvari beálló"]').isChecked(),true);assert.equal(await page.locator('input[name="parkingTypes"][value="Garázs"]').isChecked(),true);assert.equal(await page.locator('#f-wholeRooms').inputValue(),'3');assert.equal(await page.locator('#f-halfRooms').inputValue(),'0');
  assert.equal(await page.locator('#f-buildingFloors').inputValue(),'4');assert.equal(await page.locator('#f-privateGarden').inputValue(),'true');assert.equal(await page.locator('#f-sharedGarden').count(),0);
  const floor=await editorField(page,'#f-floor',interact);
  assert.deepEqual(await floor.locator('option:not([hidden])').evaluateAll(options=>options.map(option=>option.value)),['','-1','0','0.5','1','2','3','4','5','6','7','8','9']);
  assert.match(await floor.locator('option[value="0.5"]').innerText(),/Magasföldszint/);assert.match(await floor.locator('option[value="9"]').innerText(),/9.*afölötti/);
  await floor.selectOption('0.5');await (await editorField(page,'#f-buildingFloors')).fill('0');await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.equal(property.floor,0.5);assert.equal(property.floorIsUpperRange,false);assert.equal(property.buildingFloors,0,'A raised ground-only building remains valid');
  await edit(page,interact,'property',property.id);assert.equal(await page.locator('#f-floor').inputValue(),'0.5');await (await editorField(page,'#f-floor')).selectOption('9');await (await editorField(page,'#f-buildingFloors')).fill('12');await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.equal(property.floor,9);assert.equal(property.floorIsUpperRange,true,'The new ninth-or-higher choice must retain its range semantics');
  // Arrange an old exact-floor record; new users only see the capped dropdown.
  await page.evaluate(async id=>{const {STORAGE_KEY}=await import('/model.js'),raw=JSON.parse(localStorage.getItem(STORAGE_KEY)),legacy=raw.properties.find(item=>item.id===id);Object.assign(legacy,{floor:12,buildingFloors:12,floorIsUpperRange:false});localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));},property.id);await page.reload({waitUntil:'domcontentloaded'});
  await edit(page,interact,'property',property.id);assert.equal(await page.locator('#f-floor').inputValue(),'12');assert.equal(await page.locator('#f-floor option[value="12"]').evaluate(option=>option.hidden),true,'The old exact floor may be retained without offering it as a new range choice');assert.equal(await page.locator('#f-floorIsUpperRange').inputValue(),'false');await (await editorField(page,'#f-energyRating')).fill('A++');await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.equal(property.floor,12,'Unchanged legacy exact floors must not be collapsed to the new upper bucket');assert.equal(property.floorIsUpperRange,false);
  await edit(page,interact,'property',property.id);assert.equal(await page.locator('#f-floor').inputValue(),'12');assert.equal(await page.locator('#f-buildingFloors').inputValue(),'12');assert.equal(await page.locator('#f-privateGarden').inputValue(),'true');assert.equal(await page.locator('#f-sharedGarden').count(),0);
  await editorStep(page,3,interact);const wallBefore=await page.locator('#f-building').inputValue();await interact(page.locator('#building-help-property-2'));await page.locator('#building-help-panel').waitFor();assert.match(await page.locator('#building-help-title').innerText(),/Csúsztatott zsalu/);assert.ok((await page.locator('#building-help-content').innerText()).trim().length>20);assert.equal(await page.locator('#f-building').inputValue(),wallBefore,'Reading masonry information must not choose or clear an option');await interact(page.locator('#building-help-close'));await page.locator('#building-help-panel').waitFor({state:'hidden'});
  for(const name of ['condition','building','view','ceilingHeight']){const value=await page.locator(`#f-${name}`).inputValue();const card=await editorField(page,`[data-attribute-name="${name}"][data-attribute-value="${value}"]`,interact);assert.equal(await card.getAttribute('aria-pressed'),'true');await interact(card);assert.equal(await page.locator(`#f-${name}`).inputValue(),'','Clicking the selected optional card must clear its value');assert.equal(await card.getAttribute('aria-pressed'),'false');}
  await (await editorField(page,'#f-buildingFloors')).fill('');for(const name of ['privateGarden'])await (await editorField(page,`#f-${name}`)).selectOption('');await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);for(const name of ['condition','building','view','ceilingHeight'])assert.equal(property[name],'');for(const name of ['buildingFloors','privateGarden'])assert.equal(property[name],null);
  assert.deepEqual(errors,[],'Optional attribute forms must not emit frontend errors');
  console.log(`Attributes browser ${viewport.name}: optional defaults, multiple selections, reload/edit persistence, clearing, basement and true/false/unknown amenities passed.`);
 }catch(error){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`attributes-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports)await verify(browser,viewport);}finally{await browser.close();}
