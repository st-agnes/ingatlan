/** Responsive anonymous UI integration. Deterministic HTTP fixtures isolate the browser;
 * backend/onboarding-smoke.mjs proves creation semantics against actual MySQL. */
import {mockMapTiles} from './map-browser-network.mjs';
import {removeSelectedLocation,choosePropertyType,assertEditorNavigation,installEditorViewportMock,assertKeyboardNavigation} from './editor-browser-helpers.mjs';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {getLocation} from '../dist/locations.js';
import {neighborhoods} from '../dist/neighborhoods-data.js';

const modulePath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
const city=getLocation('city:Debrecen'),otherCity=getLocation('city:Szeged');
const quarter=getLocation(neighborhoods.find(item=>item.city==='Debrecen'&&item.name==='Vénkert').id);
const publicSourceKey=(kind,character)=>`${kind}-${character.repeat(64)}`;
const propertySource=publicSourceKey('property','a'),searchSource=publicSourceKey('search','b');
const draft=page=>page.evaluate(async()=>{const {loadDraft}=await import('/onboarding.js');return loadDraft();});
const rawDraft=page=>page.evaluate(()=>localStorage.getItem('otthonra.onboarding.v1'));
async function landingGeometry(page){return await page.evaluate(()=>{const input=document.getElementById('landing-location-input').getBoundingClientRect(),button=document.querySelector('#landing-search-form button[type=submit]').getBoundingClientRect(),chips=document.getElementById('landing-location-chips').getBoundingClientRect();return {offset:button.top-input.top,inputBottom:input.bottom,chipsTop:chips.top};});}
async function assertFreshLanding(page){await page.locator('#landing-search-form').waitFor();assert.equal(await page.locator('#landing-location-input').inputValue(),'');assert.equal(await page.locator('#landing-location-chips .location-chip').count(),0);}
const interact=(viewport,locator)=>viewport.touch?locator.tap():locator.click();
const pause=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds));
function landing(){
 const property={locations:[quarter],type:'Lakás',price:50000000,area:60,rooms:2.5,wholeRooms:2,halfRooms:1,lotArea:null,condition:'Jó',building:'Tégla',constructionAge:null,view:null,ceilingHeight:null,floor:2,heatingType:null,balcony:true,elevator:false,address:'PRIVATE SOURCE ADDRESS',ownerId:'PRIVATE SOURCE OWNER'};
 const search={locations:[city],type:'Lakás',minPrice:50000000,maxPrice:50000000,minArea:60,maxArea:60,minRooms:2.5,maxRooms:2.5,conditions:['Jó'],buildings:['Tégla'],constructionAges:[],views:[],ceilingHeight:null,floors:[2],heatingTypes:[],balcony:true,elevator:false,address:'PRIVATE SOURCE ADDRESS'};
 const ranged={...search,locations:[city,otherCity],minPrice:null,maxPrice:80000000,minArea:45,maxArea:80,minRooms:2,maxRooms:4};
 return {regions:[{id:'HU321',label:'Hajdú-Bihar'}],region:null,scope:'national',properties:[{key:'property-1',sourceKey:propertySource,title:'A másik ember ingatlanhirdetése',type:'Lakás',location:'Debrecen',price:50000000,area:60,rooms:2.5,wholeRooms:2,halfRooms:1,ownerFirstName:'Anna',ownerAccountType:'private',prefill:property}],searches:[search,ranged].map((prefill,index)=>({key:`search-${index+1}`,sourceKey:publicSourceKey('search',index?'c':'b'),title:'A másik ember keresése',type:'Lakás',locations:prefill.locations.map(item=>item.label),minPrice:prefill.minPrice,maxPrice:prefill.maxPrice,minArea:prefill.minArea,maxArea:prefill.maxArea,minRooms:prefill.minRooms,maxRooms:prefill.maxRooms,ownerFirstName:'Péter',ownerAccountType:'private',prefill}))};
}
async function createFixture(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 if(viewport.name==='mobile')await installEditorViewportMock(context);
 await mockMapTiles(context);
 const server={user:{id:'10000000-0000-4000-8000-000000000001',email:'onboarding-browser@example.test',name:'Saját Fiók',accountType:'private',phone:''},authRequests:[],creates:[],lookupRequests:[],rows:new Map(),failAuth:0,failSave:0,active:null,unhandled:[],landing:landing()};
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 await context.route('https://get.geojs.io/**',route=>route.fulfill({status:200,contentType:'application/json',body:'{"country_code":"XX"}'}));
 await context.route(`${origin}/runtime-config.js`,route=>route.fulfill({status:200,contentType:'text/javascript',body:'globalThis.OTTHONRA_CONFIG=Object.freeze({mode:"api",environment:"test"});'}));
 await context.route(`${origin}/api/**`,async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname.slice(4),method=request.method();
  const json=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  if(path==='/public/landing')return json(server.landing);
  if(path==='/locations'){server.lookupRequests.push({authorization:request.headers().authorization,query:url.searchParams.get('q')});const query=url.searchParams.get('q')||'';return json({items:/Szeged/i.test(query)?[otherCity]:/Vénkert/i.test(query)?[quarter]:/Debrecen/i.test(query)?[city,quarter]:[]});}
  if(path==='/streets')return json({items:[]});
  if(['/auth/register','/auth/login'].includes(path)){
   const body=request.postDataJSON();server.authRequests.push(body);
   if(server.failAuth-->0)return json({message:'A regisztráció most nem érhető el. Próbáld újra.'},503);
   server.user.email=body.email;return json({accessToken:'browser-session',user:server.user});
  }
  if(path==='/me')return json({...server.user,credits:100,unreadNotificationCount:0});
  if(path==='/me/entities')return json({properties:[...server.rows.values()].filter(row=>row.kind==='property'),searchRequests:[...server.rows.values()].filter(row=>row.kind==='search'),active:server.active,decisions:[],reportedOwnerIds:[],reportedEntities:[]});
  if(path==='/credits/ledger'||path==='/matches')return json({items:[]});
  if(path==='/feedback/pending')return json({feedbackPrompt:null});
  if(path==='/test/feedback-scenario')return json({available:false});
  if(path==='/feed')return json({active:server.active,items:[],stage:'empty',hasApproximate:false});
  if(path==='/me/active'&&method==='PUT'){server.active=request.postDataJSON();return json(server.active);}
  if(['/searches','/properties'].includes(path)&&method==='POST'){
   const body=request.postDataJSON(),kind=path==='/searches'?'search':'property';server.creates.push({kind,body});
   assert.match(body.creationRequestId,/^[a-f0-9-]{36}$/,'The completed draft must send its stable creation key');
   const key=kind+':'+body.creationRequestId;let row=server.rows.get(key);const created=!row;
   if(!row){row={...body,id:kind==='search'?'20000000-0000-4000-8000-000000000001':'30000000-0000-4000-8000-000000000001',ownerId:server.user.id,kind,archived:false,createdAt:new Date().toISOString()};delete row.creationRequestId;server.rows.set(key,row);}
   await pause(35);
   if(server.failSave-->0)return json({message:'A mentés válasza megszakadt. Próbáld újra.'},503);
   return json(row,created?201:200);
  }
  server.unhandled.push(method+' '+path);return json({message:'Unexpected browser fixture route'},404);
 });
 return {context,server};
}
async function progress(page,index){
 await page.waitForFunction(expected=>document.querySelector('#entity-form')?.getAttribute('data-editor-current-step')===String(expected),index);
 assert.equal(await page.locator('.editor-progress [data-action="editor-step"]').count(),6);assert.equal(await page.locator('.editor-step:visible').count(),1);
 assert.equal(await page.locator(`#editor-step-button-${index}`).getAttribute('aria-current'),'step');
 const fit=await page.locator('#entity-form').evaluate(element=>element.scrollWidth<=element.clientWidth+1);assert.ok(fit,'The normal six-step form must fit this viewport');await assertEditorNavigation(page);
}
async function next(page,viewport,index){await interact(viewport,page.locator('#editor-next'));await progress(page,index);}
async function gotoStep(page,viewport,index){await interact(viewport,page.locator(`#editor-step-button-${index}`));await progress(page,index);}
async function assertNoSourcePrivacy(page){const saved=JSON.stringify(await draft(page));assert.doesNotMatch(saved,/PRIVATE SOURCE|A másik ember|ownerId|ownerEmail|creationRequestHash/);}
async function screenshot(page,name){await mkdir(resolve('.local/browser-tests/screenshots'),{recursive:true});await page.screenshot({path:resolve('.local/browser-tests/screenshots',name),fullPage:true}).catch(()=>{});}

