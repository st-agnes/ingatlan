/** Foreground responsiveness under suspended/slow HTTP, using Chromium's real freeze/active lifecycle.
 * HTTP gates avoid twenty-second sleeps and isolate UI responsiveness from external services.
 */
import {mockMapTiles} from './map-browser-network.mjs';
import {choosePropertyType} from './editor-browser-helpers.mjs';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {getLocation} from '../dist/locations.js';

const modulePath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
const city=getLocation('city:Debrecen');
const id={userA:'10000000-0000-4000-8000-000000000001',userB:'10000000-0000-4000-8000-000000000002',search:'20000000-0000-4000-8000-000000000001',owned:'30000000-0000-4000-8000-000000000001',candidate:'30000000-0000-4000-8000-000000000002'};
const interact=(viewport,locator)=>viewport.touch?locator.tap():locator.click();
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function eventually(check,message,timeout=1500){const end=Date.now()+timeout;while(Date.now()<end){if(await check())return;await pause(10);}assert.ok(await check(),message);}
function gate(){let release;const promise=new Promise(resolve=>{release=resolve;});return {promise,release};}
const search=(userId=id.userA)=>({id:id.search,ownerId:userId,title:'Saját pontos keresés',type:'Lakás',locationIds:[city.id],locations:[city],city:city.city,minPrice:null,maxPrice:90000000,minArea:40,maxArea:null,minRooms:1,maxRooms:null,conditions:[],buildings:[],constructionAges:[],views:[],floors:[],heatingTypes:[],balcony:false,elevator:false,description:''});
const property=(propertyId,ownerId,title)=>({id:propertyId,ownerId,title,type:'Lakás',locationId:city.id,location:city,city:city.city,price:65000000,area:60,rooms:2,wholeRooms:2,halfRooms:0,condition:'Jó',building:'Tégla',images:[],address:'',balcony:false,elevator:false});
async function fixture(browser,viewport,{guest=false}={}){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await mockMapTiles(context);
 const server={gets:[],posts:[],unhandled:[],readGate:null,decisionGate:null,decided:false,feedbackPrompt:null,errors:[],profiles:{a:{name:'OLD_ACCOUNT_A_CANARY',email:'a@example.test',phone:''},b:{name:'NEW_ACCOUNT_B_CANARY',email:'b@example.test',phone:''}}};
 await context.addInitScript(({origin,guest})=>{
  if(!guest)localStorage.setItem('otthonra.api',JSON.stringify({baseUrl:origin,token:'resume-session-a'}));
  // CDP freezes actual script execution; explicit visibility makes headless behavior match a hidden phone tab.
  const nativeVisibility=Object.getOwnPropertyDescriptor(Document.prototype,'visibilityState')?.get;
  Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>globalThis.__resumeVisibility||nativeVisibility?.call(document)||'visible'});
  Object.defineProperty(document,'hidden',{configurable:true,get:()=>document.visibilityState==='hidden'});
 },{origin,guest});
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 await context.route('https://get.geojs.io/**',route=>route.fulfill({status:200,contentType:'application/json',body:'{"country_code":"XX"}'}));
 await context.route(`${origin}/runtime-config.js`,route=>route.fulfill({status:200,contentType:'text/javascript',body:'globalThis.OTTHONRA_CONFIG=Object.freeze({mode:"api",environment:"test"});'}));
 await context.route(`${origin}/api/**`,async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname.slice(4),method=request.method(),token=request.headers().authorization;
  const b=token==='Bearer resume-session-b',userId=b?id.userB:id.userA,profile=server.profiles[b?'b':'a'],name=profile.name;
  const json=async(data,status=200)=>{try{return await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});}catch(error){if(!/closed|handled|intercept|abort/i.test(String(error)))throw error;}};
  if(method==='GET')server.gets.push({path,token});else server.posts.push({path,method,body:request.postDataJSON()});
  // Capture account data at request start so late A responses cannot accidentally become B responses.
  let response;
  if(path==='/public/landing')return json({regions:[],region:null,scope:'national',searches:[],properties:[]});
  if(path==='/locations')return json({items:/Debrecen/i.test(url.searchParams.get('q')||'')?[city]:[]});
  if(path==='/streets')return json({items:[]});
  if(path==='/me'&&method==='PUT'){const body=request.postDataJSON();server.profiles[b?'b':'a']={name:body.name,email:body.email,phone:body.phone};return json({id:userId,...server.profiles[b?'b':'a'],accountType:'private'});}
  if(path==='/me'&&method==='GET')response={id:userId,name,email:profile.email,phone:profile.phone,accountType:'private',credits:100,unreadNotificationCount:0};
  else if(path==='/me/entities')response={properties:[property(id.owned,userId,b?'NEW_ACCOUNT_PROPERTY_CANARY':'OLD_ACCOUNT_PROPERTY_CANARY')],searchRequests:[search(userId)],active:{kind:'search',id:id.search},decisions:[],reportedOwnerIds:[],reportedEntities:[]};
  else if(path==='/credits/ledger'||path==='/matches')response={items:[]};
  else if(path==='/feedback/pending')response={feedbackPrompt:server.feedbackPrompt?structuredClone(server.feedbackPrompt):null};
  else if(path==='/test/feedback-scenario')response={available:false};
  else if(path==='/notifications'||path==='/incoming-likes')response={items:[],total:0,hasMore:false,active:{kind:'search',id:id.search}};
  else if(path==='/feed')response={active:{kind:'search',id:id.search},items:server.decided?[]:[{propertyId:id.candidate,searchRequestId:id.search,compatibilityScore:100,isExact:true,property:property(id.candidate,'foreign-owner','Valódi ajánlott otthon')}],stage:server.decided?'empty':'exact',hasApproximate:false};
  else if(path==='/impressions'&&method==='POST')return json({recorded:true});
  else if(path==='/decisions'&&method==='POST'){
   const pending=server.decisionGate;if(pending)await pending.promise;server.decided=true;
   return json({match:null,charged:0,feedbackPrompt:null});
  }else{server.unhandled.push(method+' '+path);return json({message:'Unexpected browser fixture route'},404);}
  const pending=server.readGate;if(pending)await pending.promise;
  return json(response);
 });
 const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',error=>server.errors.push(error.message));
 return {context,page,server};
}
async function freezeResume(page,{advanceClock=false}={}){
 await page.evaluate(advance=>{
  globalThis.__resumeVisibility='hidden';document.dispatchEvent(new Event('visibilitychange'));
  if(advance){const now=Date.now.bind(Date);Date.now=()=>now()+60000;}
 },advanceClock);
 const session=await page.context().newCDPSession(page);
 await session.send('Page.setWebLifecycleState',{state:'frozen'});
 await session.send('Page.setWebLifecycleState',{state:'active'});
 await page.bringToFront();
 await page.evaluate(()=>{
  globalThis.__resumeVisibility='visible';document.dispatchEvent(new Event('visibilitychange'));
  window.dispatchEvent(new Event('focus'));window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));
 });
 await session.detach();
}
async function navigate(page,viewport,destination){
 if(viewport.width<=720&&!await page.locator('#sidebar').evaluate(element=>element.classList.contains('open')))await interact(viewport,page.locator('.mobile-menu'));
 await interact(viewport,page.locator(`.nav-button[data-page="${destination}"]`));
 await page.waitForFunction(value=>location.hash==='#'+value,destination,{timeout:1500});
}
async function screenshot(page,name){await mkdir(resolve('.local/browser-tests/screenshots'),{recursive:true});await page.screenshot({path:resolve('.local/browser-tests/screenshots',name),fullPage:true}).catch(()=>{});}
async function inspect(fixture,verify,name){try{await verify();assert.deepEqual(fixture.server.unhandled,[]);assert.deepEqual(fixture.server.errors,[]);}catch(error){await screenshot(fixture.page,`tab-resume-${name}-failure.png`);throw error;}finally{fixture.server.readGate?.release();fixture.server.decisionGate?.release();await fixture.context.close();}}

