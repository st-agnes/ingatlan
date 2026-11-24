/** Anonymous, shareable listing pages and their genuine draft-entry actions. */
import {mockMapTiles} from './map-browser-network.mjs';
import {editorField} from './editor-browser-helpers.mjs';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {getLocation} from '../dist/locations.js';

const playwrightPath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=playwrightPath?(playwrightPath.startsWith('file:')?playwrightPath:pathToFileURL(resolve(playwrightPath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
const city=getLocation('city:Debrecen');
const key=(kind,letter)=>`${kind}-${letter.repeat(64)}`;
const propertyKey=key('property','a'),searchKey=key('search','b'),streetOnlyKey=key('property','c'),visibleKey=key('property','d'),missingKey=key('property','f');
const images=['https://images.example.test/first.jpg','https://images.example.test/second.jpg'];
const searchCriteria={locations:[city],type:'Lakás',minPrice:50000000,maxPrice:80000000,minArea:45,maxArea:90,minRooms:2,maxRooms:4,
 conditions:['Jó','Új/felújított'],buildings:['Tégla'],constructionAges:['10–30 év közötti'],views:['Kertre néző'],ceilingHeight:'3 m feletti',floors:[0.5,2],heatingTypes:['Hőszivattyú'],
 atticPreference:'only',minEnergyRating:'C',excludeTopFloor:true,excludeGroundFloorAndBelow:true,airConditioning:true,privateGarden:true,balcony:true,elevator:true};
function propertyDetail(sourceKey=propertyKey){
 const hideStreet=sourceKey===propertyKey,hideHouseNumber=sourceKey!==visibleKey;
 const listing={title:'Világos <b>otthon</b> és csend',type:'Lakás',city:'Debrecen',location:'Debrecen, Vénkert',neighborhood:'Vénkert',price:50000000,area:60,rooms:2.5,wholeRooms:2,halfRooms:1,
  condition:'Jó',building:'Tégla',constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m feletti',floor:2,buildingFloors:4,floorIsUpperRange:false,isAttic:false,
  heatingType:'Hőszivattyú',insulated:true,energyRating:'A+',energyRatingScheme:'2023',airConditioning:true,solarPanels:false,parkingTypes:['Garázs'],balcony:null,elevator:true,privateGarden:true,
  hideStreet,hideHouseNumber,street:'Titkos közterület',houseNumber:'12/A',address:'Titkos közterület 12/A',description:'Világos nappali és csendes, zöld kert vár az új lakóra.',images:[...images,'javascript:alert(1)'],
  ownerId:'PRIVATE OWNER ID',ownerEmail:'private-owner@example.test',phone:'+36 20 123 4567',latitude:47.53312345,longitude:21.62112345,addressDetails:{street:'PRIVATE STRUCTURED ADDRESS',houseNumber:'12/A',provider:'PRIVATE PROVIDER'}};
 return{kind:'property',key:sourceKey,sourceKey,title:listing.title,ownerFirstName:'Anna',ownerAccountType:'private',listing,
  prefill:{locations:[city],type:'Lakás',price:50000000,area:60,rooms:2.5,condition:'Jó',building:'Tégla',floor:2,heatingType:'Hőszivattyú',isAttic:false,energyRating:'A+',energyRatingScheme:'2023',balcony:null,elevator:true,
   street:'PRIVATE PREFILL ADDRESS',houseNumber:'PRIVATE HOUSE NUMBER',ownerId:'PRIVATE PREFILL OWNER'}};
}
function searchDetail(){
 const listing={...searchCriteria,locations:[city.label],description:'Nyugodt otthont keresek, ahol hosszú távra tervezhetek.',moveIn:'3 hónapon belül',financing:'Saját megtakarítás',
  ownerId:'PRIVATE SEARCH OWNER',email:'private-search@example.test',phone:'+36 20 765 4321'};
 return{kind:'search',key:searchKey,sourceKey:searchKey,title:'Zöld környéken keresünk otthont',ownerFirstName:'Péter',ownerAccountType:'agent',listing,prefill:searchCriteria,clonePrefill:{...searchCriteria,description:listing.description,moveIn:listing.moveIn,financing:listing.financing}};
}
function landing(){
 return{regions:[{id:'HU321',label:'Hajdú-Bihar'}],region:null,scope:'national',
  searches:Array.from({length:16},(_,index)=>({key:'search-'+index,sourceKey:index===0?searchKey:key('search',index%2?'e':'b'),title:index?'Másik otthont keresünk':'Zöld környéken keresünk otthont',ownerFirstName:'Péter',ownerAccountType:'agent',type:'Lakás',locations:[city.label],minPrice:50000000,maxPrice:80000000,minArea:45,maxArea:90,minRooms:2,maxRooms:4,prefill:searchCriteria})),
  properties:Array.from({length:8},(_,index)=>({key:'property-'+index,sourceKey:index===0?propertyKey:key('property',index%2?'c':'d'),title:index?'Másik eladó otthon':'Világos <b>otthon</b> és csend',ownerFirstName:'Anna',ownerAccountType:'private',type:'Lakás',location:city.label,price:50000000,area:60,rooms:2.5,image:images[0],prefill:propertyDetail().prefill}))};
}
const loadDraft=page=>page.evaluate(async()=>(await import('/onboarding.js')).loadDraft());
async function verify(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await mockMapTiles(context);
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 await context.route('https://get.geojs.io/**',route=>route.fulfill({contentType:'application/json',body:'{"country_code":"XX"}'}));
 await context.route('https://images.example.test/**',route=>route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aGRAAAAAASUVORK5CYII=','base64')}));
 await context.route(`${origin}/runtime-config.js`,route=>route.fulfill({contentType:'text/javascript',body:'globalThis.OTTHONRA_CONFIG=Object.freeze({mode:"api",environment:"test"});'}));
 const requests=[],unhandled=[],errors=[];
 await context.route(`${origin}/api/**`,route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname.slice(4);requests.push({path,method:request.method(),authorization:request.headers().authorization});
  const json=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
  if(path==='/public/landing')return json(landing());
  if(path.startsWith('/public/listings/')){const [,kind,sourceKey]=path.slice('/public/'.length).split('/');if(sourceKey===missingKey)return json({message:'Nem található.'},404);if(kind==='search'&&sourceKey===searchKey)return json(searchDetail());if(kind==='property'&&[propertyKey,streetOnlyKey,visibleKey].includes(sourceKey))return json(propertyDetail(sourceKey));return json({},404);}
  if(path==='/locations')return json({items:[city]});if(path==='/streets')return json({items:[]});
  unhandled.push(request.method()+' '+path);return json({message:'Unexpected public browser fixture route'},404);
 });
 const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',error=>errors.push(error.message));
 const interact=locator=>viewport.touch?locator.tap():locator.click();
 const detail=async(kind,sourceKey)=>{await page.goto(`${origin}/#listing/${kind}/${sourceKey}`,{waitUntil:'domcontentloaded'});await page.locator('#public-listing').waitFor();};
 try{
  await page.goto(`${origin}/#landing`,{waitUntil:'domcontentloaded'});await page.locator('.landing-search-card').first().waitFor();
  assert.equal(await page.locator('.landing-search-card').count(),16);assert.equal(await page.locator('.landing-property-card').count(),8);
  const card=page.locator('.landing-property-card').first(),link=card.locator('a.landing-card-open');
  assert.equal(await link.getAttribute('href'),`#listing/property/${propertyKey}`);assert.match(await card.locator('h3').innerText(),/Világos/);
  const owner=card.locator('.public-listing-author'),ownerBox=await owner.boundingBox(),titleBox=await card.locator('h3').boundingBox();assert.ok(ownerBox&&titleBox&&ownerBox.y<titleBox.y,'The advertiser is a compact upper-right detail above the actual title');
  const role=card.locator('[data-account-help]');assert.equal(await role.getAttribute('aria-label'),'Magánszemély');assert.equal((await role.innerText()).trim(),'','Account type is represented by an icon');
  const before=page.url();await interact(role);assert.equal(page.url(),before,'Opening the account explanation must not follow the card link');assert.equal(await role.getAttribute('aria-expanded'),'true');assert.equal(await card.locator('[data-account-help-panel]').isVisible(),true);
  await interact(role);await interact(link);await page.locator('#public-listing').waitFor();
  assert.equal(new URL(page.url()).hash,`#listing/property/${propertyKey}`);assert.match(await page.locator('#public-listing h1').innerText(),/Világos/);assert.equal(await page.locator('#public-listing h1 img,#public-listing h1 b').count(),0,'User titles are plain text');
  const text=await page.locator('#public-listing').innerText();assert.match(text,/Vénkert/);assert.match(text,/Hőszivattyú/);assert.match(text,/Energetikai tanúsítvány/);assert.match(text,/A\+/);assert.match(text,/Világos nappali/);assert.match(text.replace(/\s/g,''),/50000000Ft/);
  assert.doesNotMatch(text,/Titkos közterület|12\/A|PRIVATE|private-owner@|47\.53312345|21\.62112345/,'A hidden address and internal metadata must never appear on a public detail page');
  assert.deepEqual(await page.locator('.public-listing-gallery img').evaluateAll(nodes=>nodes.map(node=>node.src)),images,'The complete safe photo collection is visible without registration');assert.equal(await page.locator('img[src^="javascript:"]').count(),0);
  await interact(page.locator('#public-listing .public-listing-actions [data-action="onboarding-start"]').first());await page.locator('#entity-form').waitFor();
  let draft=await loadDraft(page);assert.equal(draft.kind,'search');assert.deepEqual(draft.origin,{kind:'property',key:propertyKey});assert.equal(draft.data.maxPrice,55);assert.equal(draft.data.minArea,50);assert.equal(draft.data.minRooms,2.5);assert.doesNotMatch(JSON.stringify(draft),/PRIVATE|ownerId|private-owner@|Titkos közterület/);
  await detail('property',streetOnlyKey);assert.equal((await page.locator('.public-listing-address').innerText()).trim(),'Titkos közterület');assert.doesNotMatch(await page.locator('#public-listing').innerText(),/12\/A/,'Hiding only the house number still permits the street name');
  await detail('property',visibleKey);assert.match(await page.locator('.public-listing-address').innerText(),/Titkos közterület 12\/A/);
  await detail('search',searchKey);assert.equal(await page.locator('#public-listing h1').innerText(),'Zöld környéken keresünk otthont');assert.match(await page.locator('#public-listing').innerText(),/Tetőtéri ingatlant keres/);assert.match(await page.locator('#public-listing').innerText(),/Legalább C/);assert.match(await page.locator('#public-listing').innerText(),/Nyugodt otthont/);assert.doesNotMatch(await page.locator('#public-listing').innerText(),/PRIVATE|private-search@|765 4321/);
  await interact(page.locator('#public-listing [data-action="onboarding-copy-search"]').first());await page.locator('#entity-form').waitFor();
  draft=await loadDraft(page);assert.equal(draft.kind,'search');assert.deepEqual(draft.origin,{kind:'search',key:searchKey,mode:'copy'});assert.deepEqual(draft.data.locationIds,[city.id]);
  for(const [name,value]of Object.entries({minPrice:50,maxPrice:80,minArea:45,maxArea:90,minRooms:2,maxRooms:4,atticPreference:'only',minEnergyRating:'C',moveIn:'3 hónapon belül',financing:'Saját megtakarítás',description:searchDetail().clonePrefill.description}))assert.deepEqual(draft.data[name],value,`Copying a search preserves ${name}`);
  for(const name of ['conditions','buildings','constructionAges','views','floors','heatingTypes'])assert.deepEqual(draft.data[name],searchCriteria[name]);
  assert.notEqual(draft.data.title,searchDetail().title,'The new profile receives its own editable generated title');
  const copyId=draft.id;await (await editorField(page,'#f-description',interact)).fill('Ezt a keresést a saját igényeimre módosítottam.');
  await page.waitForFunction(async()=>(await import('/onboarding.js')).loadDraft()?.data?.description==='Ezt a keresést a saját igényeimre módosítottam.');
  await detail('search',searchKey);await interact(page.locator('#public-listing [data-action="onboarding-copy-search"]').first());await page.locator('#entity-form').waitFor();draft=await loadDraft(page);assert.equal(draft.id,copyId,'A repeated copy action resumes the matching draft without asking');assert.equal(draft.data.description,'Ezt a keresést a saját igényeimre módosítottam.');
  await detail('search',searchKey);await interact(page.locator('#public-listing [data-action="onboarding-start"]').first());await page.locator('#entity-form').waitFor();draft=await loadDraft(page);assert.equal(draft.kind,'property');assert.notEqual(draft.id,copyId,'Selling to a search is a different draft origin from copying that search');assert.equal(draft.data.locationId,city.id);assert.equal(draft.data.price??null,null,'A range must not invent a seller price');assert.equal(draft.data.area??null,null);assert.equal(draft.data.condition??'','','Multiple acceptable conditions must not invent one seller condition');assert.equal(draft.data.building,'Tégla');assert.equal(draft.data.heatingType,'Hőszivattyú');assert.equal(draft.data.isAttic,true);
  await page.goto(`${origin}/#listing/property/${missingKey}`,{waitUntil:'domcontentloaded'});await page.locator('.public-listing-error').waitFor();assert.match(await page.locator('.public-listing-error').innerText(),/már nem elérhető/);assert.equal(await page.locator('#hosted-auth-form').count(),0,'An unavailable public listing does not force visitors to log in');
  assert.ok(requests.filter(request=>request.path.startsWith('/public/')).length>=6);assert.ok(requests.every(request=>request.method==='GET'&&!request.authorization),'Public viewing and draft entry need no credentials or writes');assert.deepEqual(unhandled,[]);assert.deepEqual(errors,[]);
  const fit=await page.locator('body').evaluate(element=>element.scrollWidth<=innerWidth+1);assert.equal(fit,true,'Public detail and error pages fit the viewport');
  console.log(`Public listings ${viewport.name}: whole-card navigation, named icon roles, complete anonymous details/photos, address visibility, clone/opposite drafts, resumption and unavailable listings passed.`);
 }catch(error){await mkdir('.local/browser-tests/screenshots',{recursive:true});await page.screenshot({path:resolve('.local/browser-tests/screenshots',`public-listings-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports)await verify(browser,viewport);}finally{await browser.close();}
