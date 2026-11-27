/** Actual HTML parsing and frame geometry for matched conversations and confirmation actions. */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {mockMapTiles} from './map-browser-network.mjs';
const modulePath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const screenshots=resolve('.local/browser-tests/screenshots');
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
const browser=await chromium.launch({headless:true});
try{
 for(const viewport of viewports){
  const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,isMobile:viewport.touch});
  await context.route(/https:\/\/fonts\.(?:googleapis|gstatic)\.com\//,route=>route.abort());await mockMapTiles(context);
  const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);
  const interact=locator=>viewport.touch?locator.tap():locator.click();
  try{
   await page.goto(origin+'/#messages',{waitUntil:'domcontentloaded'});await page.locator('.messages-layout>.chat').waitFor();
   const expected=await page.evaluate(async()=>{
    const {createModel,STORAGE_KEY}=await import('/model.js');let raw;
    const model=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}},()=>new Date().toISOString());model.activate('search','own-s1');
    const first=raw.matches.find(item=>item.id==='m1');first.messages=Array.from({length:45},(_,index)=>({id:'chat-geometry-'+index,senderId:index%2?'me':'u2',text:`Üzenet ${index}: `+'A megtekintés részleteit egyeztetjük. '.repeat(3),createdAt:new Date(Date.now()-60000*(45-index)).toISOString()}));
    const property=raw.properties.find(item=>item.id==='own-p1'),search=raw.searches.find(item=>item.id==='s1');
    raw.matches.push({id:'seller-chat',propertyId:property.id,searchId:search.id,createdAt:new Date(Date.now()-86400000).toISOString(),messages:[],unread:0});
    for(const [actorKind,actorId,actorUserId] of [['property',property.id,property.ownerId],['search',search.id,search.ownerId]]){const existing=raw.decisions.find(item=>item.propertyId===property.id&&item.searchId===search.id&&item.actorKind===actorKind);if(existing)existing.liked=true;else raw.decisions.push({id:'seller-chat-'+actorKind,propertyId:property.id,searchId:search.id,actorKind,actorId,actorUserId,liked:true,createdAt:new Date().toISOString(),charged:0});}
    localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));const current=createModel(localStorage),rows=current.matches();
    return rows.map(row=>{const kind=row.property.ownerId===raw.userId?'search':'property',entity=row[kind];return{id:row.id,kind,title:entity.title,key:entity.publicListingKey};});
   });
   await page.reload({waitUntil:'domcontentloaded'});await page.locator('.messages-layout').waitFor();await interact(page.locator('.conversation[data-id="m1"]'));
   assert.equal(await page.locator('.messages-layout>.conversation-list').count(),1);assert.equal(await page.locator('.messages-layout>.chat').count(),1,'Browser parsing keeps chat inside its white frame');
   assert.equal(await page.locator('.conversation button,.conversation a').count(),0,'Conversation-selection buttons contain no nested interactive badge or link');
   assert.equal(await page.locator('.conversation-row .conversation-context .advertiser-info button').count(),expected.length,'Account badge buttons remain independent siblings');
   for(const row of expected){const anchor=page.locator(`.conversation-row:has(.conversation[data-id="${row.id}"]) .conversation-listing-link`);assert.equal(await anchor.innerText(),row.title);assert.equal(await anchor.getAttribute('href'),`#listing/${row.kind}/${row.key}`);}
   const geometry=await page.evaluate(()=>{
    const frame=document.querySelector('.messages-layout'),chat=frame.querySelector(':scope>.chat'),header=chat.querySelector('.chat-header'),history=chat.querySelector('#chat-messages'),form=chat.querySelector('#chat-form');
    const rect=element=>{const r=element.getBoundingClientRect();return{x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
    return{frame:rect(frame),chat:rect(chat),header:rect(header),history:rect(history),form:rect(form),scrollHeight:history.scrollHeight,clientHeight:history.clientHeight};
   });
   assert.ok(geometry.history.y>=geometry.header.bottom-1);assert.ok(geometry.history.bottom<=geometry.form.y+1);assert.ok(geometry.form.bottom<=geometry.frame.bottom+1,'The composer stays inside the frame');assert.ok(geometry.history.right<=geometry.frame.right+1);assert.ok(geometry.scrollHeight>geometry.clientHeight+50,'Long histories scroll in their own bounded frame');
   await page.locator('#chat-messages').evaluate(element=>{element.scrollTop=element.scrollHeight;});
   await page.locator('#chat-form input').fill('Új üzenet a kereten belül <szöveg>');await interact(page.locator('#chat-form button'));await page.locator('.bubble.mine').filter({hasText:'Új üzenet a kereten belül <szöveg>'}).waitFor();
   assert.equal(await page.locator('.messages-layout>.chat #chat-messages .bubble.mine').filter({hasText:'Új üzenet a kereten belül <szöveg>'}).count(),1);
   const seller=expected.find(row=>row.id==='seller-chat');await interact(page.locator('.conversation[data-id="seller-chat"]'));assert.equal(await page.locator('.chat-header .conversation-listing-link').getAttribute('href'),`#listing/search/${seller.key}`);assert.equal(await page.locator('.chat-header .conversation-listing-link').innerText(),seller.title);
   await interact(page.locator('.chat-header [data-action="contact"]'));assert.equal(await page.locator('.modal .matched-listing-link').getAttribute('href'),`#listing/search/${seller.key}`);assert.equal(await page.locator('.modal [data-action="open-chat"][data-id="seller-chat"]').count(),1);await interact(page.locator('.modal-close'));
   await page.goto(origin+'/#matches',{waitUntil:'domcontentloaded'});await page.locator('.match-card').first().waitFor();
   for(const row of expected){const anchor=page.locator(`.match-card .matched-listing-link[href="#listing/${row.kind}/${row.key}"]`);assert.equal(await anchor.count(),1);assert.match(await anchor.evaluate(element=>getComputedStyle(element).textDecorationLine),/underline/);}
   // A new reciprocal decision exercises the actual confirmation dialog.
   await page.goto(origin+'/#discover',{waitUntil:'domcontentloaded'});await page.locator('#candidate').waitFor();await interact(page.locator('.discovery-decision-dock [data-action="like"]'));await page.getByRole('heading',{name:'Kölcsönös az érdeklődés!',exact:true}).waitFor();
   const modal=page.locator('.match-celebrate');assert.equal(await modal.locator('.match-connection-art [data-icon="contact"]').count(),1);assert.equal(await modal.locator('.match-hearts').count(),0);assert.equal(await modal.locator('p').innerText(),'Beszéljétek meg a következő lépést!');
   const actions=await modal.locator('.match-celebrate-actions>.btn').evaluateAll(items=>items.map(item=>{const r=item.getBoundingClientRect();return{x:r.x,y:r.y,height:r.height,bottom:r.bottom};}));assert.equal(actions.length,2);if(Math.abs(actions[0].y-actions[1].y)<2)assert.ok(Math.abs(actions[0].bottom-actions[1].bottom)<2,'Side-by-side confirmation buttons align');
   assert.deepEqual(errors,[]);console.log(`Conversation layout ${viewport.name}: parsed sibling controls, bounded scrolling messages/composer, exact buyer/seller profile links, contact context and aligned mutual-interest confirmation passed.`);
  }catch(error){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`conversation-layout-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}finally{await context.close();}
 }
}finally{await browser.close();}