async function verifyWizardAuth(browser,viewport){
 const {context,server}=await createFixture(browser,viewport),page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);
 try{
  await page.goto(origin+'/',{waitUntil:'domcontentloaded'});await page.locator('.landing-property-card').waitFor();
  await interact(viewport,page.locator('#landing-search-form button[type="submit"]'));
  assert.equal(await page.locator('#entity-form,#hosted-auth-form').count(),0,'An empty query cannot skip choosing a canonical location');assert.match(await page.locator('#landing-location-error').innerText(),/Válassz/);
  const initialGeometry=await landingGeometry(page);
  await page.locator('#landing-location-input').fill('Nem létező hely');await interact(viewport,page.locator('#landing-search-form button[type="submit"]'));
  assert.equal(await page.locator('#entity-form,#hosted-auth-form').count(),0);assert.match(await page.locator('#landing-location-error').innerText(),/Válassz/);
  await page.locator('#landing-location-input').fill('Debrecen');await page.locator('#landing-location-options [role="option"]').first().waitFor();
  await page.locator('#landing-location-input').press('ArrowDown');await page.locator('#landing-location-input').press('Enter');
  await page.locator('#landing-location-chips .location-chip').waitFor({state:'attached'});
  for(let selected=1;selected<=2;selected++){const geometry=await landingGeometry(page);assert.ok(geometry.chipsTop>=geometry.inputBottom-1,'Selected locations belong below the query');assert.ok(Math.abs(geometry.offset-initialGeometry.offset)<=1,'Adding location chips must not move the button relative to the input');if(selected===1){await page.locator('#landing-location-input').fill('Debrecen');await page.locator('#landing-location-options [role="option"]').first().waitFor();await page.locator('#landing-location-input').press('ArrowDown');await page.locator('#landing-location-input').press('Enter');await page.waitForFunction(()=>document.querySelectorAll('#landing-location-chips .location-chip').length===2);}}
  await interact(viewport,page.locator('#landing-search-form button[type="submit"]'));await progress(page,0);
  assert.equal((await draft(page)).data.locationIds.length,2,'Handoff copies every choice into the new draft');
  await interact(viewport,page.locator('[data-action="landing"]').first());await assertFreshLanding(page);
  await page.goto(origin+'/#onboarding');await progress(page,0);
  assert.equal(await page.locator('#hosted-auth-form').count(),0,'Location selection opens anonymous onboarding before registration');assert.match(await page.locator('#location-chips').innerText(),/Debrecen/);
  let title=`Saját keresésem ${viewport.name}`;assert.equal(await page.locator('#f-title').isVisible(),false,'Name is offered only at the final topic');assert.equal(await page.locator('#f-type').inputValue(),'');await interact(viewport,page.locator('#editor-next'));await progress(page,1);await interact(viewport,page.locator('#editor-next'));await progress(page,1);assert.ok((await page.locator('#property-type-error').innerText()).trim(),'Choosing a type must show a visible validation message');await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await progress(page,2);
  for(const field of ['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms'])assert.equal(await page.locator(`#f-${field}`).inputValue(),'','A new search must not invent numeric preferences');
  await page.locator('#f-maxPrice').fill('80');await page.locator('#f-minArea').fill('50');await page.locator('#f-maxArea').fill('70');await page.locator('#f-minRooms').fill('1');await page.locator('#f-maxRooms').fill('3');
  await page.locator('#f-minPrice').fill('90');await interact(viewport,page.locator('#editor-next'));await progress(page,2);assert.equal(await page.locator('#f-maxPrice').evaluate(element=>element.checkValidity()),false,'Invalid ranges must block the same wizard validation');
  await page.locator('#f-minPrice').fill('');
  const before=await draft(page),second=await context.newPage();await second.goto(origin+'/#onboarding',{waitUntil:'domcontentloaded'});await progress(second,2);
  assert.equal((await draft(second)).id,before.id);assert.equal(await second.locator('#f-maxPrice').inputValue(),'80');await second.close();
  await page.reload({waitUntil:'domcontentloaded'});await progress(page,2);assert.equal(await page.locator('#f-maxPrice').inputValue(),'80');
  await gotoStep(page,viewport,0);assert.equal(await page.locator('#f-title').isVisible(),false);await gotoStep(page,viewport,2);
  if(viewport.name==='mobile')await assertKeyboardNavigation(page);
  await next(page,viewport,3);await assertEditorNavigation(page,{scroll:true,lastField:true});await next(page,viewport,4);await next(page,viewport,5);const generated=await page.locator('#f-title').inputValue();assert.match(generated,/Lakás/);assert.match(generated,/Debrecen/);assert.ok(generated.length<=70);await page.locator('#f-title').fill(title);await page.locator('#f-description').fill('A saját igényeim.');await interact(viewport,page.locator('#editor-save'));
  await page.locator('#hosted-auth-form').waitFor();assert.equal(new URL(page.url()).hash,'#register');assert.equal((await draft(page)).phase,'awaiting-auth');assert.equal(server.creates.length,0);
  const initialCompleted=await draft(page);await showLanding(page);await page.locator('#landing-recent-search').waitFor();await interact(viewport,page.locator('#landing-recent-search-resume'));await page.locator('#hosted-auth-form').waitFor();assert.equal((await draft(page)).phase,'awaiting-auth','A recent finalized draft resumes registration without reopening its immutable data');assert.equal((await draft(page)).creationRequestId,initialCompleted.creationRequestId);
  await interact(viewport,page.locator('[data-action="onboarding-edit"]'));await progress(page,5);
  title+=' módosítva';await page.locator('#f-title').fill(title);await gotoStep(page,viewport,0);await gotoStep(page,viewport,5);assert.equal(await page.locator('#f-title').inputValue(),title);await interact(viewport,page.locator('#editor-save'));await page.locator('#hosted-auth-form').waitFor();
  const changedCompleted=await draft(page);assert.equal(changedCompleted.id,initialCompleted.id);assert.equal(changedCompleted.creationRequestId,initialCompleted.creationRequestId,'Editing the same draft must retain its lifetime creation receipt');assert.equal(changedCompleted.completedData.title,title);
  server.failAuth=1;await page.locator('#f-name').fill('Saját Fiók');await page.locator('#f-email').fill(server.user.email);await page.locator('#f-password').fill('BrowserOnboarding2026!');await interact(viewport,page.locator('#hosted-auth-form button[type="submit"]'));
  await page.waitForFunction(()=>document.querySelector('#auth-error')?.textContent.includes('regisztráció most'));const pending=await draft(page);assert.equal(pending.expectedEmail,server.user.email);assert.ok(pending.creationRequestId);
  await page.reload({waitUntil:'domcontentloaded'});await page.locator('#hosted-auth-form').waitFor();assert.equal(await page.locator('#f-email').inputValue(),server.user.email);
  await page.locator('#f-name').fill('Saját Fiók');await page.locator('#f-password').fill('BrowserOnboarding2026!');await page.locator('#f-email').fill('different-account@example.test');await interact(viewport,page.locator('#hosted-auth-form button[type="submit"]'));
  await page.waitForFunction(()=>document.querySelector('#auth-error')?.textContent.includes('eredetileg'));assert.equal(server.authRequests.length,1,'A changed account must be rejected before registration and save');assert.equal(server.creates.length,0);
  await page.locator('#f-email').fill(server.user.email);server.failSave=1;await interact(viewport,page.locator('#hosted-auth-form button[type="submit"]'));
  await page.locator('#onboarding-save-error').waitFor();assert.equal((await draft(page)).phase,'saving');assert.equal(server.rows.size,1,'The accepted save with a lost response must remain retryable');
  await page.reload({waitUntil:'domcontentloaded'});await page.locator('[data-action="discover-search"]').waitFor();assert.equal(new URL(page.url()).hash,'#searches');assert.equal(await draft(page),null);assert.equal(await rawDraft(page),null,'Successful creation removes the storage key, not just hides the draft');
  assert.equal(server.rows.size,1);assert.ok(server.creates.length>=2);assert.ok(server.creates.every(request=>request.body.creationRequestId===pending.creationRequestId));assert.equal([...server.rows.values()][0].title,title);assert.equal(server.active,null,'Creation waits for the ordinary discovery choice before activation');
  await interact(viewport,page.locator('[data-action="discover-search"]'));await page.waitForFunction(()=>location.hash==='#discover');assert.equal(server.active.kind,'search');
  await page.reload({waitUntil:'domcontentloaded'});await page.locator('.page-heading').waitFor();assert.equal(server.rows.size,1);assert.equal(server.creates.length,2);assert.equal(await rawDraft(page),null);
  await page.goto(origin+'/#landing');await assertFreshLanding(page);assert.equal(await rawDraft(page),null);assert.equal(await page.locator('#landing-recent-search').count(),0);
  await page.goto(origin+'/#settings');await page.locator('#profile-form').waitFor();await interact(viewport,page.locator('[data-action="disconnect"]').first());await assertFreshLanding(page);
  await page.reload({waitUntil:'domcontentloaded'});await assertFreshLanding(page);assert.equal(await page.locator('#landing-recent-search').count(),0);assert.equal(await rawDraft(page),null,'Leaving the workspace and page lifecycle cannot resurrect a saved draft');
  assert.ok(server.lookupRequests.length>0&&server.lookupRequests.every(request=>!request.authorization),'Anonymous picker calls use the normal canonical API without a session');assert.deepEqual(server.unhandled,[]);assert.deepEqual(errors,[]);
  console.log(`Onboarding ${viewport.name}: canonical picker, six steps, range validation, editable title, cross-tab/reload persistence, auth failure/account guard, lost-response resume and discovery passed.`);
 }catch(error){await screenshot(page,`onboarding-wizard-${viewport.name}-failure.png`);throw error;}finally{await context.close();}
}

