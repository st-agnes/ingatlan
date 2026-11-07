/** Real-browser regression for account types, agent costs and disguised-agent reports. */
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
const first=page=>page.evaluate(async()=> (await import('/model.js')).model.feed()[0]);
const raw=page=>page.evaluate(async()=>JSON.parse(localStorage.getItem((await import('/model.js')).STORAGE_KEY)));
async function go(page,name='discover'){await page.goto(`${origin}/?broker-visit=${++visit}#${name}`,{waitUntil:'domcontentloaded'});await page.locator('.page-heading').waitFor();}
async function contextFor(browser,viewport){const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());return context;}
async function saveScreenshot(page,name){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,name),fullPage:true}).catch(()=>{});}
async function expectBadge(locator){assert.match(await locator.innerText(),/Ingatlanközvetítő/);}
async function verifyWorkspace(browser,viewport){
 const context=await contextFor(browser,viewport),page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));page.setDefaultTimeout(10000);page.setDefaultNavigationTimeout(15000);const interact=locator=>viewport.touch?locator.tap():locator.click();
 const reportFor=id=>page.locator(`[data-action="report-account"][data-id="${id}"]`).first();
 async function reportReason(id,reason){await interact(reportFor(id));await page.getByRole('heading',{name:'Szabálytalan hirdetés?',exact:true}).waitFor();await page.locator('#f-reportReason').selectOption(reason);await interact(page.locator('.modal [data-action="confirm-report"]'));await page.locator('.modal').waitFor({state:'detached'});}
 try{
  await go(page);
  await page.evaluate(async()=>{const {createModel,STORAGE_KEY}=await import('/model.js');let serialized;const demo=createModel({getItem:()=>null,setItem:(_key,value)=>{serialized=value;}});demo.activate('search','own-s1');const fixture=JSON.parse(serialized);fixture.users.find(user=>user.id==='me').accountType='agent';fixture.users.find(user=>user.id==='u1').accountType='private';fixture.users.find(user=>user.id==='u2').accountType='agent';fixture.credits=1;fixture.reports=[];localStorage.setItem(STORAGE_KEY,JSON.stringify(fixture));});
  await go(page);
  assert.equal((await current(page)).user.accountType,'agent');assert.equal((await current(page)).credits,1);
  let candidate=await first(page);assert.equal(candidate.id,'p1');assert.equal(candidate.ownerAccountType,'private');
  assert.match(await page.locator('.decision-labels').innerText(),/Tetszik · 1 kredit/);
  assert.equal(await page.locator('#candidate .agent-badge').count(),0,'A private owner must not inherit the current agent actor badge');
  assert.match(await page.locator('#candidate .private-badge').innerText(),/Magánszemély/);
  assert.equal(await page.evaluate(async()=> (await import('/model.js')).model.feed().every(item=>item.ownerAccountType==='private')),true,'Agent searches must exclude all agent counterparties');
  const report=reportFor(candidate.id);assert.equal(await report.isEnabled(),true);assert.equal((await report.innerText()).trim(),'Szabálytalan hirdetés?');
  await interact(report);await page.getByRole('heading',{name:'Szabálytalan hirdetés?',exact:true}).waitFor();
  assert.deepEqual(await page.locator('#f-reportReason option').evaluateAll(options=>options.map(option=>option.value).filter(Boolean)),['suspected_agent','misleading_content','other_violation']);
  await interact(page.locator('.modal [data-action="close"]').last());assert.equal((await raw(page)).reports.length,0,'Cancelling a report must not store it');
  await reportReason(candidate.id,'suspected_agent');assert.match(await page.locator('#toast').innerText(),/jelent/i);
  const reportRow=(await raw(page)).reports[0];assert.ok(reportRow);assert.ok(!Number.isNaN(Date.parse(reportRow.createdAt)),'The stored report must have a timestamp');assert.equal(reportRow.reason,'suspected_agent');assert.equal((await current(page)).credits,1,'Reporting must not charge credits');
  assert.equal((await page.locator('#app').innerText()).includes(reportRow.createdAt),false,'The report timestamp must not be rendered');
  assert.equal(await reportFor(candidate.id).isEnabled(),true,'The report remains available for a different reason');
  await go(page);assert.ok((await current(page)).reportedEntities.some(row=>row.entityKind==='property'&&row.entityId===candidate.id&&row.reason==='suspected_agent'),'Reported context must survive reload');
  await reportReason(candidate.id,'suspected_agent');assert.equal((await raw(page)).reports.length,1,'The same source/reason must not produce a duplicate');assert.equal((await raw(page)).reports[0].createdAt,reportRow.createdAt);
  await reportReason(candidate.id,'misleading_content');assert.equal((await raw(page)).reports.length,2,'A second reason is a distinct report');
  await interact(page.locator('.card-actions [data-action="like"]'));await page.getByRole('heading',{name:'Egymásra találtatok!',exact:true}).waitFor();assert.equal((await current(page)).credits,0);assert.equal((await current(page)).ledger.filter(row=>row.amount===-1).length,1,'The agent search like must charge exactly one credit');await interact(page.locator('.modal [data-action="close"]').last());
  candidate=await first(page);const beforeDecisions=(await current(page)).decisions.length,beforeCandidate=candidate.id;
  await interact(page.locator('.card-actions [data-action="like"]'));await page.getByRole('heading',{name:'Kreditekre van szükséged.',exact:true}).waitFor();assert.equal((await current(page)).decisions.length,beforeDecisions);assert.equal((await first(page)).id,beforeCandidate);await interact(page.locator('.modal [data-action="close"]').last());
  await page.keyboard.press('ArrowRight');await page.getByRole('heading',{name:'Kreditekre van szükséged.',exact:true}).waitFor();assert.equal((await current(page)).decisions.length,beforeDecisions);await interact(page.locator('.modal [data-action="close"]').last());
  await page.locator('#candidate').dispatchEvent('pointerdown',{pointerId:71,clientX:100,clientY:300,bubbles:true});await page.locator('#candidate').dispatchEvent('pointermove',{pointerId:71,clientX:250,clientY:300,bubbles:true});await page.locator('#candidate').dispatchEvent('pointerup',{pointerId:71,clientX:250,clientY:300,bubbles:true});await page.getByRole('heading',{name:'Kreditekre van szükséged.',exact:true}).waitFor();assert.equal((await current(page)).decisions.length,beforeDecisions);assert.equal((await first(page)).id,beforeCandidate);await interact(page.locator('.modal [data-action="close"]').last());
  await interact(page.locator('.card-actions [data-action="details"]'));assert.match(await page.locator('.modal .private-badge').first().innerText(),/Magánszemély/);await interact(page.locator('.modal [data-action="close"]').last());
  await go(page,'properties');assert.equal(await page.locator('.entity-grid .account-badge').count(),0,'Own listings do not need account type badges');assert.equal(await page.locator('.entity-grid [data-action="report-account"]').count(),0,'Own listings cannot be reported');
  await go(page,'searches');assert.equal(await page.locator('.entity-grid .account-badge').count(),0,'Own searches do not need account type badges');
  await go(page,'matches');await expectBadge(page.locator('.match-card .agent-badge').first());
  await go(page,'discover');await interact(page.locator('[data-action="tab"][data-tab="liked"]'));assert.match(await page.locator('.liked-grid .private-badge').first().innerText(),/Magánszemély/);
  await go(page,'settings');assert.match(await page.locator('#app').innerText(),/Ingatlanközvetítő/);
  await page.evaluate(async()=>{const {model}=await import('/model.js');model.activate('property','own-p1');});await go(page);assert.match(await page.locator('.decision-labels').innerText(),/Ajánlom · 2 kredit/);
  candidate=await first(page);assert.equal(candidate.kind,'search');assert.equal(candidate.ownerAccountType,'private');assert.match(await page.locator('#candidate .private-badge').innerText(),/Magánszemély/);
  assert.equal(await page.evaluate(async()=> (await import('/model.js')).model.feed().every(item=>item.ownerAccountType==='private')),true,'Agent sellers must exclude all agent searches');
  // A separate private-actor scenario still discovers and reports declared agents.
  await page.evaluate(async()=>{const {STORAGE_KEY}=await import('/model.js');const fixture=JSON.parse(localStorage.getItem(STORAGE_KEY));fixture.users.find(user=>user.id==='me').accountType='private';fixture.active={kind:'search',id:'own-s1'};localStorage.setItem(STORAGE_KEY,JSON.stringify(fixture));});await go(page);
  for(let count=0;count<12&&(await first(page))?.ownerAccountType!=='agent';count++)await interact(page.locator('.card-actions [data-action="pass"]'));
  candidate=await first(page);assert.equal(candidate.ownerAccountType,'agent');await expectBadge(page.locator('#candidate .agent-badge'));assert.equal(await reportFor(candidate.id).isEnabled(),true,'Declared agents can also have irregular content reported');
  await interact(reportFor(candidate.id));await page.getByRole('heading',{name:'Szabálytalan hirdetés?',exact:true}).waitFor();
  assert.deepEqual(await page.locator('#f-reportReason option').evaluateAll(options=>options.map(option=>option.value).filter(Boolean)),['misleading_content','other_violation'],'A declared agent cannot be reported as pretending to be private');
  await page.locator('#f-reportReason').selectOption('misleading_content');await interact(page.locator('.modal [data-action="confirm-report"]'));await page.locator('.modal').waitFor({state:'detached'});assert.ok((await current(page)).reportedEntities.some(row=>row.entityId===candidate.id&&row.reason==='misleading_content'));
  await interact(page.locator('.card-actions [data-action="details"]'));await expectBadge(page.locator('.modal .agent-badge').first());await interact(page.locator('.modal [data-action="close"]').last());
  await page.evaluate(async()=>{const {model}=await import('/model.js');model.activate('property','own-p1');});await go(page);
  for(let count=0;count<12&&(await first(page))?.ownerAccountType!=='agent';count++)await interact(page.locator('.card-actions [data-action="pass"]'));
  candidate=await first(page);assert.equal(candidate.kind,'search');assert.equal(candidate.ownerAccountType,'agent');await expectBadge(page.locator('#candidate .agent-badge'));assert.equal(await reportFor(candidate.id).isEnabled(),true);
  const geometry=await page.locator('#candidate').evaluate(element=>({width:element.clientWidth,scrollWidth:element.scrollWidth}));assert.ok(geometry.scrollWidth<=geometry.width+1,'Account badges must fit the card on every viewport');assert.deepEqual(errors,[]);
  console.log(`Broker workspace ${viewport.name}: account labels, contextual report reasons/privacy, agent exclusion, paid search and insufficient-credit buttons/keys/swipe passed.`);
 }catch(error){await saveScreenshot(page,`broker-workspace-${viewport.name}-failure.png`);throw error;}finally{await context.close();}
}
async function verifyRegistration(browser,viewport){
 const context=await contextFor(browser,viewport),page=await context.newPage(),requests=[];page.setDefaultTimeout(10000);const interact=locator=>viewport.touch?locator.tap():locator.click();
 await context.route('**/api/auth/register',async route=>{requests.push(route.request().postDataJSON());await route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({message:'Regisztrációs próba'})});});
 try{
  // The ordinary demo API-connect form offers the same account categories.
  await go(page,'settings');await page.locator('#register-toggle').check();await page.locator('#api-accountType').selectOption('agent');await page.locator('#f-registerName').fill('Közvetítő próba');await page.locator('#api-email').fill('broker-browser@example.test');await page.locator('#f-password').fill('BrokerBrowser2026!');await interact(page.locator('#api-form button[type="submit"]'));await page.waitForFunction(()=>document.getElementById('toast').textContent.includes('Regisztrációs próba'));assert.equal(requests.at(-1).accountType,'agent');
  // Force hosted mode only for the registration form; requests are intercepted above.
  await context.route('**/runtime-config.js',route=>route.fulfill({status:200,contentType:'text/javascript',body:"globalThis.OTTHONRA_CONFIG=Object.freeze({mode:'api',environment:'test'});"}));
  await page.goto(`${origin}/?broker-register=${++visit}`,{waitUntil:'domcontentloaded'});await page.locator('#hosted-auth-form').waitFor();assert.equal(await page.locator('#f-accountType').count(),0,'Login must not ask for a registration account type');await interact(page.locator('[data-action="auth-mode"][data-mode="register"]'));
  const options=await page.locator('#f-accountType option').evaluateAll(items=>items.map(item=>({value:item.value,label:item.textContent.trim()})));assert.deepEqual(options,[{value:'private',label:'Magánszemély'},{value:'agent',label:'Ingatlanközvetítő'}]);
  await page.locator('#f-name').fill('Közvetítő próba');await page.locator('#f-email').fill('hosted-broker-browser@example.test');await page.locator('#f-password').fill('BrokerBrowser2026!');
  for(const accountType of ['agent','private']){const before=requests.length;await page.locator('#f-accountType').selectOption(accountType);await Promise.all([page.waitForResponse(response=>new URL(response.url()).pathname==='/api/auth/register'&&response.request().postDataJSON()?.accountType===accountType),interact(page.locator('#hosted-auth-form button[type="submit"]'))]);await page.waitForFunction(()=>document.getElementById('auth-error').textContent.includes('Regisztrációs próba'));assert.equal(requests.length,before+1);assert.equal(requests.at(-1).accountType,accountType);}
  console.log(`Broker registration ${viewport.name}: private/agent choices and payloads in both registration paths passed.`);
 }catch(error){await saveScreenshot(page,`broker-registration-${viewport.name}-failure.png`);throw error;}finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports){await verifyWorkspace(browser,viewport);await verifyRegistration(browser,viewport);}}finally{await browser.close();}
