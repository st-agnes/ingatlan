/** Account-wide notification navigation at desktop, tablet and mobile sizes.
 * HTTP fixtures keep event identity, menu-visit counts and per-row reads deterministic; the real
 * MySQL companion smoke verifies atomic creation, privacy and restart behavior.
 */
import {mockMapTiles} from './map-browser-network.mjs';
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
const ids={user:'10000000-0000-4000-8000-000000000001',search:'20000000-0000-4000-8000-000000000001',property:'30000000-0000-4000-8000-000000000001',inactive:'30000000-0000-4000-8000-000000000002',deleted:'30000000-0000-4000-8000-000000000003',foreignSearch:'40000000-0000-4000-8000-000000000001',foreignProperty:'50000000-0000-4000-8000-000000000001',match:'60000000-0000-4000-8000-000000000001',secondMatch:'60000000-0000-4000-8000-000000000002'};
const notices=Object.fromEntries(['like','match','message','feedback','credit','refund','completed','expired','deleted'].map((kind,index)=>[kind,`70000000-0000-4000-8000-${String(index+1).padStart(12,'0')}`]));
const timestamp='2026-11-19T10:00:00Z';
const clone=value=>JSON.parse(JSON.stringify(value));
const interact=(viewport,locator)=>viewport.touch?locator.tap():locator.click();
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function eventually(check,message,timeout=2000){const end=Date.now()+timeout;while(Date.now()<end){if(await check())return;await pause(10);}assert.ok(await check(),message);}
function gate(){let release;const promise=new Promise(resolve=>{release=resolve;});return {promise,release};}
function property(id,ownerId,title){return {id,ownerId,title,type:'Lakás',locationId:city.id,location:city,city:city.city,price:65000000,area:60,rooms:2,wholeRooms:2,halfRooms:0,condition:'Jó',building:'Tégla',images:[],address:'',balcony:false,elevator:false,archived:false,createdAt:timestamp};}
function search(id,ownerId,title){return {id,ownerId,title,type:'Lakás',locationIds:[city.id],locations:[city],city:city.city,minPrice:null,maxPrice:90000000,minArea:40,maxArea:null,minRooms:1,maxRooms:null,conditions:[],buildings:[],constructionAges:[],views:[],floors:[],heatingTypes:[],balcony:false,elevator:false,description:'A pontos feltételek alapján keresek.',archived:false,createdAt:timestamp};}
function target(page,entityKind=null,entityId=null,propertyId=null,searchRequestId=null,matchId=null){return {page,entityKind,entityId,propertyId,searchRequestId,matchId};}
function notice(id,kind,text,to,extra={}){return {id,kind,text,target:to,amount:0,decisionId:null,feedbackPackageId:null,createdAt:timestamp,readAt:null,...extra};}
function initialNotices(){return [
 notice(notices.like,'incoming_like','Eszter kedvelte a második ingatlanodat.',target('incoming','property',ids.inactive,ids.inactive,ids.foreignSearch)),
 notice(notices.match,'match_created','Új párosításod született.',target('messages','search',ids.search,ids.foreignProperty,ids.search,ids.match)),
 notice(notices.message,'message_received','Új üzenet érkezett a keresési igényedhez.',target('messages','search',ids.search,ids.foreignProperty,ids.search,ids.match)),
 notice(notices.feedback,'feedback_received','Új név nélküli visszajelzés érkezett.',target('insights','property',ids.inactive,ids.inactive)),
 notice(notices.credit,'credit_added','Kreditjóváírás <b>csak szöveg</b>.',target('credits'),{amount:20}),
 notice(notices.refund,'like_refund','Korábbi kedvelésed kreditjeit visszatérítettük.',target('credits'),{amount:2,readAt:'2026-11-19T10:01:00Z'}),
 notice(notices.completed,'feedback_completed','A visszajelzés-csomag teljesült.',target('insights','property',ids.inactive,ids.inactive)),
 notice(notices.expired,'feedback_expired','Lejárt a visszajelzés-csomag.',target('insights','property',ids.inactive,ids.inactive)),
 notice(notices.deleted,'incoming_like','Egy régebbi, már törölt profilodhoz tartozó kedvelés.',target('incoming','property',ids.deleted,ids.deleted,ids.foreignSearch))
 ];}