async function verifyTeaserSeeds(browser,viewport){
 const {context,server}=await createFixture(browser,viewport),page=await context.newPage();page.setDefaultTimeout(10000);
 try{
  await page.goto(origin+'/',{waitUntil:'domcontentloaded'});await page.locator('.landing-property-card').waitFor();
  await interact(viewport,page.locator('.landing-property-card [data-action="onboarding-start"]'));await progress(page,0);assert.match(await page.locator('#location-chips').innerText(),/Vénkert/);assert.notEqual(await page.locator('#f-title').inputValue(),'A másik ember ingatlanhirdetése');
  await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await progress(page,2);
  for(const [name,value] of Object.entries({minPrice:'',maxPrice:'55',minArea:'50',maxArea:'',minRooms:'2.5',maxRooms:''}))assert.equal(await page.locator(`#f-${name}`).inputValue(),value,`Property teaser ${name}`);
  await assertNoSourcePrivacy(page);await interact(viewport,page.locator('[data-action="onboarding-abandon"]'));await page.locator('.landing-search-card').first().waitFor();
  await interact(viewport,page.locator('.landing-search-card [data-action="onboarding-start"]').first());await progress(page,0);assert.match(await page.locator('#location-chips').innerText(),/Debrecen/);assert.equal(await page.locator('#f-street').inputValue(),'');assert.equal(await page.locator('#f-houseNumber').inputValue(),'');
  await interact(viewport,page.locator('#editor-next'));await progress(page,0);assert.equal(await page.locator('#f-street').evaluate(element=>element.checkValidity()),false,'A teaser never supplies another property address');
  await page.locator('#f-street').fill('OTTHONRA TEST');await page.locator('#f-houseNumber').fill('1');await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await progress(page,2);
  for(const [name,value] of Object.entries({price:'50',area:'60',wholeRooms:'2',halfRooms:'1'}))assert.equal(await page.locator(`#f-${name}`).inputValue(),value,`Exact search teaser ${name}`);
  await assertNoSourcePrivacy(page);await interact(viewport,page.locator('[data-action="onboarding-abandon"]'));await page.locator('.landing-search-card').first().waitFor();
  await interact(viewport,page.locator('.landing-search-card [data-action="onboarding-start"]').nth(1));await progress(page,0);assert.equal(await page.locator('#location-chips .location-chip').count(),0,'Multiple source towns do not invent the seller location');
  const snapshot=await draft(page);for(const field of ['price','area','rooms','wholeRooms'])assert.ok(snapshot.data[field]==null||snapshot.data[field]==='','Ranges must not be guessed into an exact property');
  assert.equal(server.creates.length,0);assert.equal(server.authRequests.length,0);await assertNoSourcePrivacy(page);
  console.log(`Onboarding seeds ${viewport.name}: property tolerance bounds and finest public neighborhood, exact-only seller fields, ambiguous ranges/towns and private-address protection passed.`);
 }catch(error){await screenshot(page,`onboarding-seeds-${viewport.name}-failure.png`);throw error;}finally{await context.close();}
}

