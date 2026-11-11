/** Real desktop/tablet/mobile wizard navigation and fixed discovery decisions. */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {editorField,editorStep,editorSave} from './editor-browser-helpers.mjs';

const modulePath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const screenshots=resolve('.local/browser-tests/screenshots');
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
const state=page=>page.evaluate(async()=>(await import('/model.js')).model.getState());
const labels={property:['Alapadatok','Ár és méret','Ingatlanjellemzők','Felszereltség','Képek és leírás'],search:['Helyszín és típus','Ár és méret','Ingatlanjellemzők','Kényelem és felszereltség','További elképzelések']};
let visit=0;

async function fresh(page,kind='search',long=false){
 await page.goto(`${origin}/?wizard-dock=${++visit}#discover`,{waitUntil:'domcontentloaded'});await page.locator('.page-heading').waitFor();
 await page.evaluate(async({kind,long})=>{
  const {createModel,STORAGE_KEY}=await import('/model.js');let raw;
  const model=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}});model.activate(kind,kind==='property'?'own-p1':'own-s1');
  raw.active={kind,id:kind==='property'?'own-p1':'own-s1'};raw.decisions=[];raw.matches=[];raw.credits=100;
  if(long){for(const item of [...raw.properties,...raw.searches])item.description=Array(25).fill('Fontos számomra a világos, nyugodt otthon és a jól használható terek.').join(' ');}
  localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));
 },{kind,long});
 await page.reload({waitUntil:'domcontentloaded'});await page.locator('#candidate').waitFor();
}

async function verifyProgress(page,kind,index){
 const buttons=page.locator('.editor-progress [data-action="editor-step"]');assert.equal(await buttons.count(),5);
 for(let step=0;step<5;step++)assert.ok((await buttons.nth(step).innerText()).includes(labels[kind][step]),`Step ${step+1} must have its topic name`);
 assert.equal(await page.locator(`#editor-step-button-${index}`).getAttribute('aria-current'),'step');
 assert.equal(await page.locator('.editor-step:visible').count(),1,'Only one topic is displayed at a time');
 assert.equal(await page.locator(`#editor-step-${index}`).isVisible(),true);
 const geometry=await page.locator('.entity-wizard').evaluate(element=>({width:element.clientWidth,scroll:element.scrollWidth}));
 assert.ok(geometry.scroll<=geometry.width+1,'Named progress and fields must fit without horizontal scrolling');
}