function match(id,ownedProperty,foreignSearch){return {id,property:ownedProperty,searchRequest:foreignSearch,contact:{id:'foreign-match-owner',name:'Teszt Eszter',email:'mutual-contact@example.test',phone:'+36 30 555 0101'},createdAt:timestamp,messages:[{id:'message-'+id,matchId:id,senderId:'foreign-match-owner',text:'Megőrzött beszélgetés törölt profilhoz.',createdAt:timestamp}],unread:1};}
async function fixture(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await mockMapTiles(context);
 const ownedSearch=search(ids.search,ids.user,'Aktív keresési igény'),foreignSearch=search(ids.foreignSearch,'foreign-search-owner','Régebbi, pontosan ezt az otthont kereső igény');
 foreignSearch.ownerFirstName='Eszter';foreignSearch.ownerAccountType='private';foreignSearch.email='PRIVATE_FOREIGN_CONTACT@example.test';foreignSearch.phone='PRIVATE_FOREIGN_PHONE';
 const server={properties:[property(ids.property,ids.user,'Első eladó ingatlan'),property(ids.inactive,ids.user,'Második, nem aktív ingatlan')],searches:[ownedSearch],foreignSearch,active:{kind:'search',id:ids.search},notifications:initialNotices(),gets:[],writes:[],reads:[],activations:[],incomingOffsets:[],decisions:[],deletions:[],unhandled:[],errors:[],markGate:null,credits:100,lastVisit:null,visits:[],clock:Date.parse(timestamp)+600000};
 server.matches=[match(ids.match,property(ids.foreignProperty,'foreign-property-owner','Meglévő párosítás ingatlana'),ownedSearch)];
 const pendingPairs=()=>{const own=server.properties.find(item=>item.id===server.active?.id),allPairs=own?.id===ids.inactive?Array.from({length:51},(_,index)=>({property:clone(own),searchRequest:index===50?clone(server.foreignSearch):search(`40000000-0000-4000-8000-${String(index+100).padStart(12,'0')}`,'other-search-owner',`Újabb érdeklődő ${index+1}`),compatibilityScore:100,isExact:true,compatible:true,likedYou:true,likedAt:timestamp,myDecision:null,matchId:null})):[];return allPairs.filter(item=>!server.decisions.some(decision=>decision.propertyId===item.property.id&&decision.searchRequestId===item.searchRequest.id)&&!server.matches.some(value=>value.property.id===item.property.id&&value.searchRequest.id===item.searchRequest.id));};
 const unread=()=>server.notifications.filter(item=>!item.readAt).length;
 const newCount=()=>server.notifications.filter(item=>server.lastVisit==null||Date.parse(item.createdAt)>Date.parse(server.lastVisit)).length;
 const tick=()=>new Date(server.clock+=1000).toISOString();
 const receipt=item=>({...clone(item),unreadCount:unread()});
 const contextFor=item=>{
  const to=item.target,own=(to?.entityKind==='property'?server.properties:server.searches).find(entity=>entity.id===to?.entityId);
  const hasMatch=to?.page==='messages'&&server.matches.some(value=>value.id===to.matchId);
  const available=to?.page==='credits'||hasMatch||!!own&&!own.archived;
  const incoming=available&&item.kind==='incoming_like'?{property:clone(own),searchRequest:clone(server.foreignSearch),propertyId:own.id,searchRequestId:server.foreignSearch.id,compatibilityScore:100,isExact:true,reasons:[],matchDetails:[],likedYou:true,likedAt:timestamp,myDecision:null,matchId:null,compatible:true,searchSpecificity:65,valueForMoney:1}:null;
  return {notification:clone(item),available,target:clone(to),canActivate:available&&!!own&&!own.archived,item:incoming};
 };
 await context.addInitScript(origin=>localStorage.setItem('otthonra.api',JSON.stringify({baseUrl:origin,token:'notification-browser-session'})),origin);
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 await context.route(`${origin}/runtime-config.js`,route=>route.fulfill({status:200,contentType:'text/javascript',body:'globalThis.OTTHONRA_CONFIG=Object.freeze({mode:"api",environment:"test"});'}));
 await context.route(`${origin}/api/**`,async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname.slice(4),method=request.method();
  const json=async(data,status=200)=>{try{return await route.fulfill({status,contentType:'application/json',body:data==null?'':JSON.stringify(data)});}catch(error){if(!/closed|handled|intercept|abort/i.test(String(error)))throw error;}};
  if(method==='GET')server.gets.push(path);else server.writes.push({path,method,body:request.postData()?request.postDataJSON():null});
  if(path==='/me'&&method==='GET')return json({id:ids.user,name:'Teszt Tulajdonos',email:'owner@example.test',phone:'',accountType:'private',credits:server.credits,unreadNotificationCount:unread(),newNotificationCount:newCount(),notificationLastVisitAt:server.lastVisit,pendingIncomingLikeCount:pendingPairs().length});
  if(path==='/me/entities')return json({properties:clone(server.properties.filter(item=>!item.archived)),searchRequests:clone(server.searches.filter(item=>!item.archived)),active:clone(server.active),decisions:[],reportedOwnerIds:[],reportedEntities:[]});
  if(path==='/credits/ledger')return json({items:[{id:'initial-credit',amount:100,description:'Kezdő tesztkreditek',createdAt:timestamp}]});
  if(path==='/notifications'&&method==='GET')return json({items:clone(server.notifications),total:server.notifications.length,unreadCount:unread(),newCount:newCount(),visitedAt:server.lastVisit,visitThrough:tick(),offset:0,limit:50,hasMore:false});
  if(path==='/notifications/visit'&&method==='POST'){const {through}=request.postDataJSON();assert.ok(Number.isFinite(Date.parse(through)));assert.ok(Date.parse(through)<=server.clock,'A visit acknowledges only events through the returned page watermark');server.visits.push(through);if(server.lastVisit==null||Date.parse(through)>Date.parse(server.lastVisit))server.lastVisit=through;return json({newCount:newCount(),visitedAt:server.lastVisit});}
  const contextPath=path.match(/^\/notifications\/([^/]+)\/context$/);
  if(contextPath){const item=server.notifications.find(value=>value.id===contextPath[1]);return item?json(contextFor(item)):json({message:'Az értesítés nem található.'},404);}
  const readPath=path.match(/^\/notifications\/([^/]+)\/read$/);
  if(readPath&&method==='PUT'){
   const item=server.notifications.find(value=>value.id===readPath[1]);if(!item)return json({message:'Az értesítés nem található.'},404);
   server.reads.push(item.id);const pending=server.markGate;if(pending)await pending.promise;
   item.readAt??='2026-11-19T10:05:00Z';return json(receipt(item));
  }
  if(path==='/me/active'&&method==='PUT'){const body=request.postDataJSON();server.activations.push(body);const own=(body.kind==='property'?server.properties:server.searches).find(item=>item.id===body.id&&!item.archived);if(!own)return json({message:'A profil már törölve lett.'},404);server.active={kind:body.kind,id:body.id};return json(server.active);}
  if(path==='/incoming-likes'){
   const offset=Number(url.searchParams.get('offset')||0),limit=Number(url.searchParams.get('limit')||50);server.incomingOffsets.push(offset);
   const pairs=pendingPairs();
   return json({active:clone(server.active),items:pairs.slice(offset,offset+limit),total:pairs.length,offset,limit,hasMore:offset+limit<pairs.length,likeCost:server.active?.kind==='property'?2:0});
  }
  if(path==='/matches')return json({items:clone(server.matches)});
  const matchRead=path.match(/^\/matches\/([^/]+)\/read$/);if(matchRead&&method==='PUT'){const item=server.matches.find(value=>value.id===matchRead[1]);if(!item)return json({message:'A párosítás nem található.'},404);item.unread=0;return json({read:true});}
  if(path==='/feedback/pending')return json({feedbackPrompt:null});
  if(path==='/test/feedback-scenario')return json({available:false});
  if(path==='/feed')return json({active:clone(server.active),items:[],stage:'empty',hasApproximate:false});
  if(path.endsWith('/insights')){const id=path.split('/')[2];return json({propertyId:id,stats:{uniqueViewers:10,buyerLikes:3,sellerLikes:2,matchedViewers:1,matchRate:10},feedback:{total:1,items:[{id:'anonymous-feedback',reason:'layout',createdAt:timestamp}],reasonCounts:[{reason:'layout',count:1}],offset:0,limit:50,hasMore:false},activePackage:null,packages:[]});}
  if(path==='/decisions'&&method==='POST'){
   const body=request.postDataJSON();server.decisions.push(body);assert.equal(server.active.kind,'property');assert.equal(server.active.id,ids.inactive);
   assert.deepEqual([body.propertyId,body.searchRequestId,body.liked],[ids.inactive,ids.foreignSearch,true]);
   server.matches.push(match(ids.secondMatch,clone(server.properties.find(item=>item.id===ids.inactive)),clone(server.foreignSearch)));server.credits-=2;
   return json({matchId:ids.secondMatch,charged:2,credits:server.credits,feedbackPrompt:null});
  }
  const deleting=path.match(/^\/(properties|searches)\/([^/]+)$/);
  if(deleting&&method==='DELETE'){
   const collection=deleting[1]==='properties'?server.properties:server.searches,item=collection.find(value=>value.id===deleting[2]);if(!item)return json({message:'A profil nem található.'},404);
   item.archived=true;server.deletions.push(item.id);if(server.active?.id===item.id)server.active=null;return json(null,204);
  }
  server.unhandled.push(method+' '+path);return json({message:'Unexpected notification browser fixture route'},404);
 });
 const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',error=>server.errors.push(error.message));
 return {context,page,server,unread,newCount,tick};
}
async function navigate(page,viewport,destination){
 if(viewport.width<=720&&!await page.locator('#sidebar').evaluate(element=>element.classList.contains('open')))await interact(viewport,page.locator('.mobile-menu'));
 await interact(viewport,page.locator(`.nav-button[data-page="${destination}"]`));await page.waitForFunction(value=>location.hash==='#'+value,destination,{timeout:2000});
}
async function screenshot(page,name){await mkdir(resolve('.local/browser-tests/screenshots'),{recursive:true});await page.screenshot({path:resolve('.local/browser-tests/screenshots',name),fullPage:true}).catch(()=>{});}
async function inspect(t,verify,name){try{await verify();assert.deepEqual(t.server.unhandled,[]);assert.deepEqual(t.server.errors,[]);}catch(error){await screenshot(t.page,`activity-notifications-${name}-failure.png`);throw error;}finally{t.server.markGate?.release();await t.context.close();}}
async function readyNotifications(page){await page.locator('#notifications-list').waitFor();await page.locator('#workspace-refresh-status').waitFor({state:'hidden'});}
async function badge(page,value){await eventually(async()=>value===0?await page.locator('#notifications-nav-count').isHidden()&&await page.locator('#notifications-top-count').isHidden():await page.locator('#notifications-nav-count').innerText()===String(value)&&await page.locator('#notifications-top-count').innerText()===String(value),`Both new-event badges should show ${value}`);}
async function incomingBadge(page,value){const indicator=page.locator('#incoming-nav-count');await eventually(async()=>value===0?await indicator.isHidden():await indicator.isVisible()&&await indicator.innerText()===String(value),`The active-profile pending badge should show ${value}`);}
const card=(page,id)=>page.locator(`[data-notification-id="${id}"]`);
async function openNotice(page,viewport,id){await interact(viewport,card(page,id).locator('[data-action="notification-open"]'));}