async function verifyCrossTabAuth(browser,viewport){
 const {context,server}=await createFixture(browser,viewport),first=await context.newPage();first.setDefaultTimeout(10000);let second;
 try{
  await first.goto(origin+'/',{waitUntil:'domcontentloaded'});await first.locator('.landing-property-card').waitFor();
  await first.evaluate(async({city,email})=>{const {createDraft,saveDraft,prepareDraftForAuth}=await import('/onboarding.js');saveDraft(prepareDraftForAuth(createDraft('search',{title:'Több lapon folytatott keresés',type:'Lakás',locationIds:[city.id],locations:[city],minPrice:null,maxPrice:80,minArea:50,maxArea:null,minRooms:null,maxRooms:null,balcony:false,elevator:false},{editor:{locations:[city]}}),email));},{city,email:server.user.email});
  await first.goto(origin+'/#register');await first.locator('#hosted-auth-form').waitFor();second=await context.newPage();await second.goto(origin+'/#register');await second.locator('#hosted-auth-form').waitFor();
  const key=(await draft(first)).creationRequestId;
  await second.evaluate(async()=>{const {connectApi}=await import('/api.js');await connectApi(location.origin,'onboarding-browser@example.test','BrowserOnboarding2026!');});
  await first.waitForFunction(()=>!localStorage.getItem('otthonra.onboarding.v1'));
  await first.locator('.page-heading').waitFor();await second.goto(origin+'/#searches',{waitUntil:'domcontentloaded'});await second.locator('.page-heading').waitFor();
  assert.equal(server.rows.size,1);assert.ok(server.creates.length>=1);assert.ok(server.creates.every(request=>request.body.creationRequestId===key));assert.equal(server.authRequests.length,1,'A session established in another tab resumes the saved draft');
  assert.equal(await draft(second),null);assert.equal(await rawDraft(first),null);assert.equal(await rawDraft(second),null);await first.reload({waitUntil:'domcontentloaded'});await first.locator('.page-heading').waitFor();assert.equal(await rawDraft(first),null,'An older open tab cannot restore a consumed draft');assert.deepEqual(server.unhandled,[]);
  console.log(`Onboarding session ${viewport.name}: registration/login in another tab resumes one stable owned creation and clears the completed draft.`);
 }catch(error){await screenshot(first,`onboarding-tabs-${viewport.name}-failure.png`);throw error;}finally{await context.close();}
}