async function createWizard(page,interact,kind,viewport){
 await page.goto(`${origin}/?wizard-dock=${++visit}#${kind==='property'?'properties':'searches'}`,{waitUntil:'domcontentloaded'});
 const before=await state(page),title=`Lépésenként ${kind} ${viewport.name}`;
 await interact(page.locator(`.page-heading [data-action="new"][data-kind="${kind}"]`));
 await page.waitForFunction(()=>document.activeElement?.id==='f-title');await verifyProgress(page,kind,0);
 assert.equal(await page.locator('#editor-save').isVisible(),false,'Saving is offered only after all topic screens');
 await interact(page.locator('#editor-next'));await verifyProgress(page,kind,0);
 assert.equal((await state(page))[kind==='property'?'properties':'searches'].length,before[kind==='property'?'properties':'searches'].length,'An invalid next action must not create an entity');
 await page.locator('#f-title').fill(title);
 await page.locator('#location-input').fill('Debrecen');await interact(page.locator('[data-location-id="city:Debrecen"]'));
 if(kind==='search'){await page.locator('#location-input').fill('Hajdúszoboszló');await interact(page.locator('[data-location-id="city:Hajdúszoboszló"]'));}
 if(kind==='property')await page.locator('#f-type').selectOption('Ház');
 await page.evaluate(()=>{globalThis.wizardOriginalTitle=document.getElementById('f-title');});
 await interact(page.locator('#editor-next'));await verifyProgress(page,kind,1);
 assert.equal(await page.locator('#editor-step-button-0').getAttribute('data-state'),'completed');
 if(kind==='property'){
  await page.locator('#f-price').fill('95.5');await page.locator('#f-area').fill('86.5');await page.locator('#f-wholeRooms').fill('3');await page.locator('#f-halfRooms').fill('1');
  await interact(page.locator('#editor-next'));await verifyProgress(page,kind,1);
  assert.equal(await page.locator('#f-lotArea').evaluate(element=>element.validity.valueMissing),true,'House plot is required on the size screen');
  await page.locator('#f-lotArea').fill('520.5');
 }else{
  await page.locator('#f-minPrice').fill('');await page.locator('#f-maxPrice').fill('105.5');await page.locator('#f-minArea').fill('65');await page.locator('#f-maxArea').fill('');await page.locator('#f-minRooms').fill('2.5');await page.locator('#f-maxRooms').fill('');
 }
 await interact(page.locator('#editor-next'));await verifyProgress(page,kind,2);
 if(kind==='property'){
  await page.locator('#f-condition').selectOption('Jó');await page.locator('#f-building').selectOption('Tégla');await page.locator('#f-view').selectOption('Kertre néző');
  assert.equal(await page.locator('#property-floor-field').isVisible(),false);
 }else{
  await page.locator('input[name="conditions"][value="Jó"]').check();await page.locator('input[name="conditions"][value="Új/felújított"]').check();await page.locator('input[name="buildings"][value="Tégla"]').check();
 }
 await interact(page.locator('#editor-next'));await verifyProgress(page,kind,3);
 if(kind==='property'){
  await page.locator('#f-heatingType').selectOption('Hőszivattyú');await page.locator('#f-insulated').selectOption('false');await page.locator('#f-airConditioning').selectOption('true');
  await page.locator('input[name="parkingTypes"][value="Garázs"]').check();await page.locator('input[name="parkingTypes"][value="Udvari beálló"]').check();
  assert.equal(await page.locator('#entity-amenities').isVisible(),false);
 }else{
  await page.locator('input[name="heatingTypes"][value="Hőszivattyú"]').check();await page.locator('#f-ceilingHeight').selectOption('3 m feletti');await page.locator('input[name="floors"][value="0"]').check();await page.locator('#f-elevator').check();
 }
 await interact(page.locator('#editor-next'));await verifyProgress(page,kind,4);
 const description=`Megőrzött leírás – ${viewport.name} – ${kind}`;
 await page.locator('#f-description').fill(description);
 if(kind==='property')await page.locator('#property-images').fill('https://images.unsplash.com/photo-1600585154340-be6161a56a0c');
 else await page.locator('#f-moveIn').selectOption('3 hónapon belül');
 await interact(page.locator('#editor-back'));await verifyProgress(page,kind,3);
 await editorStep(page,0,interact);await verifyProgress(page,kind,0);
 assert.equal(await page.evaluate(()=>globalThis.wizardOriginalTitle===document.getElementById('f-title')),true,'Back navigation must retain the same input nodes and their draft values');
 assert.equal(await page.locator('#f-title').inputValue(),title);assert.equal(await page.locator('#location-chips .location-chip').count(),kind==='property'?1:2);
 await page.locator('#f-title').fill(title+' módosítva');
 await editorStep(page,1,interact);await verifyProgress(page,kind,1);
 assert.equal(await page.locator(kind==='property'?'#f-price':'#f-maxPrice').inputValue(),kind==='property'?'95.5':'105.5');
 await page.locator(kind==='property'?'#f-area':'#f-minArea').fill('87.5');
 await editorStep(page,4,interact);await verifyProgress(page,kind,4);
 assert.equal(await page.locator('#f-description').inputValue(),description);
 if(kind==='property'){
  assert.equal(await page.locator('#property-images').inputValue(),'https://images.unsplash.com/photo-1600585154340-be6161a56a0c');assert.equal(await page.locator('#f-insulated').inputValue(),'false');assert.equal(await page.locator('#f-airConditioning').inputValue(),'true');assert.equal(await page.locator('input[name="parkingTypes"][value="Garázs"]').isChecked(),true);
 }else{
  for(const field of ['minPrice','maxArea','maxRooms'])assert.equal(await page.locator(`#f-${field}`).inputValue(),'');assert.equal(await page.locator('input[name="conditions"][value="Új/felújított"]').isChecked(),true);assert.equal(await page.locator('#f-moveIn').inputValue(),'3 hónapon belül');
 }
 const draft=await state(page);assert.equal(draft[kind==='property'?'properties':'searches'].length,before[kind==='property'?'properties':'searches'].length,'No topic change or backward edit may save the draft early');
 await editorSave(page,interact);
 if(kind==='search'){await page.getByRole('heading',{name:'Elkészült a keresési igényed.',exact:true}).waitFor();await interact(page.locator('.search-created-actions [data-action="close"]'));}
 await page.locator('#entity-form').waitFor({state:'detached'});
 const after=await state(page),saved=after[kind==='property'?'properties':'searches'].find(item=>item.title===title+' módosítva');assert.ok(saved);assert.equal(after[kind==='property'?'properties':'searches'].length,before[kind==='property'?'properties':'searches'].length+1,'Only the final save creates one entity');assert.deepEqual(after.active,before.active);
 assert.equal(saved.description,description);
 if(kind==='property'){assert.equal(saved.area,87.5);assert.equal(saved.lotArea,520.5);assert.equal(saved.rooms,3.5);assert.equal(saved.insulated,false);assert.equal(saved.airConditioning,true);assert.equal(saved.heatingType,'Hőszivattyú');assert.deepEqual(saved.parkingTypes,['Udvari beálló','Garázs']);}
 else{assert.equal(saved.minArea,87.5);assert.equal(saved.maxPrice,105.5);for(const field of ['minPrice','maxArea','maxRooms'])assert.equal(saved[field],null);assert.deepEqual(saved.locationIds,['city:Debrecen','city:Hajdúszoboszló']);assert.equal(saved.moveIn,'3 hónapon belül');}
 await interact(page.locator(`[data-action="edit"][data-kind="${kind}"][data-id="${saved.id}"]`));await page.waitForFunction(()=>document.activeElement?.id==='f-title');await verifyProgress(page,kind,0);
 assert.equal(await page.locator('#f-title').inputValue(),saved.title);await editorStep(page,4,interact);assert.equal(await page.locator('#f-description').inputValue(),description);
 await page.locator('#f-description').fill(description+' szerkesztve');await editorStep(page,0,interact);await editorStep(page,4,interact);await editorSave(page,interact);await page.locator('#entity-form').waitFor({state:'detached'});
 const edited=await state(page);assert.equal(edited[kind==='property'?'properties':'searches'].length,after[kind==='property'?'properties':'searches'].length);assert.equal(edited[kind==='property'?'properties':'searches'].find(item=>item.id===saved.id).description,description+' szerkesztve');assert.equal(await page.locator('.search-created-actions').count(),0,'Editing must not reopen the new-search activation prompt');
}