async function accountWideLikes(browser,viewport){
 const t=await fixture(browser,viewport),{page,server,unread,tick}=t;
 await inspect(t,async()=>{
  await page.goto(origin+'/#discover',{waitUntil:'domcontentloaded'});await page.locator('.page-heading').waitFor();await badge(page,9);await incomingBadge(page,0);assert.equal(unread(),8,'An already-read event still counts as new until the notifications menu is visited');assert.equal(server.visits.length,0);
  await navigate(page,viewport,'notifications');await readyNotifications(page);
  assert.equal(await page.locator('[data-notification-id]').count(),9);await badge(page,0);assert.equal(server.visits.length,1);assert.equal(await page.locator('.notification-card.is-unread').count(),8,'Opening the menu does not read individual notification rows');
  assert.equal(server.reads.length,0,'Viewing the list cannot silently mark every event as read');assert.equal(server.active.id,ids.search);
  for(const label of ['Új kedvelés','Új párosítás','Új üzenet','Új visszajelzés','Kreditjóváírás','Kreditvisszatérítés','Teljesült a visszajelzés-csomagod','Lejárt a visszajelzés-csomagod'])assert.ok((await page.locator('#notifications-list').innerText()).includes(label),label);
  assert.match(await card(page,notices.like).innerText(),/Második, nem aktív ingatlan/);
  assert.doesNotMatch(await page.locator('#notifications-list').innerText(),/PRIVATE_FOREIGN_CONTACT|PRIVATE_FOREIGN_PHONE/);
  assert.equal(await card(page,notices.credit).locator('b').count(),0,'Notification text must be escaped');
  assert.equal(await card(page,notices.like).locator('.refund-amount').count(),0,'Noncredit activity is not displayed as a refund');
  server.markGate=gate();await interact(viewport,card(page,notices.credit).locator('[data-action="notification-read"]'));
  await eventually(()=>server.reads.includes(notices.credit),'Mark-read should reach the API');await badge(page,0);assert.match(await card(page,notices.credit).getAttribute('class'),/is-unread/);
  server.markGate.release();server.markGate=null;await eventually(async()=>!(await card(page,notices.credit).getAttribute('class')).includes('is-unread'),'The explicit read receipt updates only its notification row');await badge(page,0);
  const firstRead=server.notifications.find(item=>item.id===notices.credit).readAt;
  await openNotice(page,viewport,notices.like);await page.locator(`.modal[data-notification-context="${notices.like}"]`).waitFor();
  assert.deepEqual(server.activations.at(-1),{kind:'property',id:ids.inactive});assert.equal(server.active.id,ids.inactive);
  assert.equal(server.decisions.length,0,'Opening a notification does not send a reciprocal like');
  assert.match(await page.locator('.modal h2').innerText(),/Régebbi, pontosan ezt az otthont kereső igény/);
  assert.doesNotMatch(await page.locator('.modal').innerText(),/PRIVATE_FOREIGN_CONTACT|PRIVATE_FOREIGN_PHONE|mutual-contact@example/);
  assert.ok(server.gets.includes(`/notifications/${notices.like}/context`));assert.ok(server.gets.includes('/incoming-likes'));
  assert.equal(await page.locator('.incoming-card').count(),50);await incomingBadge(page,51);assert.equal(await page.locator(`.incoming-card[data-id="${ids.foreignSearch}"]`).count(),0,'The notified older like is beyond the ordinary first page');assert.ok(server.incomingOffsets.every(offset=>offset===0),'Opening one older event does not scan every incoming page');
  await badge(page,0);assert.match(await page.locator('.breadcrumb').innerText(),/Téged kedveltek/);
  await interact(viewport,page.locator('.modal [data-action="incoming-like"]'));await eventually(()=>server.decisions.length===1,'The exact notification context should remain actionable');
  assert.deepEqual([server.decisions[0].propertyId,server.decisions[0].searchRequestId],[ids.inactive,ids.foreignSearch]);
  await page.getByRole('heading',{name:'Kölcsönös az érdeklődés!',exact:true}).waitFor();await interact(viewport,page.locator('.modal [data-action="close"]').last());await incomingBadge(page,50);
  await navigate(page,viewport,'notifications');await readyNotifications(page);await badge(page,0);
  assert.doesNotMatch(await card(page,notices.like).getAttribute('class'),/is-unread/);assert.equal(server.notifications.find(item=>item.id===notices.credit).readAt,firstRead);
  await page.reload({waitUntil:'domcontentloaded'});await readyNotifications(page);await badge(page,0);assert.equal(server.notifications.find(item=>item.id===notices.credit).readAt,firstRead);
  // A later event is new even when its row is read without visiting the menu.
  await navigate(page,viewport,'discover');const laterId='70000000-0000-4000-8000-000000000010';
  server.notifications.push(notice(laterId,'credit_added','Újabb esemény az előző menümegnyitás után.',target('credits'),{createdAt:tick(),amount:1}));
  await page.reload({waitUntil:'domcontentloaded'});await page.locator('.page-heading').waitFor();await badge(page,1);const visitsBeforeRead=server.visits.length;
  await page.evaluate(async id=>{const model=(await import('/api.js')).getModel();await model.getNotificationContext(id);await model.markNotificationRead(id);},laterId);
  await navigate(page,viewport,'properties');await page.locator('.entity-grid').waitFor();await badge(page,1);assert.equal(server.visits.length,visitsBeforeRead,'Context lookup and explicit per-row read do not acknowledge a menu visit');assert.ok(server.notifications.find(item=>item.id===laterId).readAt);
  await navigate(page,viewport,'notifications');await readyNotifications(page);await badge(page,0);assert.equal(server.visits.length,visitsBeforeRead+1);assert.doesNotMatch(await card(page,laterId).getAttribute('class'),/is-unread/);
  console.log(`Activity notifications likes ${viewport.name}: account-wide kinds, independent durable row reads and menu-visit badges, inactive profile activation and exact older-like context/reply passed.`);
 },`likes-${viewport.name}`);
}
async function eventTargets(browser,viewport){
 const t=await fixture(browser,viewport),{page,server}=t;server.active={kind:'property',id:ids.property};
 await inspect(t,async()=>{
  await page.goto(origin+'/#notifications',{waitUntil:'domcontentloaded'});await readyNotifications(page);
  await openNotice(page,viewport,notices.message);await page.locator('#chat-form').waitFor();assert.equal(new URL(page.url()).hash,'#messages');
  assert.deepEqual(server.activations.at(-1),{kind:'search',id:ids.search});assert.match(await page.locator('.chat-header').innerText(),/Teszt Eszter/);assert.match(await page.locator('#chat-messages').innerText(),/Megőrzött beszélgetés/);
  await navigate(page,viewport,'notifications');await readyNotifications(page);await openNotice(page,viewport,notices.feedback);
  await page.locator(`.property-insights[data-property-id="${ids.inactive}"]`).waitFor();assert.equal(server.active.id,ids.inactive);assert.match(await page.locator('.insights-property-heading h2').innerText(),/Második, nem aktív ingatlan/);assert.match(await page.locator('.feedback-results').innerText(),/Nem tetszik az ingatlan elrendezése/);
  const beforeCredits=server.activations.length;await navigate(page,viewport,'notifications');await readyNotifications(page);await openNotice(page,viewport,notices.credit);
  await page.waitForFunction(()=>location.hash==='#credits');await page.locator('.credit-hero').waitFor();assert.equal(server.activations.length,beforeCredits,'A balance notification must not activate an arbitrary profile');
  assert.ok(server.notifications.find(item=>item.id===notices.message).readAt);assert.ok(server.notifications.find(item=>item.id===notices.feedback).readAt);assert.ok(server.notifications.find(item=>item.id===notices.credit).readAt);
  console.log(`Activity notifications targets ${viewport.name}: specific conversation, seller feedback profile and credits destinations passed.`);
 },`targets-${viewport.name}`);
}
async function deletionAndUnavailable(browser,viewport){
 const t=await fixture(browser,viewport),{page,server}=t;server.notifications=server.notifications.filter(item=>item.id===notices.deleted);
 server.matches=[match(ids.secondMatch,clone(server.properties.find(item=>item.id===ids.inactive)),clone(server.foreignSearch))];
 await inspect(t,async()=>{
  await page.goto(origin+'/#notifications',{waitUntil:'domcontentloaded'});await readyNotifications(page);await badge(page,0);assert.equal(server.notifications[0].readAt,null);await openNotice(page,viewport,notices.deleted);
  await page.getByRole('heading',{name:'Az esemény már nem nyitható meg.',exact:true}).waitFor();await badge(page,0);assert.equal(server.activations.length,0);assert.equal(server.decisions.length,0);
  await interact(viewport,page.locator('.modal').getByRole('button',{name:'Rendben',exact:true}));
  await navigate(page,viewport,'properties');const deleting=page.locator(`[data-action="delete"][data-kind="property"][data-id="${ids.inactive}"]`);await deleting.waitFor();
  assert.match((await deleting.getAttribute('aria-label'))||'',/törlés/i);await interact(viewport,deleting);
  const confirmation=page.locator('.modal');assert.match(await confirmation.innerText(),/Törl/);assert.doesNotMatch(await confirmation.innerText(),/Archiv/);
  await interact(viewport,confirmation.locator(`[data-action="confirm-delete"][data-id="${ids.inactive}"]`));
  await eventually(()=>server.deletions.includes(ids.inactive),'The delete action should use the existing soft-retaining API');
  await eventually(async()=>await page.locator(`[data-action="delete"][data-id="${ids.inactive}"]`).count()===0,'Deleted profiles disappear from the owner list');
  assert.equal(server.properties.find(item=>item.id===ids.inactive).archived,true);assert.equal(server.matches.length,1);assert.equal(await page.locator('[data-action="restore"]').count(),0);
  const archivedMatch=notice(notices.match,'match_created','Meglévő párosítás a törölt profilodból.',target('messages','property',ids.inactive,ids.inactive,ids.foreignSearch,ids.secondMatch));server.notifications.push(archivedMatch);
  await navigate(page,viewport,'notifications');await readyNotifications(page);const beforeHistory=server.activations.length;await openNotice(page,viewport,notices.match);
  await page.locator('#chat-form').waitFor();assert.equal(server.activations.length,beforeHistory,'Historical conversations stay available without restoring or activating a deleted profile');assert.equal(server.active.id,ids.search);
  assert.match(await page.locator('#chat-messages').innerText(),/Megőrzött beszélgetés törölt profilhoz/);assert.equal(server.notifications.find(item=>item.id===notices.match).readAt,'2026-11-19T10:05:00Z');
  console.log(`Activity notifications deletion ${viewport.name}: selected unavailable event is seen, zero badges hide, deletion wording is honest and existing conversations survive without restoration passed.`);
 },`delete-${viewport.name}`);
}

const browser=await chromium.launch({headless:true});let failures=0;
try{for(const viewport of viewports)for(const verify of [accountWideLikes,eventTargets,deletionAndUnavailable]){try{await verify(browser,viewport);}catch(error){failures++;console.error(`${verify.name} ${viewport.name}: ${error.stack||error}`);}}}finally{await browser.close();}
if(failures)process.exitCode=1;
