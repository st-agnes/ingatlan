/** Browser coverage for owner labels, reporting reasons and active-profile incoming likes. */
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
let visit=0;
const current=page=>page.evaluate(async()=> (await import('/model.js')).model.getState());
const raw=page=>page.evaluate(async()=>JSON.parse(localStorage.getItem((await import('/model.js')).STORAGE_KEY)));
const candidates=page=>page.evaluate(async()=> (await import('/model.js')).model.feed());
async function go(page,name='discover'){await page.goto(`${origin}/?interaction-visit=${++visit}#${name}`,{waitUntil:'domcontentloaded'});await page.locator('.page-heading').waitFor();}
async function createContext(browser,viewport){const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());return context;}
async function configure(page,accountType='private'){
 await go(page);
 await page.evaluate(async accountType=>{
  const {createModel,STORAGE_KEY}=await import('/model.js');let serialized;
  const demo=createModel({getItem:()=>null,setItem:(_key,value)=>{serialized=value;}});demo.activate('search','own-s1');
  const fixture=JSON.parse(serialized);fixture.users.find(user=>user.id==='me').accountType=accountType;fixture.users.find(user=>user.id==='u1').accountType='private';fixture.users.find(user=>user.id==='u2').accountType='agent';fixture.credits=24;fixture.reports=[];fixture.matches=[];
  const secondary=fixture.searches.find(search=>search.id==='own-s2');Object.assign(secondary,{title:'Másik saját keresés',locationIds:['district:Budapest:13'],city:'Budapest',districts:['XIII.']});
  const decision=(id,actorKind,actorId,propertyId,searchId,owner)=>({id,actorKind,actorId,actorUserId:owner,propertyId,searchId,liked:true,createdAt:'2026-11-07T08:00:00.000Z'});
  fixture.decisions=[decision('incoming-p1','property','p1','p1','own-s1','u1'),decision('incoming-p2','property','p2','p2','own-s1','u2'),decision('incoming-p4-other','property','p4','p4','own-s2','u4'),decision('incoming-s1','search','s1','own-p1','s1','u1'),decision('incoming-s2','search','s2','own-p1','s2','u2')];
  localStorage.setItem(STORAGE_KEY,JSON.stringify(fixture));
 },accountType);
 await go(page);
}
async function closeModal(page,interact){await interact(page.locator('.modal [data-action="close"]').last());await page.locator('.modal').waitFor({state:'detached'});}
async function activate(page,interact,kind,id){await go(page,kind==='property'?'properties':'searches');await interact(page.locator(`[data-action="activate-one"][data-kind="${kind}"][data-id="${id}"]`));await page.waitForFunction(expected=>location.hash==='#discover'&&document.querySelector('.active-strip .strip-title')?.textContent, id);}
async function chooseCandidate(page,interact,type){for(let count=0;count<20;count++){const first=(await candidates(page))[0];assert.ok(first,'Expected another candidate');if(first.ownerAccountType===type)return first;await interact(page.locator('.card-actions [data-action="pass"]'));}throw new Error('No candidate with the expected owner type.');}
async function screenshot(page,name){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,name),fullPage:true}).catch(()=>{});}
async function fit(locator){const geometry=await locator.evaluate(element=>({width:element.clientWidth,scrollWidth:element.scrollWidth}));assert.ok(geometry.scrollWidth<=geometry.width+1,'Interaction controls must fit without horizontal scrolling');}
async function enterIncoming(page,interact){const menu=page.locator('.mobile-menu');if(await menu.isVisible())await interact(menu);await interact(page.locator('.nav-button[data-page="incoming"]'));await page.waitForFunction(()=>location.hash==='#incoming');await page.locator('.incoming-grid,.empty-state,.empty').first().waitFor().catch(()=>{});}
async function switchIncoming(page,interact,kind,id){await interact(page.locator('[data-action="activate"]').first());await interact(page.locator(`.modal [data-action="activate-one"][data-kind="${kind}"][data-id="${id}"]`));await page.waitForFunction(()=>location.hash==='#incoming'&&!document.querySelector('.modal'));}
async function report(page,interact,kind,id,label){await interact(page.locator(`[data-action="report-account"][data-kind="${kind}"][data-id="${id}"]`).first());await page.getByRole('heading',{name:'Szabálytalan hirdetés?',exact:true}).waitFor();const select=page.locator('#f-reportReason');await select.selectOption({label});const reason=await select.inputValue();await interact(page.locator('.modal [data-action="confirm-report"]'));await page.locator('.modal').waitFor({state:'detached'});await page.waitForTimeout(30);return reason;}
async function verifyReports(browser,viewport){
 const context=await createContext(browser,viewport),page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await configure(page);const privateCandidate=await chooseCandidate(page,interact,'private');assert.equal(await page.locator('#candidate .private-badge').innerText(),'Magánszemély');
  const reportButton=page.locator(`[data-action="report-account"][data-kind="property"][data-id="${privateCandidate.id}"]`).first();assert.equal(await reportButton.innerText(),'Szabálytalan hirdetés?');
  await interact(reportButton);await page.getByRole('heading',{name:'Szabálytalan hirdetés?',exact:true}).waitFor();
  const options=await page.locator('#f-reportReason option').evaluateAll(items=>items.filter(item=>item.value).map(item=>item.textContent.trim()));assert.deepEqual(options,['Ingatlanközvetítő','Hamis, megtévesztő tartalom','Egyéb szabálytalanság']);
  await interact(page.locator('.modal [data-action="confirm-report"]'));assert.equal(await page.locator('.modal').count(),1,'A report requires one explicit reason');assert.equal((await raw(page)).reports.length,0);
  await closeModal(page,interact);
  const firstReason=await report(page,interact,'property',privateCandidate.id,'Ingatlanközvetítő');assert.equal(firstReason,'suspected_agent');let reports=(await raw(page)).reports;assert.equal(reports.length,1);assert.equal(reports[0].reason,firstReason);assert.equal(reports[0].entityId,privateCandidate.id);assert.ok(!Number.isNaN(Date.parse(reports[0].createdAt)));assert.equal((await current(page)).credits,24);
  await report(page,interact,'property',privateCandidate.id,'Ingatlanközvetítő');assert.equal((await raw(page)).reports.length,1,'The same entity and reason must be idempotent');
  const secondReason=await report(page,interact,'property',privateCandidate.id,'Hamis, megtévesztő tartalom');assert.equal(secondReason,'misleading_content');assert.equal((await raw(page)).reports.length,2,'Another reason on the same entity remains reportable');
  await go(page);assert.equal(await page.locator(`[data-action="report-account"][data-id="${privateCandidate.id}"]`).first().isEnabled(),true);assert.equal((await page.locator('#app').innerText()).includes(reports[0].createdAt),false,'Report timestamps must not render');
  const agentCandidate=await chooseCandidate(page,interact,'agent');assert.equal(await page.locator('#candidate .agent-badge').innerText(),'Ingatlanközvetítő');
  await interact(page.locator(`[data-action="report-account"][data-kind="property"][data-id="${agentCandidate.id}"]`).first());
  const agentOptions=await page.locator('#f-reportReason option').evaluateAll(items=>items.filter(item=>item.value&&!item.disabled).map(item=>item.textContent.trim()));assert.deepEqual(agentOptions,['Hamis, megtévesztő tartalom','Egyéb szabálytalanság']);await closeModal(page,interact);
  await report(page,interact,'property',agentCandidate.id,'Hamis, megtévesztő tartalom');reports=(await raw(page)).reports;assert.ok(reports.some(item=>item.entityId===agentCandidate.id&&item.reason==='misleading_content'));
  await activate(page,interact,'property','own-p1');const search=await chooseCandidate(page,interact,'private');assert.equal(search.kind,'search');assert.equal(await page.locator('#candidate .private-badge').innerText(),'Magánszemély');
  const other=await report(page,interact,'search',search.id,'Egyéb szabálytalanság');assert.equal(other,'other_violation');assert.ok((await raw(page)).reports.some(item=>item.entityKind==='search'&&item.entityId===search.id&&item.reason===other),'Search reports persist their own source and chosen reason');assert.equal((await current(page)).credits,24);
  await fit(page.locator('#candidate'));assert.deepEqual(errors,[]);console.log(`Interaction reports ${viewport.name}: explicit owner labels, universal reporting, owner-specific reasons, contextual deduplication, reload and timestamp privacy passed.`);
 }catch(error){await screenshot(page,`interaction-reports-${viewport.name}-failure.png`);throw error;}finally{await context.close();}
}
async function verifyPrivateIncoming(browser,viewport){
 const context=await createContext(browser,viewport),page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await configure(page);assert.match(await page.locator('.nav-button[data-page="incoming"]').innerText(),/Kedveltek/);await enterIncoming(page,interact);
  assert.equal(await page.locator('.incoming-card').count(),2);assert.equal(await page.locator('.incoming-card[data-id="p1"] .private-badge').innerText(),'Magánszemély');assert.equal(await page.locator('.incoming-card[data-id="p2"] .agent-badge').innerText(),'Ingatlanközvetítő');
  const visible=await page.locator('#app').innerText();assert.equal(visible.includes('peter@example.hu'),false);assert.equal(visible.includes('+36 30 555 0141'),false);const unchanged=await current(page);assert.equal(unchanged.decisions.length,0,'Viewing incoming likes cannot make a decision');assert.equal(unchanged.credits,24);
  await interact(page.locator('.incoming-card[data-id="p1"] [data-action="incoming-details"]'));assert.equal((await page.locator('.modal').innerText()).includes('peter@example.hu'),false);await fit(page.locator('.modal'));await closeModal(page,interact);
  await interact(page.locator('.incoming-card[data-id="p1"] [data-action="incoming-like"]'));await page.getByRole('heading',{name:'Egymásra találtatok!',exact:true}).waitFor();assert.equal((await current(page)).credits,24);await closeModal(page,interact);
  const accepted=(await current(page)).decisions.find(item=>item.actorKind==='search'&&item.propertyId==='p1'&&item.searchId==='own-s1');assert.equal(accepted.liked,true);assert.equal(await page.locator('.incoming-card[data-id="p1"] [data-action="open-chat"]').count(),1);
  await go(page,'incoming');assert.equal(await page.locator('.incoming-card').count(),2,'Returned likes and matches remain in the incoming list');
  await switchIncoming(page,interact,'search','own-s2');assert.equal((await current(page)).active.id,'own-s2');assert.equal(await page.locator('.incoming-card').count(),1);assert.equal(await page.locator('.incoming-card[data-id="p4"]').count(),1);assert.equal(await page.locator('.incoming-card[data-id="p1"]').count(),0,'Switching active profiles must discard the former incoming list');
  await interact(page.locator('.incoming-card[data-id="p4"] [data-action="incoming-pass"]'));await page.waitForFunction(async()=>{const state=(await import('/model.js')).model.getState();return state.decisions.some(item=>item.propertyId==='p4'&&item.searchId==='own-s2'&&item.liked===false);});assert.equal((await current(page)).credits,24);assert.equal(await page.locator('.incoming-card[data-id="p4"] [data-action="incoming-like"]').count(),0,'A final rejection cannot be re-liked from the incoming list');
  await switchIncoming(page,interact,'property','own-p1');assert.equal(await page.locator('.incoming-card').count(),2);assert.equal(await page.locator('.incoming-card[data-id="s1"] .private-badge').innerText(),'Magánszemély');assert.equal(await page.locator('.incoming-card[data-id="s2"] .agent-badge').innerText(),'Ingatlanközvetítő');
  await interact(page.locator('.incoming-card[data-id="s1"] [data-action="incoming-like"]'));await page.getByRole('heading',{name:'Egymásra találtatok!',exact:true}).waitFor();assert.equal((await current(page)).credits,22,'An incoming search costs the ordinary seller price');await closeModal(page,interact);assert.ok((await current(page)).decisions.some(item=>item.actorKind==='property'&&item.propertyId==='own-p1'&&item.searchId==='s1'&&item.liked));
  await fit(page.locator('.incoming-grid'));assert.deepEqual(errors,[]);console.log(`Incoming private ${viewport.name}: separate navigation, both sides and owner labels, privacy, active switching, final responses and normal seller billing passed.`);
 }catch(error){await screenshot(page,`interaction-incoming-private-${viewport.name}-failure.png`);throw error;}finally{await context.close();}
}
async function verifyAgentIncoming(browser,viewport){
 const context=await createContext(browser,viewport),page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await configure(page,'agent');assert.ok((await candidates(page)).length>0);assert.ok((await candidates(page)).every(item=>item.ownerAccountType==='private'),'Agent search discovery must exclude agents');assert.equal(await page.locator('#candidate .private-badge').innerText(),'Magánszemély');assert.equal(await page.locator('.search-summary .account-badge').count(),0);
  for(const destination of ['properties','searches']){await go(page,destination);assert.equal(await page.locator('.entity-grid .account-badge').count(),0,'Own cards must not repeat the profile type');assert.equal(await page.locator('.entity-grid [data-action="report-account"]').count(),0);}
  await go(page);await enterIncoming(page,interact);assert.equal(await page.locator('.incoming-card').count(),1);assert.equal(await page.locator('.incoming-card[data-id="p1"]').count(),1);assert.equal(await page.locator('.incoming-card[data-id="p2"]').count(),0,'Agent sources must not leak into incoming likes for an agent');
  await interact(page.locator('.incoming-card[data-id="p1"] [data-action="incoming-like"]'));await page.getByRole('heading',{name:'Egymásra találtatok!',exact:true}).waitFor();assert.equal((await current(page)).credits,23);assert.equal((await current(page)).ledger.filter(item=>item.amount===-1).length,1);await closeModal(page,interact);
  await switchIncoming(page,interact,'property','own-p1');assert.equal(await page.locator('.incoming-card').count(),1);assert.equal(await page.locator('.incoming-card[data-id="s1"]').count(),1);assert.equal(await page.locator('.incoming-card[data-id="s2"]').count(),0);
  await go(page);assert.ok((await candidates(page)).length>0);assert.ok((await candidates(page)).every(item=>item.ownerAccountType==='private'),'Agent seller discovery must exclude agents');assert.equal(await page.locator('#candidate .private-badge').innerText(),'Magánszemély');await fit(page.locator('#candidate'));assert.deepEqual(errors,[]);console.log(`Incoming agent ${viewport.name}: agent-to-agent exclusion on both sides, hidden own labels, filtered incoming lists and one-credit reciprocity passed.`);
 }catch(error){await screenshot(page,`interaction-incoming-agent-${viewport.name}-failure.png`);throw error;}finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports){await verifyReports(browser,viewport);await verifyPrivateIncoming(browser,viewport);await verifyAgentIncoming(browser,viewport);}}finally{await browser.close();}
