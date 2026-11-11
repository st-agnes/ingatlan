/** Real browser regression for the seller form, mobile number entry and house-specific fields. */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {editorField,editorSave,editorStep} from './editor-browser-helpers.mjs';

const modulePath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const screenshots=resolve('.local/browser-tests/screenshots');
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
let visit=0;
const state=page=>page.evaluate(async()=> (await import('/model.js')).model.getState());
async function openNew(page,interact,kind){await page.goto(`${origin}/?seller-visit=${++visit}#${kind==='property'?'properties':'searches'}`,{waitUntil:'domcontentloaded'});await interact(page.locator(`.page-heading [data-action="new"][data-kind="${kind}"]`));await page.waitForFunction(()=>document.activeElement?.id==='f-title');}
async function edit(page,interact,kind,id){await page.goto(`${origin}/?seller-visit=${++visit}#${kind==='property'?'properties':'searches'}`,{waitUntil:'domcontentloaded'});await interact(page.locator(`[data-action="edit"][data-kind="${kind}"][data-id="${id}"]`));await page.waitForFunction(()=>document.activeElement?.id==='f-title');}
async function chooseLocation(page,interact){await (await editorField(page,'#location-input')).fill('Debrecen');await interact(page.locator('[data-location-id="city:Debrecen"]'));}
async function save(page,interact,isNewSearch=false){await editorSave(page,interact);if(isNewSearch){await page.getByRole('heading',{name:'Elkészült a keresési igényed.',exact:true}).waitFor();await interact(page.locator('.search-created-actions [data-action="close"]'));}await page.locator('#entity-form').waitFor({state:'detached'});}
async function verifyNumeric(input,{integer=false}={}){
 if(!integer){for(const decimal of ['12.5','0.5']){await input.fill('');await input.pressSequentially(decimal);assert.equal(await input.inputValue(),decimal,'sequential decimal typing must preserve the fractional part');}}
 await input.fill(integer?'12':'12.5');const previous=await input.inputValue();
 for(const key of ['-','+','e']){await input.press(key);assert.equal(await input.inputValue(),previous,`${key} must not enter ${await input.getAttribute('name')}`);}
 assert.equal(await input.evaluate(element=>{const event=new InputEvent('beforeinput',{bubbles:true,cancelable:true,inputType:'insertText',data:'−15'});return !element.dispatchEvent(event);}),true,'mobile minus entry must be cancelled');
 assert.equal(await input.evaluate(element=>{const clipboardData=new DataTransfer();clipboardData.setData('text/plain','-15');const event=new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData});return !element.dispatchEvent(event);}),true,'negative pasted numbers must be cancelled');
 await input.evaluate(element=>{element.value='-15';element.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal(await input.inputValue(),previous,'drop/autofill input fallback must restore the previous number');
 await input.evaluate(element=>{element.value='1e-2';element.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal(await input.inputValue(),previous,'exponent notation must not bypass the guard');
 if(integer){await input.press('.');assert.equal(await input.inputValue(),previous,'room counts must stay integers');}
 await input.fill('');assert.equal(await input.inputValue(),'','clearing an optional bound must remain possible');
}
async function fitsModal(page){const geometry=await page.locator('.modal').evaluate(element=>({width:element.clientWidth,scrollWidth:element.scrollWidth}));assert.ok(geometry.scrollWidth<=geometry.width+1,'Seller controls must fit the modal without horizontal scrolling');}

async function verify(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 const page=await context.newPage();page.setDefaultTimeout(8000);page.setDefaultNavigationTimeout(15000);
 const errors=[];page.on('pageerror',error=>errors.push(error.message));const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await openNew(page,interact,'property');await chooseLocation(page,interact);
  const title=`Eladói űrlap – ${viewport.name}`;await (await editorField(page,'#f-title')).fill(title);
  const primaryOptions=await page.locator('#f-heatingType option').evaluateAll(options=>options.map(option=>option.value));
  assert.equal(primaryOptions.length,14);assert.ok(primaryOptions.includes('Nincs fűtés'));assert.deepEqual(await page.locator('#f-secondaryHeatingType option').evaluateAll(options=>options.map(option=>option.value)),primaryOptions);
  assert.equal(await page.locator('#f-rooms,#f-parkingType').count(),0);
  for(const name of ['price','area'])await verifyNumeric(await editorField(page,`#f-${name}`));
  for(const name of ['wholeRooms','halfRooms'])await verifyNumeric(await editorField(page,`#f-${name}`),{integer:true});
  await (await editorField(page,'#f-price')).fill('82.5');await (await editorField(page,'#f-area')).fill('64.5');await (await editorField(page,'#f-wholeRooms')).fill('0');await (await editorField(page,'#f-halfRooms')).fill('0');
  await interact(page.locator('#editor-next'));assert.equal(await page.locator('#editor-step-button-1').getAttribute('aria-current'),'step');assert.equal(await page.locator('#entity-form').count(),1);assert.equal((await state(page)).properties.some(value=>value.title===title),false,'zero rooms must not save or advance past room counts');
  await (await editorField(page,'#f-wholeRooms')).fill('2');await (await editorField(page,'#f-halfRooms')).fill('3');await (await editorField(page,'#f-floor')).selectOption('-1');await (await editorField(page,'#f-balcony')).check();await (await editorField(page,'#f-elevator')).check();
  await (await editorField(page,'#f-heatingType')).selectOption('Nincs fűtés');await (await editorField(page,'#f-secondaryHeatingType')).selectOption('Klíma');
  for(const value of ['Garázs','Udvari beálló'])await (await editorField(page,`input[name="parkingTypes"][value="${value}"]`)).check();
  await fitsModal(page);await save(page,interact);
  let property=(await state(page)).properties.find(value=>value.title===title);assert.ok(property);assert.equal(property.wholeRooms,2);assert.equal(property.halfRooms,3);assert.equal(property.rooms,3.5);assert.equal(property.floor,-1);assert.equal(property.heatingType,'Nincs fűtés');assert.equal(property.secondaryHeatingType,'Klíma');assert.deepEqual([...property.parkingTypes].sort(),['Garázs','Udvari beálló'].sort());
  await edit(page,interact,'property',property.id);assert.equal(await page.locator('#f-wholeRooms').inputValue(),'2');assert.equal(await page.locator('#f-halfRooms').inputValue(),'3');assert.equal(await page.locator('#f-heatingType').inputValue(),'Nincs fűtés');assert.equal(await page.locator('#f-secondaryHeatingType').inputValue(),'Klíma');assert.equal(await page.locator('input[name="parkingTypes"][value="Garázs"]').isChecked(),true);
  await (await editorField(page,'#f-type')).selectOption('Ház');assert.equal(await page.locator('#f-lotArea').isEnabled(),true);assert.equal(await page.locator('#f-lotArea').evaluate(element=>element.required),true);
  assert.equal(await page.locator('#property-floor-field').evaluate(element=>element.classList.contains('hidden')),true);assert.equal(await page.locator('#property-floor-field').isVisible(),false);assert.equal(await page.locator('#entity-amenities').isVisible(),false);for(const name of ['floor','balcony','elevator'])assert.equal(await page.locator(`#f-${name}`).isEnabled(),false);
  await editorStep(page,1);await interact(page.locator('#editor-next'));assert.equal(await page.locator('#editor-step-button-1').getAttribute('aria-current'),'step');assert.equal(await page.locator('#entity-form').count(),1);assert.equal(await page.locator('#f-lotArea').evaluate(element=>element.validity.valueMissing),true,'a house requires a plot before leaving the size step');
  await verifyNumeric(await editorField(page,'#f-lotArea'));await (await editorField(page,'#f-lotArea')).fill('650.5');await (await editorField(page,'#f-type')).selectOption('Lakás');assert.equal(await page.locator('#f-lotArea').isEnabled(),false);assert.equal(await page.locator('#f-lotArea').evaluate(element=>element.required),false);assert.equal(await page.locator('#f-floor').isEnabled(),true);await editorStep(page,2);assert.equal(await page.locator('#property-floor-field').isVisible(),true);await editorStep(page,3);assert.equal(await page.locator('#entity-amenities').isVisible(),true);
  await (await editorField(page,'#f-type')).selectOption('Ház');await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.equal(property.lotArea,650.5);assert.equal(property.floor,null);assert.equal(property.balcony,false);assert.equal(property.elevator,false);assert.equal(property.wholeRooms,2);assert.equal(property.halfRooms,3);
  await edit(page,interact,'property',property.id);assert.equal(await page.locator('#f-lotArea').inputValue(),'650.5');assert.equal(await page.locator('#property-floor-field').evaluate(element=>element.classList.contains('hidden')),true);assert.equal(await page.locator('#property-floor-field').isVisible(),false);assert.equal(await page.locator('#entity-amenities').isVisible(),false);assert.equal(await page.locator('#f-wholeRooms').inputValue(),'2');assert.equal(await page.locator('#f-halfRooms').inputValue(),'3');
  await editorStep(page,3);for(const checkbox of await page.locator('input[name="parkingTypes"]').all())await checkbox.uncheck();await (await editorField(page,'#f-secondaryHeatingType')).selectOption('');await save(page,interact);property=(await state(page)).properties.find(value=>value.id===property.id);assert.deepEqual(property.parkingTypes,[]);assert.equal(property.secondaryHeatingType,'');
  await openNew(page,interact,'search');await chooseLocation(page,interact);const searchTitle=`Fűtés és házszűrők – ${viewport.name}`;await (await editorField(page,'#f-title')).fill(searchTitle);
  for(const name of ['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms'])await verifyNumeric(await editorField(page,`#f-${name}`));
  await (await editorField(page,'#f-maxPrice')).fill('100.5');await (await editorField(page,'#f-minArea')).fill('40');await (await editorField(page,'#f-minRooms')).fill('2.5');
  const heatingOptions=await page.locator('input[name="heatingTypes"]').evaluateAll(inputs=>inputs.map(input=>input.value));assert.deepEqual(heatingOptions,primaryOptions.filter(Boolean));
  for(const value of ['Gázkazán','Hőszivattyú'])await (await editorField(page,`input[name="heatingTypes"][value="${value}"]`)).check();await (await editorField(page,'input[name="floors"][value="-1"]')).check();await (await editorField(page,'#f-balcony')).check();await (await editorField(page,'#f-elevator')).check();await (await editorField(page,'#f-type')).selectOption('Ház');
  assert.equal(await page.locator('#floors-group').evaluate(element=>element.classList.contains('hidden')),true);assert.equal(await page.locator('#floors-group').isVisible(),false);assert.equal(await page.locator('#entity-amenities').isVisible(),false);assert.equal(await page.locator('input[name="floors"][value="-1"]').isEnabled(),false);
  await fitsModal(page);await save(page,interact,true);let search=(await state(page)).searches.find(value=>value.title===searchTitle);assert.ok(search);assert.deepEqual(search.heatingTypes,['Gázkazán','Hőszivattyú']);assert.deepEqual(search.floors,[]);assert.equal(search.balcony,false);assert.equal(search.elevator,false);for(const name of ['minPrice','maxArea','maxRooms'])assert.equal(search[name],null);
  await edit(page,interact,'search',search.id);assert.equal(await page.locator('input[name="heatingTypes"][value="Gázkazán"]').isChecked(),true);assert.equal(await page.locator('#f-minPrice').inputValue(),'');assert.equal(await page.locator('#f-maxArea').inputValue(),'');assert.equal(await page.locator('#f-maxRooms').inputValue(),'');await (await editorField(page,'#f-type')).selectOption('Lakás');await editorStep(page,3);assert.equal(await page.locator('#floors-group').isVisible(),true);assert.equal(await page.locator('#f-balcony').isEnabled(),true);
  assert.deepEqual(errors,[],'Seller and search forms must not emit frontend errors');console.log(`Seller form ${viewport.name}: heating, parking, whole/half rooms, number entry, conditional house fields and reload persistence passed.`);
 }catch(error){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`seller-form-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports)await verify(browser,viewport);}finally{await browser.close();}