async function pickLocation(page,viewport,prefix,query,id){
 await page.locator(`#${prefix}-input`).fill(query);
 const option=page.locator(`#${prefix}-options [role="option"][data-location-id="${id}"]`);
 await option.waitFor();await interact(viewport,option);
}
async function showLanding(page){await page.goto(origin+'/#landing',{waitUntil:'domcontentloaded'});await assertFreshLanding(page);}
async function assertNoReplacementPrompt(page){assert.equal(await page.locator('[data-action="onboarding-replace"],[data-action="onboarding-resume"]').count(),0,'Starting a draft never asks whether to replace another one');}

async function verifyDraftOrigins(browser,viewport){
 const {context,server}=await createFixture(browser,viewport),page=await context.newPage(),errors=[];page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));
 try{
  await page.goto(origin+'/',{waitUntil:'domcontentloaded'});await page.locator('.landing-property-card').waitFor();
  await interact(viewport,page.locator('.landing-property-card [data-action="onboarding-start"]'));await progress(page,0);await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await progress(page,2);
  await page.locator('#f-maxPrice').fill('97');await gotoStep(page,viewport,5);await page.locator('#f-title').fill('Saját megőrzött keresésem');await gotoStep(page,viewport,3);
  const original=await draft(page);assert.equal(original.origin.key,propertySource);
  await showLanding(page);await page.locator('#landing-recent-search').waitFor();assert.match(await page.locator('#landing-recent-search').innerText(),/Legutóbbi keresésed/);
  assert.match(await page.locator('#landing-recent-search').innerText(),/Saját megőrzött keresésem/);
  const recentGeometry=await page.evaluate(()=>({form:document.getElementById('landing-search-form').getBoundingClientRect().bottom,recent:document.getElementById('landing-recent-search').getBoundingClientRect().top}));
  assert.ok(recentGeometry.recent>=recentGeometry.form-1,'The recent search is directly below the landing search');
  await interact(viewport,page.locator('#landing-recent-search-resume'));await progress(page,3);assert.equal((await draft(page)).id,original.id);assert.equal(await page.locator('#f-maxPrice').inputValue(),'97');
  await showLanding(page);
  // A different entity occupies the old first slot; the original moves and changes price.
  const same=server.landing.properties[0],other={...structuredClone(same),sourceKey:publicSourceKey('property','d'),key:'property-1'};
  same.key='property-2';same.price=80000000;same.prefill.price=80000000;server.landing.properties=[other,same];
  await page.reload({waitUntil:'domcontentloaded'});await page.locator('.landing-property-card').first().waitFor();
  await interact(viewport,page.locator(`.landing-property-card [data-source="${propertySource}"]`));await progress(page,3);await assertNoReplacementPrompt(page);
  assert.equal((await draft(page)).id,original.id,'Stable entity identity, not card position or changed price, resumes the draft');assert.equal(await page.locator('#f-maxPrice').inputValue(),'97');assert.equal(await page.locator('#f-title').inputValue(),'Saját megőrzött keresésem');
  await showLanding(page);await interact(viewport,page.locator(`.landing-property-card [data-source="${other.sourceKey}"]`));await progress(page,0);await assertNoReplacementPrompt(page);
  const replacement=await draft(page);assert.notEqual(replacement.id,original.id,'A different, otherwise identical listing starts a new draft');assert.equal(replacement.origin.key,other.sourceKey);assert.equal(await page.locator('#f-maxPrice').inputValue(),'55');
  await showLanding(page);await interact(viewport,page.locator(`.landing-search-card [data-source="${searchSource}"]`));await progress(page,0);await assertNoReplacementPrompt(page);
  const seller=await draft(page);assert.equal(seller.kind,'property');assert.notEqual(seller.id,replacement.id);assert.equal(seller.origin.key,searchSource);
  await page.locator('#f-street').fill('OTTHONRA TEST');await page.locator('#f-houseNumber').fill('1');await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await progress(page,2);await page.locator('#f-price').fill('123');await next(page,viewport,3);
  await showLanding(page);assert.equal(await page.locator('#landing-recent-search').count(),0,'An unfinished seller property is not presented as a recent search');
  server.landing.searches.reverse();server.landing.searches.forEach((item,index)=>item.key=`search-${index+1}`);
  await page.reload({waitUntil:'domcontentloaded'});await page.locator('.landing-search-card').first().waitFor();await interact(viewport,page.locator(`.landing-search-card [data-source="${searchSource}"]`));await progress(page,3);
  assert.equal((await draft(page)).id,seller.id);assert.equal(await page.locator('#f-price').inputValue(),'123','A repeated search teaser preserves the owner-entered property fields');
  await showLanding(page);await pickLocation(page,viewport,'landing-location','Debrecen',city.id);await pickLocation(page,viewport,'landing-location','Szeged',otherCity.id);await interact(viewport,page.locator('#landing-search-form button[type="submit"]'));await progress(page,0);await assertNoReplacementPrompt(page);
  const locationsDraft=await draft(page);assert.notEqual(locationsDraft.id,seller.id);assert.equal(await page.locator('#f-type').inputValue(),'');
  await pickLocation(page,viewport,'location','Vénkert',quarter.id);await removeSelectedLocation(page,otherCity.id,locator=>interact(viewport,locator));await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await progress(page,2);await page.locator('#f-maxPrice').fill('111');await page.locator('#f-minArea').fill('50');await next(page,viewport,3);
  await showLanding(page);await pickLocation(page,viewport,'landing-location','Vénkert',quarter.id);await pickLocation(page,viewport,'landing-location','Debrecen',city.id);await interact(viewport,page.locator('#landing-search-form button[type="submit"]'));await progress(page,3);
  assert.equal((await draft(page)).id,locationsDraft.id,'Exact current locations resume even when reordered or edited since the original seed');assert.equal(await page.locator('#f-maxPrice').inputValue(),'111');
  await showLanding(page);await pickLocation(page,viewport,'landing-location','Debrecen',city.id);await interact(viewport,page.locator('#landing-search-form button[type="submit"]'));await progress(page,0);await assertNoReplacementPrompt(page);
  const changed=await draft(page);assert.notEqual(changed.id,locationsDraft.id);assert.deepEqual(changed.data.locationIds,[city.id]);assert.equal(await page.locator('#f-type').inputValue(),'');
  await showLanding(page);const second=await context.newPage();await second.goto(origin+'/#landing',{waitUntil:'domcontentloaded'});await second.locator('#landing-recent-search').waitFor();
  await interact(viewport,page.locator('.landing-search-card [data-action="onboarding-start"]').first());await progress(page,0);await second.locator('#landing-recent-search').waitFor({state:'detached'});
  await showLanding(page);await interact(viewport,page.locator('.landing-hero-actions [data-intent="search"]'));await progress(page,0);await second.locator('#landing-recent-search').waitFor();
  await interact(viewport,page.locator('[data-action="onboarding-abandon"]'));await assertFreshLanding(page);await second.locator('#landing-recent-search').waitFor({state:'detached'});
  await second.close();
  await page.evaluate(async()=>{const {createDraft,saveDraft}=await import('/onboarding.js');saveDraft(createDraft('search',{title:'Lejárt keresésem',type:'Lakás',locationIds:['city:Debrecen']},{now:Date.now()-8*86400000}));});
  await page.reload({waitUntil:'domcontentloaded'});await assertFreshLanding(page);assert.equal(await page.locator('#landing-recent-search').count(),0);assert.equal(await rawDraft(page),null,'An expired recent search is removed rather than offered');
  assert.equal(server.creates.length,0);assert.equal(server.authRequests.length,0);assert.deepEqual(server.unhandled,[]);assert.deepEqual(errors,[]);
  console.log(`Onboarding origins ${viewport.name}: stable entity/source identity, automatic same-source resume and replacement, current location-set matching, recent search layout/resume, cross-tab updates and expiry passed.`);
 }catch(error){await screenshot(page,`onboarding-origins-${viewport.name}-failure.png`);throw error;}finally{await context.close();}
}
const browser=await chromium.launch({headless:true});let failures=0;
try{for(const viewport of viewports)for(const verify of [verifyWizardAuth,verifyTeaserSeeds,verifyCrossTabAuth,verifyDraftOrigins]){try{await verify(browser,viewport);}catch(error){failures++;console.error(`${verify.name} ${viewport.name}: ${error.stack||error}`);}}}finally{await browser.close();}
if(failures)process.exitCode=1;
