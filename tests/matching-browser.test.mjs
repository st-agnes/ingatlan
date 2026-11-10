/** Real-browser discovery staging, consent and specialization in the shared demo model. */
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
async function configure(page,kind){
 await page.goto(origin+'/#discover',{waitUntil:'domcontentloaded'});await page.locator('.page-heading').waitFor();
 await page.evaluate(async kind=>{
  const {createModel,STORAGE_KEY}=await import('/model.js');let raw;
  const model=createModel({getItem:()=>null,setItem:(_key,value)=>{raw=JSON.parse(value);}},()=> '2026-11-10T10:00:00.000Z');model.activate('search','own-s1');
  raw.decisions=[];raw.matches=[];raw.reports=[];raw.credits=100;
  const baseProperty=raw.properties.find(item=>item.id==='p1');
  const property=(id,title,price,extra={})=>({...baseProperty,id,title,ownerId:id==='near-property'?'u2':'u1',locationId:'district:Budapest:13',city:'Budapest',district:'XIII.',price,area:60,rooms:3,wholeRooms:3,halfRooms:0,...extra});
  raw.properties=raw.properties.filter(item=>item.ownerId==='me');raw.properties.push(property('exact-property','Tökéletes tesztotthon',70),property('near-property','Részleges tesztotthon',88),property('wrong-place','Másik város',5,{locationId:'city:Debrecen',city:'Debrecen',district:''}));
  const criteria={locationIds:['district:Budapest:13'],city:'Budapest',districts:['XIII.'],type:'Lakás',minPrice:null,maxPrice:80,minArea:50,maxArea:85,minRooms:2,maxRooms:4,conditions:[],buildings:[],constructionAges:[],views:[],floors:[],heatingTypes:[],ceilingHeight:'',balcony:false,elevator:false};
  for(const id of ['own-s1','own-s2'])Object.assign(raw.searches.find(item=>item.id===id),criteria,{title:id==='own-s1'?'Aktív tesztkeresés':'Másik tesztkeresés'});
  Object.assign(raw.properties.find(item=>item.id==='own-p1'),property('own-p1','Saját tesztotthon',80),{ownerId:'me'});
  raw.searches=raw.searches.filter(item=>item.ownerId==='me');
  const request=(id,title,extra)=>({...criteria,id,title,ownerId:id==='near-search'?'u3':'u1',description:'Kitalált böngészős tesztkeresés.',...extra});
  raw.searches.push(request('narrow-search','Szűk tesztkeresés',{minPrice:75,maxPrice:85,minArea:58,maxArea:65,minRooms:3,maxRooms:3}),request('broad-search','Tág tesztkeresés',{maxPrice:100,minArea:20,maxArea:200,minRooms:1,maxRooms:10}),request('near-search','Részleges tesztkeresés',{maxPrice:70}));
  raw.active={kind,id:kind==='property'?'own-p1':'own-s1'};localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));
 },kind);
 await page.reload({waitUntil:'domcontentloaded'});await page.locator('#candidate').waitFor();
}
async function verify(browser,viewport,kind){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 const page=await context.newPage();page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',error=>errors.push(error.message));const interact=locator=>viewport.touch?locator.tap():locator.click();
 try{
  await configure(page,kind);
  assert.match(await page.locator('#candidate .score').innerText(),/100%/);assert.doesNotMatch(await page.locator('#app').innerText(),/Másik város/);
  const exactExplanation=await page.locator('#candidate .feature-tags').innerText();assert.doesNotMatch(exactExplanation,/Helyszín|Ingatlantípus|Keresés:|Ingatlan:|M Ft|m²/);assert.equal(await page.locator('#candidate .feature-tags [data-criterion="location"],#candidate .feature-tags [data-criterion="type"]').count(),0);
  if(kind==='property'){
   assert.match(await page.locator('#candidate').innerText(),/Szűk tesztkeresés/);assert.match(await page.locator('#candidate .specialization').innerText(),/Specializáltság: [\d,]+%/);assert.doesNotMatch(await page.locator('#candidate .specialization').innerText(),/\/100/);
   await interact(page.locator('.card-actions [data-action="pass"]'));await page.getByRole('heading',{name:'Tág tesztkeresés',exact:true}).waitFor();assert.match(await page.locator('#candidate .score').innerText(),/100%/);
  }
  await interact(page.locator('.card-actions [data-action="pass"]'));await page.getByRole('heading',{name:'Elfogytak a tökéletes egyezések.',exact:true}).waitFor();
  assert.equal(await page.locator('#candidate').count(),0,'No partial card may appear before consent');
  const before=await readState(page);assert.equal(await page.locator('[data-action="approximate-decline"]').count(),0);assert.equal(await page.locator('.approximate-offer button').count(),1);await page.waitForTimeout(120);assert.equal(await page.locator('#candidate').count(),0);assert.deepEqual(await readState(page),before,'Leaving partial matches closed does not consume or bill a candidate');
  const geometry=await page.locator('.approximate-offer').evaluate(element=>({width:element.clientWidth,scrollWidth:element.scrollWidth}));assert.ok(geometry.scrollWidth<=geometry.width+1,'Consent controls must fit on screen');
  await interact(page.locator('[data-action="approximate-accept"]'));await page.locator('#candidate').waitFor();const score=Number((await page.locator('#candidate .score').innerText()).match(/\d+/)?.[0]);assert.ok(score<100);assert.match(await page.locator('.matching-stage').innerText(),/Részleges egyezések/);
  assert.ok(await page.locator('#candidate .criterion-different').count()>0);assert.ok(await page.locator('#candidate .criterion-passed').count()>0);
  const explanation=await page.locator('#candidate .feature-tags').innerText(),priceExplanation=await page.locator('#candidate [data-criterion="price"]').innerText();
  assert.equal(await page.locator('#candidate .feature-tags [data-criterion="location"],#candidate .feature-tags [data-criterion="type"]').count(),0);
  assert.doesNotMatch(explanation,/Keresés:|Ingatlan:|Helyszín|Ingatlantípus/);
  assert.match(priceExplanation,kind==='search'?/88.*M Ft/:/70.*M Ft/);
  assert.doesNotMatch(priceExplanation,/80.*M Ft/,'An unmet criterion must not repeat the active entity value');
  const fulfilled=await page.locator('#candidate .match-passed').innerText();
  assert.match(fulfilled,/Megfelelő alapterület/);assert.doesNotMatch(fulfilled,/50|85|60|m²|\d+\s*szoba/,'Fulfilled conditions use concise labels without numeric comparison details');
  assert.equal(await page.locator('[data-action="approximate-decline"]').count(),0);assert.ok(await page.locator('#candidate .owner-first-name').count()>0);
  await page.reload({waitUntil:'domcontentloaded'});await page.getByRole('heading',{name:'Elfogytak a tökéletes egyezések.',exact:true}).waitFor();assert.equal(await page.locator('#candidate').count(),0,'Consent does not survive a new browser session view');
  await interact(page.locator('[data-action="approximate-accept"]'));await page.locator('#candidate').waitFor();
  if(kind==='search'){
   await interact(page.locator('[data-action="edit-active"]').first());await page.locator('#entity-form').waitFor();await page.locator('#f-maxPrice').fill('81');await interact(page.locator('#entity-form button[type="submit"]'));
   await page.getByRole('heading',{name:'Elfogytak a tökéletes egyezések.',exact:true}).waitFor();assert.equal(await page.locator('#candidate').count(),0,'Editing criteria resets consent');
   await page.evaluate(async()=>{const {STORAGE_KEY}=await import('/model.js');const raw=JSON.parse(localStorage.getItem(STORAGE_KEY));Object.assign(raw.searches.find(item=>item.id===raw.active.id),{maxPrice:1,minArea:1000000,maxArea:null,minRooms:1000,maxRooms:null});localStorage.setItem(STORAGE_KEY,JSON.stringify(raw));});
   await page.reload({waitUntil:'domcontentloaded'});await page.getByRole('heading',{name:'Elfogytak a tökéletes egyezések.',exact:true}).waitFor();await interact(page.locator('[data-action="approximate-accept"]'));await page.locator('#candidate').waitFor();assert.match(await page.locator('#candidate .score').innerText(),/^0%/,'A real zero-percent partial score must never become the former 97-percent fallback');
  }else{
   await interact(page.locator('[data-action="activate"]').first());await interact(page.locator('.modal [data-action="activate-one"][data-kind="search"][data-id="own-s1"]'));await page.locator('#candidate').waitFor();assert.match(await page.locator('#candidate .score').innerText(),/100%/);
   await interact(page.locator('.card-actions [data-action="pass"]'));await page.getByRole('heading',{name:'Elfogytak a tökéletes egyezések.',exact:true}).waitFor();assert.equal(await page.locator('#candidate').count(),0,'Switching roles resets consent');
  }
  assert.deepEqual(errors,[]);console.log(`Matching ${kind} ${viewport.name}: exact-first discovery, single explicit opt-in, concise fulfilled criteria and counterpart-only mismatch values, first names, partial percentages, scoped consent and specialization passed.`);
 }catch(error){await mkdir(screenshots,{recursive:true});await page.screenshot({path:resolve(screenshots,`matching-${kind}-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports)for(const kind of ['search','property'])await verify(browser,viewport,kind);}finally{await browser.close();}