async function readResponsiveness(browser,viewport){
 const t=await fixture(browser,viewport),{page,server}=t;
 await inspect(t,async()=>{
  await page.goto(origin+'/#discover',{waitUntil:'domcontentloaded'});await page.locator('#candidate').waitFor();
  server.readGate=gate();const before=server.gets.length;await freezeResume(page,{advanceClock:true});
  await eventually(()=>server.gets.length>before,'Returning to a stale authenticated tab should begin one readonly refresh');
  const refreshCalls=server.gets.slice(before);assert.ok(refreshCalls.filter(item=>item.path==='/me').length<=1,'A visible/focus/pageshow burst must not issue multiple account refreshes');
  await navigate(page,viewport,'settings');await page.locator('#profile-form').waitFor({timeout:1500});
  await page.locator('#f-name').fill('Még nem mentett név');
  await page.evaluate(()=>{globalThis.profileNode=document.getElementById('profile-form');});
  server.readGate.release();server.readGate=null;
  await page.locator('#workspace-refresh-status').waitFor({state:'hidden',timeout:5000});
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  assert.equal(await page.locator('#f-name').inputValue(),'Még nem mentett név','Late readonly data must preserve a dirty settings form');
  assert.equal(await page.evaluate(()=>globalThis.profileNode===document.getElementById('profile-form')),true,'Refreshing must preserve input focus and mounted form nodes');
  const profileSaved=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/me'&&response.request().method()==='PUT');
  await interact(viewport,page.locator('#profile-form button[type="submit"]'));assert.equal((await profileSaved).status(),200);
  await page.locator('#workspace-refresh-status').waitFor({state:'hidden',timeout:5000});
  const profileWrites=server.posts.filter(item=>item.path==='/me'&&item.method==='PUT');assert.equal(profileWrites.length,1);assert.deepEqual(profileWrites[0].body,{name:'Még nem mentett név',email:'a@example.test',phone:''});assert.equal(server.profiles.a.name,'Még nem mentett név','A real submit Event must retain its form before awaiting refresh');
  assert.equal(await page.locator('#f-name').inputValue(),'Még nem mentett név');
  server.readGate=gate();await freezeResume(page,{advanceClock:true});
  await navigate(page,viewport,'properties');await page.locator('.page-heading [data-action="new"]').waitFor({timeout:1500});
  await interact(viewport,page.locator('.page-heading [data-action="new"]'));await page.locator('#entity-form').waitFor({timeout:1500});
  await page.locator('#location-input').fill('Debrecen');await interact(viewport,page.locator('[data-location-id="city:Debrecen"]'));
  await page.locator('#f-street').fill('Megőrzendő utca');await page.locator('#f-houseNumber').fill('12/A');
  await page.evaluate(()=>{globalThis.editorNode=document.getElementById('entity-form');});
  await freezeResume(page);server.readGate.release();server.readGate=null;
  await page.locator('#workspace-refresh-status').waitFor({state:'hidden',timeout:5000});
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  assert.equal(await page.evaluate(()=>globalThis.editorNode===document.getElementById('entity-form')),true);
  assert.equal(await page.locator('#f-street').inputValue(),'Megőrzendő utca');assert.equal(await page.locator('#f-houseNumber').inputValue(),'12/A');
  await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await page.waitForFunction(()=>document.getElementById('entity-form')?.getAttribute('data-editor-current-step')==='2',null,{timeout:1500});
  assert.equal(server.posts.filter(item=>['/properties','/searches'].includes(item.path)).length,0,'Readonly resume cannot submit an unfinished wizard');assert.equal(server.posts.filter(item=>item.path==='/me').length,1,'Foregrounding cannot resubmit the explicitly saved profile');
  await interact(viewport,page.locator('.modal-close'));
  server.feedbackPrompt={id:'40000000-0000-4000-8000-000000000001',propertyId:id.candidate,sellerFirstName:'Péter',expiresAt:new Date(Date.now()+15*60000).toISOString()};
  await navigate(page,viewport,'discover');await page.locator('.feedback-survey').waitFor();
  await page.evaluate(()=>{globalThis.feedbackNode=document.querySelector('.feedback-survey');});await freezeResume(page,{advanceClock:true});
  assert.equal(await page.evaluate(()=>globalThis.feedbackNode===document.querySelector('.feedback-survey')),true,'A pending feedback question must survive resuming without being replaced');assert.equal(await page.locator('.feedback-answer').count(),8);
  assert.equal(await page.locator('.discovery-decision-dock:visible').count(),0);assert.equal(server.posts.filter(item=>item.path.startsWith('/feedback/')).length,0,'Foregrounding never answers or dismisses a feedback prompt automatically');
  console.log(`Tab resume reads ${viewport.name}: frozen/active lifecycle, event coalescing, immediate cached navigation, dirty form/editor and pending feedback preservation passed.`);
 },`reads-${viewport.name}`);
}
async function mutationOwnership(browser,viewport){
 const t=await fixture(browser,viewport),{page,server}=t;
 await inspect(t,async()=>{
  await page.goto(origin+'/#discover',{waitUntil:'domcontentloaded'});await page.locator('#candidate').waitFor();server.decisionGate=gate();
  await interact(viewport,page.locator('.discovery-decision-dock [data-action="like"]'));await eventually(()=>server.posts.some(item=>item.path==='/decisions'),'The first like should reach the API');
  await freezeResume(page,{advanceClock:true});
  const pendingLike=page.locator('.discovery-decision-dock [data-action="like"]');
  if(await pendingLike.isVisible()&&await pendingLike.isEnabled())await interact(viewport,pendingLike);else await page.keyboard.press('ArrowRight');
  assert.equal(server.posts.filter(item=>item.path==='/decisions').length,1,'A suspended write keeps its duplicate guard after foregrounding');
  server.readGate=gate();
  await navigate(page,viewport,'properties');await page.locator('.page-heading [data-action="new"]').waitFor({timeout:1500});await interact(viewport,page.locator('.page-heading [data-action="new"]'));await page.locator('#entity-form').waitFor({timeout:1500});
  await page.locator('#location-input').fill('Debrecen');await interact(viewport,page.locator('[data-location-id="city:Debrecen"]'));await page.locator('#f-street').fill('Teszt utca');await page.locator('#f-houseNumber').fill('9');
  await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await page.waitForFunction(()=>document.getElementById('entity-form')?.getAttribute('data-editor-current-step')==='2',null,{timeout:1500});
  await interact(viewport,page.locator('#editor-step-button-0'));await page.waitForFunction(()=>document.getElementById('entity-form')?.getAttribute('data-editor-current-step')==='0',null,{timeout:1500});
  await page.evaluate(()=>{globalThis.pendingWriteEditor=document.getElementById('entity-form');});
  const acknowledged=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/decisions');server.decisionGate.release();server.decisionGate=null;await acknowledged;
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  assert.equal(await page.evaluate(()=>globalThis.pendingWriteEditor===document.getElementById('entity-form')),true,'A late decision acknowledgement must not close a newer local editor');assert.equal(await page.locator('#f-street').inputValue(),'Teszt utca');assert.equal(await page.locator('#f-houseNumber').inputValue(),'9');
  await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await page.waitForFunction(()=>document.getElementById('entity-form')?.getAttribute('data-editor-current-step')==='2',null,{timeout:1500});
  assert.equal(server.posts.filter(item=>item.path==='/decisions').length,1,'Neither return events nor post-ack readonly refresh may replay the decision');
  console.log(`Tab resume writes ${viewport.name}: pending write stays single, local Next/Back stay usable before acknowledgement, a newer editor survives its response, and no automatic replay passed.`);
 },`writes-${viewport.name}`);
}
async function accountPrivacy(browser,viewport){
 const t=await fixture(browser,viewport),{page,context,server}=t;
 await inspect(t,async()=>{
  await page.goto(origin+'/#settings',{waitUntil:'domcontentloaded'});await page.locator('#profile-form').waitFor();assert.equal(await page.locator('#f-name').inputValue(),'OLD_ACCOUNT_A_CANARY');
  server.readGate=gate();await freezeResume(page,{advanceClock:true});
  const other=await context.newPage();await other.goto(origin+'/runtime-config.js',{waitUntil:'domcontentloaded'});
  await other.evaluate(origin=>localStorage.setItem('otthonra.api',JSON.stringify({baseUrl:origin,token:'resume-session-b'})),origin);
  await page.bringToFront();
  await eventually(async()=>!(await page.locator('#app').innerText()).includes('OLD_ACCOUNT_A_CANARY'),'Changing account in another tab must hide the old private snapshot before a new GET returns');
  assert.doesNotMatch(await page.locator('#app').innerText(),/OLD_ACCOUNT_PROPERTY_CANARY/);
  server.readGate.release();server.readGate=null;await page.locator('#profile-form').waitFor();await eventually(async()=>await page.locator('#f-name').inputValue()==='NEW_ACCOUNT_B_CANARY','The new account should replace the cleared snapshot');
  await other.close();assert.doesNotMatch(await page.locator('#app').innerText(),/OLD_ACCOUNT_A_CANARY|OLD_ACCOUNT_PROPERTY_CANARY/);
  console.log(`Tab resume account ${viewport.name}: cross-tab credentials invalidate private cached DOM and stale responses cannot restore it.`);
 },`account-${viewport.name}`);
}
async function guestDraftPreservation(browser,viewport){
 const t=await fixture(browser,viewport,{guest:true}),{page,server}=t;
 await inspect(t,async()=>{
  await page.goto(origin+'/#landing',{waitUntil:'domcontentloaded'});
  await page.evaluate(async city=>{
   const {createDraft,updateDraft,saveDraft,originFromLocations}=await import('/onboarding.js');
   saveDraft(updateDraft(createDraft('search',{type:'Lakás',locationIds:[city.id],maxPrice:90,minArea:40},{origin:originFromLocations([city.id]),editor:{locations:[city],titleGenerated:true}}),{step:2}));
  },city);
  await page.goto(origin+'/#onboarding');await page.locator('#entity-form').waitFor();await page.locator('#f-maxPrice').fill('123.5');await page.locator('#f-maxArea').fill('');
  await interact(viewport,page.locator('#editor-step-button-0'));await page.locator('#location-input').fill('Hajdú');
  await page.evaluate(()=>{globalThis.guestForm=document.getElementById('entity-form');});
  await freezeResume(page,{advanceClock:true});
  assert.equal(await page.evaluate(()=>globalThis.guestForm===document.getElementById('entity-form')),true,'A resumed guest wizard keeps its original nodes');
  assert.equal(await page.locator('#f-maxPrice').inputValue(),'123.5');assert.equal(await page.locator('#f-maxArea').inputValue(),'');assert.equal(await page.locator('#location-input').inputValue(),'Hajdú','A partial location query is not lost on return');
  await page.locator('#location-input').fill('');await choosePropertyType(page,'Lakás',locator=>interact(viewport,locator));await interact(viewport,page.locator('#editor-next'));await page.waitForFunction(()=>document.getElementById('entity-form')?.getAttribute('data-editor-current-step')==='3',null,{timeout:1500});
  const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('otthonra.onboarding.v1')));assert.equal(saved.data.maxPrice,'123.5');assert.equal(saved.step,3);
  assert.ok(server.gets.every(item=>!item.token),'A guest draft must not start authenticated workspace reads');assert.equal(server.posts.length,0);
  console.log(`Tab resume guest ${viewport.name}: frozen/active lifecycle preserves raw draft fields, mounted wizard, step navigation and anonymous scope.`);
 },`guest-${viewport.name}`);
}

const browser=await chromium.launch({headless:true});let failures=0;
try{for(const viewport of viewports)for(const verify of [readResponsiveness,mutationOwnership,accountPrivacy,guestDraftPreservation]){try{await verify(browser,viewport);}catch(error){failures++;console.error(`${verify.name} ${viewport.name}: ${error.stack||error}`);}}}finally{await browser.close();}
if(failures)process.exitCode=1;
