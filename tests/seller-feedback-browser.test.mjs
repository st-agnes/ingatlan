/** Seller packages/statistics and the buyer's single-click feedback gate, in real Chromium. */
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const modulePath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(resolve(modulePath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const screenshots=resolve('.local/browser-tests/screenshots');
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
const readState=page=>page.evaluate(async()=> (await import('/model.js')).model.getState());
async function freshDemo(page){
 await page.goto(origin+'/#discover',{waitUntil:'domcontentloaded'});await page.locator('.page-heading').waitFor();
 await page.evaluate(async()=>{const {createModel,STORAGE_KEY}=await import('/model.js');let raw;const demo=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}});demo.activate('search','own-s1');localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));});
 await page.reload({waitUntil:'domcontentloaded'});await page.locator('#candidate').waitFor();
 await page.locator('#candidate .property-image').scrollIntoViewIfNeeded();
 await page.waitForFunction(async()=>{const {STORAGE_KEY}=await import('/model.js');const raw=JSON.parse(localStorage.getItem(STORAGE_KEY));return raw.propertyImpressions?.some(item=>item.propertyId==='p1'&&item.viewerUserId==='me');});
}
async function buyerFixture(page){
 await freshDemo(page);
 await page.evaluate(async()=>{
  const {createModel,STORAGE_KEY}=await import('/model.js');let raw=JSON.parse(localStorage.getItem(STORAGE_KEY));
  raw.userId='u1';raw.credits=100;raw.active={kind:'property',id:'p1'};localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));
  createModel(localStorage).buyFeedbackPackage('p1',10,'11111111-1111-4111-8111-111111111111');
  raw=JSON.parse(localStorage.getItem(STORAGE_KEY));raw.userId='me';raw.credits=24;raw.active={kind:'search',id:'own-s1'};raw.users.find(user=>user.id==='me').feedbackPassCounter=19;
  localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));
 });
 await page.reload({waitUntil:'domcontentloaded'});await page.locator('#candidate').waitFor();
}
async function verify(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 const page=await context.newPage();page.setDefaultTimeout(12000);const errors=[];page.on('pageerror',error=>errors.push(error.message));
 // Locator actions scroll and retry against the current DOM during route renders.
 const interact=locator=>viewport.touch?locator.tap():locator.click();
 const navigate=async name=>{if(await page.locator('.mobile-menu').isVisible())await interact(page.locator('.mobile-menu'));await interact(page.locator(`.nav-button[data-page="${name}"]`));await page.waitForFunction(expected=>location.hash===`#${expected}`,name);};
 try{
  await freshDemo(page);
  await navigate('properties');
  await interact(page.locator('.property-insights-button').first());await page.locator('.property-insights').waitFor();
  assert.equal(await page.locator('.insight-stat').count(),4);assert.match(await page.locator('.property-insights').innerText(),/Látták|Kedvelték|Kedvelt keresések|Párosítási arány/);
  assert.equal(await page.locator('.feedback-total').innerText(),'0 db');
  await interact(page.locator('[data-action="feedback-packages"]'));assert.equal(await page.locator('.feedback-plan').count(),3);
  await interact(page.locator('[data-action="feedback-plan"][data-size="50"]'));assert.equal(await page.locator('[data-action="feedback-buy"]').count(),0);assert.match(await page.locator('.modal').innerText(),/kreditre van szükséged/);
  await interact(page.locator('.modal [data-action="close"]').last());
  await interact(page.locator('[data-action="feedback-packages"]'));await interact(page.locator('[data-action="feedback-plan"][data-size="10"]'));
  const before=(await readState(page)).credits;await interact(page.locator('[data-action="feedback-buy"]'));await page.waitForFunction(()=>document.querySelector('.feedback-package-counts')?.textContent.includes('0 / 10'));
  assert.equal((await readState(page)).credits,before-10);assert.equal(await page.locator('[data-action="feedback-packages"]').count(),0);assert.match(await page.locator('.feedback-package-counts').innerText(),/0 \/ 10/);
  assert.equal(await page.locator('[data-action="feedback-toggle"]').count(),0,'An active prepaid feedback campaign cannot be paused');
  assert.doesNotMatch(await page.locator('.feedback-package-panel').innerText(),/szüneteltet|folytathatod/i);
  const layout=await page.locator('.property-insights').evaluate(element=>({width:element.clientWidth,scrollWidth:element.scrollWidth}));assert.ok(layout.scrollWidth<=layout.width+1,'Insights fit the viewport');
  await buyerFixture(page);
  const buyerCredits=(await readState(page)).credits;await interact(page.locator('.card-actions [data-action="pass"]'));await page.locator('.feedback-survey').waitFor();
  assert.match(await page.locator('#feedback-prompt-title').innerText(),/Segíts Péternek egy visszajelzéssel/);assert.equal(await page.locator('.feedback-answer').count(),8);assert.equal(await page.locator('#candidate').count(),0);assert.equal(await page.locator('.feedback-survey .modal-close').count(),0);
  assert.match(await page.locator('#feedback-prompt-question').innerText(),/Miért nem tetszett az ingatlan/);
  await page.reload({waitUntil:'domcontentloaded'});await page.locator('.feedback-survey').waitFor();assert.equal(await page.locator('#candidate').count(),0,'Reload cannot skip the pending question');
  await interact(page.locator('[data-action="feedback-answer"][data-reason="layout"]'));await page.locator('#candidate').waitFor();assert.equal(await page.locator('.feedback-survey').count(),0);assert.equal((await readState(page)).credits,buyerCredits);
  let saved=await page.evaluate(async()=>JSON.parse(localStorage.getItem((await import('/model.js')).STORAGE_KEY)));assert.equal(saved.feedbackPackages[0].receivedCount,1);assert.equal(saved.feedbackInvitations[0].reason,'layout');
  await page.evaluate(async()=>{const {STORAGE_KEY}=await import('/model.js');const raw=JSON.parse(localStorage.getItem(STORAGE_KEY));raw.userId='u1';raw.credits=90;raw.active={kind:'property',id:'p1'};localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));});
  await page.goto(origin+'/#insights',{waitUntil:'domcontentloaded'});await page.reload({waitUntil:'domcontentloaded'});await page.locator('.property-insights').waitFor();
  assert.equal(await page.locator('.feedback-total').innerText(),'1 db');assert.match(await page.locator('.feedback-history').innerText(),/Nem tetszik az ingatlan elrendezése/);assert.equal(await page.locator('.insight-stat').first().locator('strong').innerText(),'1 ember');
  await buyerFixture(page);await interact(page.locator('.card-actions [data-action="pass"]'));await page.locator('.feedback-survey').waitFor();
  await interact(page.locator('[data-action="feedback-answer"][data-reason="decline"]'));await page.locator('#candidate').waitFor();
  saved=await page.evaluate(async()=>JSON.parse(localStorage.getItem((await import('/model.js')).STORAGE_KEY)));assert.equal(saved.feedbackPackages[0].receivedCount,0,'Opt-out does not consume one of the seller feedback items');assert.equal(saved.feedbackInvitations[0].reason,'decline');
  assert.deepEqual(errors,[]);console.log(`Seller feedback ${viewport.name}: property-scoped statistics, prepaid continuously active package confirmation, visible impressions, blocking persisted one-click answers, anonymous results and non-counting opt-out passed.`);
 }catch(error){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`seller-feedback-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports)await verify(browser,viewport);}finally{await browser.close();}