async function assertReachable(page){
 const dock=page.locator('.discovery-decision-dock');assert.equal(await dock.isVisible(),true);
 const details=await dock.evaluate(element=>({position:getComputedStyle(element).position,width:element.clientWidth,scroll:element.scrollWidth}));assert.equal(details.position,'fixed');assert.ok(details.scroll<=details.width+1);
 for(const action of ['pass','like']){
  const proof=await dock.locator(`[data-action="${action}"]`).evaluate(element=>{const b=element.getBoundingClientRect();const top=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return{left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:innerWidth,height:innerHeight,hit:element===top||element.contains(top)};});
  assert.ok(proof.left>=0&&proof.right<=proof.width+1&&proof.top>=0&&proof.bottom<=proof.height+1,`${action} must stay in the viewport without scrolling`);assert.equal(proof.hit,true,`${action} must be directly clickable above the content`);
 }
}

async function verifyDock(page,interact,kind,viewport){
 await fresh(page,kind,true);await assertReachable(page);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollHeight>innerHeight),'The fixture must contain genuinely scrollable discovery content');
 for(const fraction of [0,.5,1]){
  await page.evaluate(async fraction=>{window.scrollTo({top:(document.documentElement.scrollHeight-innerHeight)*fraction,behavior:'instant'});await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));},fraction);
  await assertReachable(page);
 }
 await interact(page.locator('.card-actions [data-action="details"]'));await page.locator('.modal').waitFor();assert.equal(await page.locator('.discovery-decision-dock').isVisible(),false,'Background decisions must not sit over a detail dialog');
 const modalActions=page.locator('.modal-actions [data-action="pass"],.modal-actions [data-action="like"]');assert.equal(await modalActions.count(),2);
 for(const fraction of [0,.5,1]){
  await page.locator('.modal').evaluate(async(element,fraction)=>{element.scrollTo({top:(element.scrollHeight-element.clientHeight)*fraction,behavior:'instant'});await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));},fraction);
  for(const button of await modalActions.all()){
   const proof=await button.evaluate(element=>{const b=element.getBoundingClientRect(),top=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return{top:b.top,bottom:b.bottom,height:innerHeight,hit:element===top||element.contains(top)};});
   assert.ok(proof.top>=0&&proof.bottom<=proof.height+1,'Detail-dialog decisions must remain in view at every modal scroll position');assert.equal(proof.hit,true,'Detail-dialog decisions must remain unobstructed');
  }
 }
 await interact(page.locator('.modal [data-action="close"]').first());await page.locator('.modal').waitFor({state:'detached'});await assertReachable(page);
 if(viewport.width<=720){
  await interact(page.locator('.mobile-menu'));assert.equal(await page.locator('.discovery-decision-dock').isVisible(),false,'The mobile navigation must own its click targets');
  await page.setViewportSize({width:800,height:1100});await assertReachable(page);
  await page.setViewportSize({width:viewport.width,height:viewport.height});assert.equal(await page.locator('.discovery-decision-dock').isVisible(),false);
  await interact(page.locator('.sidebar .nav-button[data-page="discover"]'));await assertReachable(page);
 }
 const before=await state(page);await interact(page.locator('.card-actions [data-action="pass"]'));await page.waitForFunction(async count=>(await import('/model.js')).model.getState().decisions.length===count+1,before.decisions.length);await page.locator('#candidate').waitFor();await assertReachable(page);
 const next=await state(page);await interact(page.locator('.card-actions [data-action="like"]'));await page.waitForFunction(async count=>(await import('/model.js')).model.getState().decisions.length===count+1,next.decisions.length);
 const after=await state(page);assert.equal(after.credits,next.credits-(kind==='property'?2:0),'Fixed decisions must retain the ordinary billing rules');
 if(await page.locator('.modal').count())await interact(page.locator('.modal [data-action="close"]').last());
 console.log(`Decision dock ${kind} ${viewport.name}: top/middle/bottom viewport reachability, unobstructed clicks, modal/menu layering and normal pass/like billing passed.`);
}

async function verify(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());await context.route('https://images.unsplash.com/**',route=>route.abort());
 const page=await context.newPage();page.setDefaultTimeout(10000);page.setDefaultNavigationTimeout(20000);const errors=[];page.on('pageerror',error=>errors.push(error.message));const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await fresh(page);
  for(const kind of ['property','search'])await createWizard(page,interact,kind,viewport);
  for(const kind of ['search','property'])await verifyDock(page,interact,kind,viewport);
  assert.deepEqual(errors,[]);console.log(`Wizard ${viewport.name}: all five named topics, validation, backward edits without draft loss, nullable bounds, optional choices, one final save and edits passed.`);
 }catch(error){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`wizard-dock-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports)await verify(browser,viewport);}finally{await browser.close();}
