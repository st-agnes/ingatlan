/** City-region picker regression on desktop, tablet and mobile. Uses the real demo modules. */
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
const readState=page=>page.evaluate(async()=> (await import('/model.js')).model.getState());
async function openPage(page,kind){
 await page.goto(`${origin}/?areas-visit=${++visit}#${kind==='search'?'searches':'properties'}`,{waitUntil:'domcontentloaded'});
}
async function newEntity(page,interact,kind){await openPage(page,kind);await interact(page.locator(`.page-heading [data-action="new"][data-kind="${kind}"]`));await page.waitForFunction(()=>document.activeElement?.id==='f-title');}
async function editEntity(page,interact,kind,id){await openPage(page,kind);await interact(page.locator(`[data-action="edit"][data-id="${id}"]`));await page.waitForFunction(()=>document.activeElement?.id==='f-title');}
async function query(page,value){await (await editorField(page,'#location-input')).fill(value);await page.locator('#location-options').waitFor({state:'visible'});}
async function choose(page,interact,id){await interact(page.locator(`#location-options [data-location-id="${id}"]`));assert.equal(await page.locator('#location-input').inputValue(),'');}
async function save(page,interact,isNewSearch=false){
 await editorSave(page,interact);
 if(isNewSearch){await page.getByRole('heading',{name:'Elkészült a keresési igényed.',exact:true}).waitFor();await interact(page.locator('.search-created-actions [data-action="close"]'));}
 await page.locator('#entity-form').waitFor({state:'detached'});
}
async function verify(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 const page=await context.newPage();page.setDefaultTimeout(10000);page.setDefaultNavigationTimeout(20000);
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await newEntity(page,interact,'search');
  assert.equal(await page.locator('.location-source a').getAttribute('href'),'https://www.ksh.hu/teruleti_szamjel_menu');
  await query(page,'Debrecen');
  const debrecen=page.locator('#location-options [data-location-id="area:Debrecen"]');
  assert.match(await debrecen.innerText(),/Debrecen és környéke \(13 település\)/);
  await choose(page,interact,'area:Debrecen');
  await query(page,'Budapest');
  const budapest=page.locator('#location-options [data-location-id="area:Budapest"]');
  assert.match(await budapest.innerText(),/Budapest és környéke \(81 település\)/);
  await choose(page,interact,'area:Budapest');
  await query(page,'Solymár');await choose(page,interact,'city:Solymár');
  const chips=page.locator('#location-chips');
  assert.match(await chips.innerText(),/Debrecen és környéke \(13 település\)/);
  assert.match(await chips.innerText(),/Budapest és környéke \(81 település\)/);
  assert.match(await chips.innerText(),/Solymár/);
  const geometry=await page.locator('.modal').evaluate(element=>({width:element.clientWidth,scrollWidth:element.scrollWidth}));
  assert.ok(geometry.scrollWidth<=geometry.width+1,'Region names and counts must fit the modal without horizontal scrolling');
  const title=`Városkörnyékek és település – ${viewport.name}`;
  await (await editorField(page,'#f-title')).fill(title);await save(page,interact,true);
  let search=(await readState(page)).searches.find(item=>item.title===title);assert.ok(search);
  assert.deepEqual(search.locationIds,['area:Debrecen','area:Budapest','city:Solymár'],'Selected groups stay compact and are not expanded to member IDs');
  await openPage(page,'search');
  const card=page.locator('.entity-card').filter({has:page.getByRole('heading',{name:title,exact:true})});
  assert.match(await card.innerText(),/Debrecen és környéke \(13 település\)/);
  assert.match(await card.innerText(),/Budapest és környéke \(81 település\)/);
  await editEntity(page,interact,'search',search.id);
  assert.match(await page.locator('#location-chips').innerText(),/Debrecen és környéke \(13 település\)/);
  await interact(page.locator('[data-remove-location="area:Debrecen"]'));
  assert.doesNotMatch(await page.locator('#location-chips').innerText(),/Debrecen/);
  await save(page,interact);
  search=(await readState(page)).searches.find(item=>item.id===search.id);
  assert.deepEqual(search.locationIds,['area:Budapest','city:Solymár']);
  await newEntity(page,interact,'property');
  assert.equal(await page.locator('.location-source').count(),0,'Seller field must stay a precise location selector');
  await query(page,'Debrecen');
  assert.equal(await page.locator('#location-options [data-location-id^="area:"]').count(),0);
  assert.equal(await page.locator('#location-options [data-location-id="city:Debrecen"]').count(),1);
  await choose(page,interact,'city:Debrecen');
  const propertyTitle=`Pontos településű ingatlan – ${viewport.name}`;
  await (await editorField(page,'#f-title')).fill(propertyTitle);await (await editorField(page,'#f-price')).fill('65');await (await editorField(page,'#f-area')).fill('62');await (await editorField(page,'#f-wholeRooms')).fill('3');await (await editorField(page,'#f-halfRooms')).fill('0');
  await save(page,interact);
  const property=(await readState(page)).properties.find(item=>item.title===propertyTitle);assert.ok(property);
  assert.equal(property.locationId,'city:Debrecen');
  assert.deepEqual(errors,[],'City-region selection must not emit frontend errors');
  console.log(`Areas browser ${viewport.name}: counted region suggestions, mixed selections, source link, compact IDs, reload/edit/removal and precise seller location passed.`);
 }catch(error){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`areas-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports)await verify(browser,viewport);}finally{await browser.close();}
