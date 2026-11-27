/** Anonymous, shareable listing pages and their genuine draft-entry actions. */
import {mockMapTiles} from './map-browser-network.mjs';
import {editorField,editorStep,editorSave,choosePropertyType} from './editor-browser-helpers.mjs';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {getLocation,locations} from '../dist/locations.js';

const playwrightPath=process.env.PLAYWRIGHT_MODULE;
const playwrightUrl=playwrightPath?(playwrightPath.startsWith('file:')?playwrightPath:pathToFileURL(resolve(playwrightPath)).href):new URL('../.local/browser-tests/node_modules/playwright/index.mjs',import.meta.url).href;
const {chromium}=await import(playwrightUrl);
const origin=new URL(process.argv[2]||'http://127.0.0.1:3000').origin;
const viewports=[{name:'desktop',width:1280,height:900,touch:false},{name:'tablet',width:800,height:1100,touch:true},{name:'mobile',width:390,height:844,touch:true}];
const city=getLocation('city:Debrecen');
const key=(kind,letter)=>`${kind}-${letter.repeat(64)}`;
const propertyKey=key('property','a'),searchKey=key('search','b'),streetOnlyKey=key('property','c'),visibleKey=key('property','d'),missingKey=key('property','f');
const interestSent='Elküldtük érdeklődésedet! Most a másik félen a sor, hogy felvegyétek a kapcsolatot.';
const images=['https://images.example.test/first.jpg','https://images.example.test/second.jpg'];
const searchCriteria={locations:[city],type:'Lakás',minPrice:50000000,maxPrice:70000000,minArea:45,maxArea:90,minRooms:2,maxRooms:4,
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
  privateMaxPrice:80000000,ownerId:'PRIVATE SEARCH OWNER',email:'private-search@example.test',phone:'+36 20 765 4321'};
 return{kind:'search',key:searchKey,sourceKey:searchKey,title:'Zöld környéken keresünk otthont',ownerFirstName:'Péter',ownerAccountType:'agent',listing,prefill:searchCriteria,clonePrefill:{...searchCriteria,description:listing.description,moveIn:listing.moveIn,financing:listing.financing}};
}
function landing(){
 return{regions:[{id:'HU321',label:'Hajdú-Bihar'}],region:null,scope:'national',
  searches:Array.from({length:16},(_,index)=>({key:'search-'+index,sourceKey:index===0?searchKey:key('search',index%2?'e':'b'),title:index?'Másik otthont keresünk':'Zöld környéken keresünk otthont',ownerFirstName:'Péter',ownerAccountType:'agent',type:'Lakás',locations:[city.label],minPrice:50000000,maxPrice:70000000,minArea:45,maxArea:90,minRooms:2,maxRooms:4,prefill:searchCriteria})),
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
  if(path.endsWith('/map')&&path.startsWith('/public/listings/')){const [,kind,sourceKey]=path.slice('/public/'.length).split('/');return sourceKey===missingKey?json({},404):json({kind,available:true,locationIds:[city.id],externalUrl:sourceKey===visibleKey?'https://www.google.com/maps/search/?api=1&query=Debrecen%20Titkos%20k%C3%B6zter%C3%BClet%2012%2FA':null});}
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
  await mkdir('.local/browser-tests/screenshots',{recursive:true});await page.locator('.landing-search-card').first().scrollIntoViewIfNeeded();await page.screenshot({path:resolve('.local/browser-tests/screenshots',`public-listings-landing-${viewport.name}.png`)});
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
  await page.screenshot({path:resolve('.local/browser-tests/screenshots',`public-listings-property-${viewport.name}.png`)});
  await interact(page.locator('#public-listing .public-listing-actions [data-action="onboarding-start"]').first());await page.locator('#entity-form').waitFor();
  let draft=await loadDraft(page);assert.equal(draft.kind,'search');assert.deepEqual(draft.origin,{kind:'property',key:propertyKey});assert.equal(Number(draft.data.maxPrice),55);assert.equal(Number(draft.data.minArea),50);assert.equal(Number(draft.data.minRooms),2.5);assert.doesNotMatch(JSON.stringify(draft),/PRIVATE|ownerId|private-owner@|Titkos közterület/);
  await detail('property',streetOnlyKey);assert.equal((await page.locator('.public-listing-address').innerText()).trim(),'Titkos közterület');assert.doesNotMatch(await page.locator('#public-listing').innerText(),/12\/A/,'Hiding only the house number still permits the street name');
  await detail('property',visibleKey);assert.match(await page.locator('.public-listing-address').innerText(),/Titkos közterület 12\/A/);
  await detail('search',searchKey);assert.equal(await page.locator('#public-listing h1').innerText(),'Zöld környéken keresünk otthont');assert.match(await page.locator('#public-listing').innerText(),/Magasföldszint, 2\. emelet vagy tetőtér/);assert.match(await page.locator('#public-listing').innerText(),/Legalább C/);assert.match(await page.locator('#public-listing').innerText(),/Nyugodt otthont/);assert.doesNotMatch(await page.locator('#public-listing').innerText(),/PRIVATE|private-search@|765 4321/);const publicText=(await page.locator('#public-listing').innerText()).replace(/\s/g,'');assert.match(publicText,/50[–−-]70MFt/);assert.doesNotMatch(publicText,/80000000|80M(?:Ft)?/,'Anonymous search details show only the public bargaining limit');
  await interact(page.locator('#public-listing [data-action="onboarding-copy-search"]').first());await page.locator('#entity-form').waitFor();
  draft=await loadDraft(page);assert.equal(draft.kind,'search');assert.deepEqual(draft.origin,{kind:'search',key:searchKey,mode:'copy'});assert.deepEqual(draft.data.locationIds,[city.id]);
  for(const [name,value]of Object.entries({minPrice:50,maxPrice:70,publicMaxPrice:70,minArea:45,maxArea:90,minRooms:2,maxRooms:4,atticPreference:'only',minEnergyRating:'C',moveIn:'3 hónapon belül',financing:'Saját megtakarítás',description:searchDetail().clonePrefill.description}))assert.deepEqual(typeof value==='number'?Number(draft.data[name]):draft.data[name],value,`Copying a search preserves ${name}`);
  for(const name of ['conditions','buildings','constructionAges','views','floors','heatingTypes'])assert.deepEqual(name==='floors'?draft.data[name].map(Number):draft.data[name],searchCriteria[name]);
  assert.doesNotMatch(JSON.stringify(draft),/privateMaxPrice|80000000/,'Copying a public search cannot inherit its undisclosed private budget');assert.notEqual(draft.data.title,searchDetail().title,'The new profile receives its own editable generated title');
  const copyId=draft.id;await (await editorField(page,'#f-description',interact)).fill('Ezt a keresést a saját igényeimre módosítottam.');
  await page.waitForFunction(async()=>(await import('/onboarding.js')).loadDraft()?.data?.description==='Ezt a keresést a saját igényeimre módosítottam.');
  await detail('search',searchKey);await interact(page.locator('#public-listing [data-action="onboarding-copy-search"]').first());await page.locator('#entity-form').waitFor();draft=await loadDraft(page);assert.equal(draft.id,copyId,'A repeated copy action resumes the matching draft without asking');assert.equal(draft.data.description,'Ezt a keresést a saját igényeimre módosítottam.');
  await detail('search',searchKey);await interact(page.locator('#public-listing [data-action="onboarding-start"]').first());await page.locator('#entity-form').waitFor();draft=await loadDraft(page);assert.equal(draft.kind,'property');assert.notEqual(draft.id,copyId,'Selling to a search is a different draft origin from copying that search');assert.equal(draft.data.locationId,city.id);assert.ok(draft.data.price==null||draft.data.price==='','A range must not invent a seller price');assert.ok(draft.data.area==null||draft.data.area==='','A range must not invent a seller area');assert.equal(draft.data.condition??'','','Multiple acceptable conditions must not invent one seller condition');assert.equal(draft.data.building,'Tégla');assert.equal(draft.data.heatingType,'Hőszivattyú');assert.ok(draft.data.isAttic==null,'A floor-or-attic search must not impose an attic on a seller draft');
  await page.goto(`${origin}/#listing/property/${missingKey}`,{waitUntil:'domcontentloaded'});await page.locator('.public-listing-error').waitFor();assert.match(await page.locator('.public-listing-error').innerText(),/már nem elérhető/);assert.equal(await page.locator('#hosted-auth-form').count(),0,'An unavailable public listing does not force visitors to log in');
  assert.ok(requests.filter(request=>request.path.startsWith('/public/')).length>=6);assert.ok(requests.every(request=>request.method==='GET'&&!request.authorization),'Public viewing and draft entry need no credentials or writes');assert.deepEqual(unhandled,[]);assert.deepEqual(errors,[]);
  const fit=await page.locator('body').evaluate(element=>element.scrollWidth<=innerWidth+1);assert.equal(fit,true,'Public detail and error pages fit the viewport');
  console.log(`Public listings ${viewport.name}: whole-card navigation, named icon roles, complete anonymous details/photos, address visibility, clone/opposite drafts, resumption and unavailable listings passed.`);
 }catch(error){await mkdir('.local/browser-tests/screenshots',{recursive:true});await page.screenshot({path:resolve('.local/browser-tests/screenshots',`public-listings-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
/** Signed-in pages exercise the same DOM/routes as public visitors, with an authenticated pair context. */
async function verifySignedIn(browser,viewport){
 const context=await browser.newContext({viewport:{width:viewport.width,height:viewport.height},hasTouch:viewport.touch,reducedMotion:'reduce'});
 await mockMapTiles(context);
 await context.addInitScript(origin=>localStorage.setItem('otthonra.api',JSON.stringify({baseUrl:origin,token:'public-listing-browser-session'})),origin);
 await context.route('https://fonts.googleapis.com/**',route=>route.abort());await context.route('https://fonts.gstatic.com/**',route=>route.abort());
 await context.route('https://images.example.test/**',route=>route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aGRAAAAAASUVORK5CYII=','base64')}));
 await context.route(`${origin}/runtime-config.js`,route=>route.fulfill({contentType:'text/javascript',body:'globalThis.OTTHONRA_CONFIG=Object.freeze({mode:"api",environment:"test"});'}));
 await context.route('**/vendor/maplibre/maplibre-gl.mjs*',async route=>{
  const url=new URL(route.request().url());if(url.searchParams.has('public-browser-original'))return route.continue();url.searchParams.set('public-browser-original','1');
  return route.fulfill({contentType:'text/javascript',body:`export * from ${JSON.stringify(url.href)};import {Map as OriginalMap} from ${JSON.stringify(url.href)};export class Map extends OriginalMap{constructor(options){super({...options,fadeDuration:0});options.container.__listingBrowserMap=this;}}`});
 });
 const ids={user:'11111111-1111-4111-8111-111111111111',property:'22222222-2222-4222-8222-222222222222',search:'33333333-3333-4333-8333-333333333333',otherProperty:'44444444-4444-4444-8444-444444444444',otherSearch:'55555555-5555-4555-8555-555555555555',alternateSearch:'66666666-6666-4666-8666-666666666666',alternateProperty:'88888888-8888-4888-8888-888888888888',createdSearch:'99999999-9999-4999-8999-999999999999'};
 const asProperty=(id,ownerId,publicListingKey,title)=>({...propertyDetail().listing,id,ownerId,ownerFirstName:ownerId===ids.user?'Teszt':'Anna',ownerAccountType:'private',locationId:city.id,location:city,publicListingKey,title,archived:false,description:'Kitalált, kapcsolatfelvétel előtti nyilvános adatok.'});
 const asSearch=(id,ownerId,publicListingKey,title)=>({...searchCriteria,id,ownerId,ownerFirstName:ownerId===ids.user?'Teszt':'Péter',ownerAccountType:'private',locationIds:[city.id],locations:[city],publicListingKey,title,archived:false,description:'Kitalált keresési igény.',publicMaxPrice:70000000,maxPrice:80000000});
 const ownProperty=asProperty(ids.property,ids.user,visibleKey,'Saját eladó ingatlanom'),ownSearch=asSearch(ids.search,ids.user,searchKey,'Saját aktív keresésem'),foreignProperty=asProperty(ids.otherProperty,'other-owner',propertyKey,'Megnézhető eladó otthon'),foreignSearch=asSearch(ids.otherSearch,'search-owner',searchKey,'Megnézhető keresési igény');
 const alternateSearch=asSearch(ids.alternateSearch,ids.user,searchKey,'Másik saját keresésem'),alternateProperty=asProperty(ids.alternateProperty,ids.user,visibleKey,'Másik saját ingatlanom');
 const wrongTypeSearch={...asSearch('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',ids.user,searchKey,'Saját házkeresésem'),type:'Ház'};
 const archivedSearch={...asSearch('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',ids.user,searchKey,'Archivált keresésem'),archived:true};
 const ownSearches=[ownSearch,alternateSearch,wrongTypeSearch,...Array.from({length:48},(_,index)=>asSearch(`cccccccc-cccc-4ccc-8ccc-${String(index+1).padStart(12,'0')}`,ids.user,searchKey,`További saját keresés ${index+1}`)),archivedSearch],ownProperties=[ownProperty,alternateProperty];
 const neighborhood=locations.find(item=>item.kind==='neighborhood'&&item.city==='Debrecen'&&(item.name==='Vénkert'||item.label.includes('Vénkert')))||city,otherTown=getLocation('city:Hajdúszoboszló');
 const server={active:{kind:'search',id:ids.search},credits:20,partial:false,hasUnseenExact:false,prior:new Map(),decisions:[],activations:[],creations:[],requests:[],errors:[],unhandled:[],google:[],matchId:null};
 const activeProfile=()=>[...ownSearches,...ownProperties].find(item=>item.id===server.active.id);
 const activeScore=()=>server.active.id===ids.alternateSearch?73:server.active.id===ids.alternateProperty?86:activeProfile()?.type!=='Lakás'?0:server.partial?73:100;
 const profileSummary=(kind,item)=>({kind,id:item.id,title:item.title,type:item.type,locations:item.locations||[item.location],locationIds:item.locationIds||[item.locationId],...(kind==='search'?{minPrice:item.minPrice,maxPrice:item.maxPrice,minArea:item.minArea,minRooms:item.minRooms}:{price:item.price})});
 const prior=kind=>server.prior.get(kind)||null;
 const feedItem=()=>({property:server.active.kind==='search'?foreignProperty:activeProfile(),searchRequest:server.active.kind==='search'?activeProfile():foreignSearch,
  propertyId:server.active.kind==='search'?ids.otherProperty:server.active.id,searchRequestId:server.active.kind==='search'?server.active.id:ids.otherSearch,
  compatibilityScore:activeScore(),isExact:activeScore()===100,likedYou:true,compatible:activeScore()>0,reasons:[],matchDetails:[],searchSpecificity:42,myDecision:prior(server.active.kind==='search'?'property':'search'),matchId:server.matchId});
 await context.route('https://www.google.com/maps/**',route=>{server.google.push(route.request().url());return route.fulfill({contentType:'text/html',body:'<!doctype html><title>Isolated public Google address link</title><p>Mock map destination</p>'});});
 await context.route(`${origin}/api/**`,async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname.slice(4),method=request.method();server.requests.push({path,method,authorization:request.headers().authorization});
  const json=async(body,status=200)=>{try{return await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});}catch(error){if(!/closed|handled|intercept|abort/i.test(String(error)))throw error;}};
  const map=path.match(/^\/public\/listings\/(property|search)\/([^/]+)\/map$/);
  if(map){const [,kind,sourceKey]=map;return json({kind,available:true,locationIds:sourceKey===visibleKey?[]:kind==='search'?[city.id,otherTown.id]:[neighborhood.id],externalUrl:sourceKey===visibleKey?'https://www.google.com/maps/search/?api=1&query=Debrecen%20Titkos%20k%C3%B6zter%C3%BClet%2012%2FA':null});}
  const listing=path.match(/^\/public\/listings\/(property|search)\/([^/]+)$/);if(listing)return json(listing[1]==='property'?propertyDetail(listing[2]):searchDetail());
  const profiles=path.match(/^\/listings\/(property|search)\/([^/]+)\/profiles$/);
  if(profiles){const kind=profiles[1]==='property'?'search':'property',owned=(kind==='search'?ownSearches:ownProperties).filter(item=>!item.archived),ordered=[...owned.filter(item=>item.id===server.active.id),...owned.filter(item=>item.id!==server.active.id)],offset=Number(url.searchParams.get('offset')||0),limit=Number(url.searchParams.get('limit')||50),items=ordered.slice(offset,offset+limit).map(item=>({profile:profileSummary(kind,item),score:item.type!=='Lakás'?0:item.id===ids.alternateSearch?73:item.id===ids.alternateProperty?86:100,isExact:item.type==='Lakás'&&![ids.alternateSearch,ids.alternateProperty].includes(item.id),compatible:item.type==='Lakás',isActive:server.active.kind===kind&&server.active.id===item.id}));return json({kind,items,total:ordered.length,offset,limit,hasMore:offset+limit<ordered.length});}
  const interaction=path.match(/^\/listings\/(property|search)\/([^/]+)\/context$/);
  if(interaction){const kind=interaction[1],buying=server.active.kind==='search',decision=prior(kind),score=activeScore();return json({available:true,
   active:profileSummary(server.active.kind,activeProfile()),
   item:feedItem(),compatible:score>0,isExact:score===100,compatibilityScore:score,myDecision:decision,matchId:server.matchId,likeCost:buying?0:2,credits:server.credits,
   canDecide:score>0&&!decision&&!server.matchId,requiresApproximateConsent:false,hasUnseenExact:false,unavailableReason:score===0?'incompatible':null});}
  if(path==='/me')return json({id:ids.user,name:'Teszt Felhasználó',email:'viewer@example.test',phone:'+36 30 555 0101',accountType:'private',credits:server.credits,unreadNotificationCount:0,newNotificationCount:0,notificationLastVisitAt:null});
  if(path==='/me/entities')return json({properties:ownProperties,searchRequests:ownSearches,active:server.active,decisions:[],reportedOwnerIds:[],reportedEntities:[]});
  if(path==='/me/active'&&method==='PUT'){const selected=request.postDataJSON();assert.ok((selected.kind==='search'?ownSearches:ownProperties).some(item=>item.id===selected.id&&!item.archived),'Only an owned live profile can be activated');server.activations.push(selected);server.active=selected;return json(selected);}
  if(path==='/credits/ledger')return json({items:[]});if(path==='/matches')return json({items:[]});if(path==='/feedback/pending')return json({feedbackPrompt:null});if(path==='/test/feedback-scenario')return json({available:false});
  if(path==='/feed')return json({active:server.active,items:prior(server.active.kind==='search'?'property':'search')?[]:[feedItem()],stage:'exact',hasApproximate:false});
  if(path==='/incoming-likes'){const pending=!prior(server.active.kind==='search'?'property':'search')&&!server.matchId;return json({active:server.active,items:pending?[feedItem()]:[],total:pending?1:0,offset:0,limit:50,hasMore:false,likeCost:server.active.kind==='property'?2:0});}
  if(path==='/impressions')return json({recorded:true});
  if(path==='/locations')return json({items:[city]});if(path==='/streets')return json({items:[]});
  if(path==='/searches'&&method==='POST'){const input=request.postDataJSON(),created={...asSearch(ids.createdSearch,ids.user,searchKey,input.title),...input,locations:[city]};ownSearches.push(created);server.creations.push({kind:'search',...input,id:created.id});return json(created,201);}
  if(path==='/decisions'&&method==='POST'){const body=request.postDataJSON();assert.equal(body.listingKey,server.active.kind==='search'?propertyKey:searchKey,'A public detail decision identifies the viewed listing as well as the exact pair');assert.equal(Object.hasOwn(body,'allowApproximate'),false,'Public decisions do not opt into the discovery feed');server.decisions.push(body);server.prior.set(server.active.kind==='search'?'property':'search',body.liked?'liked':'passed');const charged=body.liked&&server.active.kind==='property'?2:0;server.credits-=charged;return json({charged,matchId:null,feedbackPrompt:null});}
  server.unhandled.push(method+' '+path);return json({message:'Unexpected signed-in listing browser fixture route'},404);
 });
 const page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',error=>server.errors.push(error.message));
 const interact=locator=>viewport.touch?locator.tap():locator.click(),publicPage=async(kind,sourceKey)=>{await page.goto(`${origin}/#listing/${kind}/${sourceKey}`,{waitUntil:'domcontentloaded'});await page.locator('.public-listing-context').waitFor();};
 try{
  await page.goto(`${origin}/#discover`,{waitUntil:'domcontentloaded'});await page.locator('#candidate').waitFor();
  const discoveryTitle=page.locator('#candidate .listing-title-link');assert.equal(await discoveryTitle.getAttribute('href'),`#listing/property/${propertyKey}`);
  assert.match(await discoveryTitle.evaluate(element=>getComputedStyle(element).textDecorationLine),/underline/,'The title has a permanent link affordance before the first tap');
  assert.equal((await page.locator('.decision-labels').innerText()).replace(/\s+/g,' ').trim(),'Nem az igazi Vegyük fel a kapcsolatot!');
  assert.equal(await page.locator('.card-actions [data-action="like"] [data-icon="contact"] [data-part="phone"]').count(),1);assert.equal(await page.locator('.card-actions [data-action="like"] [data-icon="contact"] [data-part="message"]').count(),1);
  const locationStyle=await page.locator('#candidate .listing-location-name').evaluate(element=>({size:parseFloat(getComputedStyle(element).fontSize),underline:getComputedStyle(element).textDecorationLine}));assert.ok(locationStyle.size>=14);assert.match(locationStyle.underline,/underline/);assert.match(await page.locator('#candidate .listing-location-link').innerText(),/Térképen/);
  await interact(discoveryTitle);await page.locator('.public-listing-context').waitFor();
  assert.equal(new URL(page.url()).hash,`#listing/property/${propertyKey}`);assert.match(await page.locator('.public-listing-context').innerText(),/Saját aktív keresésem/);assert.match(await page.locator('.public-listing-match-score').innerText(),/100%/);
  const headingBox=await page.locator('#public-listing h1').boundingBox(),profileBox=await page.locator('.public-listing-context').boundingBox();assert.ok(headingBox&&profileBox&&profileBox.y>=headingBox.y+headingBox.height,'The active profile occupies the CTA area beneath the advertisement title');
  assert.equal(await page.locator('#public-listing-profile').count(),1);assert.equal(await page.locator('[data-action="public-listing-decision"]').count(),2);assert.equal(await page.locator('#public-listing [data-action="onboarding-start"]').count(),0,'Relevant signed-in profiles replace guest onboarding CTAs');
  const ownProfileCard=page.locator('.public-listing-active-profile'),response=page.locator('.public-listing-decision-dock');
  assert.equal(await ownProfileCard.locator('h2').innerText(),ownSearch.title);assert.equal(await ownProfileCard.locator('[data-action="public-listing-decision"]').count(),0);assert.equal(await page.locator('.public-listing-context [data-action="public-listing-decision"]').count(),0);assert.equal(await response.locator('.card-actions>button').count(),2);
  assert.equal(await page.locator('.public-listing-target-response,.public-listing-response-heading,[data-action="public-listing-profile-top"]').count(),0,'There is no repeated target title, explanatory response heading or footer profile return');
  assert.doesNotMatch(await page.locator('#public-listing').innerText(),/Erről (?:az ingatlanról|a keresési igényről) döntesz/);assert.equal(await page.locator('.public-listing-header [data-action="public-listing-back"]').count(),1);assert.equal(await page.locator('.public-listing-header nav a[href="#discover"]').count(),0,'The discovery origin has one contextual Back action');
  assert.equal(await response.evaluate(element=>getComputedStyle(element).position),'fixed');
  for(const fraction of [0,.5,1]){
   await page.evaluate(async fraction=>{scrollTo({top:(document.documentElement.scrollHeight-innerHeight)*fraction,behavior:'instant'});await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));},fraction);
   for(const button of await response.locator('.card-actions>button').all()){
    const box=await button.evaluate(element=>{const b=element.getBoundingClientRect(),hit=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);return{left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:innerWidth,height:innerHeight,hit:element===hit||element.contains(hit)};});
    assert.ok(box.left>=0&&box.right<=box.width+1&&box.top>=0&&box.bottom<=box.height+1,'The detail dock remains in the viewport at every scroll position');assert.equal(box.hit,true,'The detail buttons are reachable without scrolling to them');
   }
  }
  assert.match(await page.locator('.public-listing-contact').getAttribute('aria-label'),/^Vegyük fel a kapcsolatot!/);assert.match(await page.locator('.public-listing-pass').getAttribute('aria-label'),/Nem az igazi/);for(const part of ['phone','message'])assert.equal(await page.locator(`.public-listing-contact [data-icon="contact"] [data-part="${part}"]`).count(),1);
  const openProfiles=async()=>{await interact(page.locator('[data-action="public-listing-profiles"]'));await page.locator('.listing-profile-option').first().waitFor();};
  const switchProfile=async(kind,id)=>{await openProfiles();await interact(page.locator(`.listing-profile-option[data-kind="${kind}"][data-id="${id}"]`));await page.waitForFunction(expected=>document.querySelector('.public-listing-context h2')?.textContent===expected,kind==='property'?(id===ids.property?ownProperty.title:alternateProperty.title):id===ids.search?ownSearch.title:id===ids.alternateSearch?alternateSearch.title:ownSearches.find(item=>item.id===id).title);};
  await openProfiles();assert.equal(await page.locator('.listing-profile-option').count(),50);assert.equal(await page.locator('.listing-profile-option[data-kind="property"]').count(),0);assert.equal(await page.locator(`.listing-profile-option[data-id="${archivedSearch.id}"]`).count(),0);assert.equal(await page.locator(`.listing-profile-option[data-id="${ids.search}"]`).getAttribute('aria-pressed'),'true');
  assert.match(await page.locator(`.listing-profile-option[data-id="${ids.alternateSearch}"] .listing-profile-option-score`).innerText(),/73%/);assert.match(await page.locator(`.listing-profile-option[data-id="${wrongTypeSearch.id}"] .listing-profile-option-score`).innerText(),/0%/);
  await interact(page.locator('[data-action="public-listing-profiles-more"]'));await page.waitForFunction(()=>document.querySelectorAll('.listing-profile-option').length===51);assert.equal(await page.locator('[data-action="public-listing-profiles-more"]').count(),0);
  await interact(page.locator('.listing-profile-options-actions [data-action="close"]'));assert.equal(server.activations.length,0,'Cancelling or reading more profiles cannot activate a profile');assert.equal(server.decisions.length,0);
  await switchProfile('search',ids.alternateSearch);assert.equal(new URL(page.url()).hash,`#listing/property/${propertyKey}`);assert.match(await page.locator('.public-listing-match-score').innerText(),/73%/);assert.equal(await page.locator('[data-action="public-listing-approximate"]').count(),0);assert.equal(await page.locator('.public-listing-decisions [data-action="public-listing-decision"]:enabled').count(),2);assert.deepEqual(server.activations.at(-1),{kind:'search',id:ids.alternateSearch});
  await switchProfile('search',ids.search);assert.match(await page.locator('.public-listing-match-score').innerText(),/100%/);assert.equal(server.credits,20);assert.equal(server.decisions.length,0,'Changing context only reads compatibility; it cannot send interest or debit credits');
  await interact(page.locator('.public-listing-context [data-action="public-listing-new-profile"]'));await page.locator('#entity-form').waitFor();
  await page.locator('#location-input').fill('Debrecen');await interact(page.locator(`#location-options [data-location-id="${city.id}"]`));await choosePropertyType(page,'Lakás',interact);await (await editorField(page,'#f-maxPrice',interact)).fill('95');await (await editorField(page,'#f-minArea',interact)).fill('45');await editorSave(page,interact);
  await page.waitForFunction(previous=>{const title=document.querySelector('.public-listing-context h2')?.textContent;return title&&title!==previous&&!document.getElementById('entity-form');},ownSearch.title);
  assert.equal(server.creations.length,1);assert.equal(await page.locator('.public-listing-context h2').innerText(),server.creations[0].title);assert.equal(server.active.id,ids.createdSearch);assert.deepEqual(server.activations.at(-1),{kind:'search',id:ids.createdSearch});assert.equal(new URL(page.url()).hash,`#listing/property/${propertyKey}`);assert.equal(server.decisions.length,0);assert.equal(server.credits,20);await switchProfile('search',ids.search);
  await page.goBack();await page.locator('#candidate').waitFor();assert.equal(new URL(page.url()).hash,'#discover','The browser back button returns to discovery');
  await interact(page.locator('#candidate .listing-title-link'));await page.locator('.public-listing-context').waitFor();
  await interact(page.locator('[data-action="public-listing-decision"][data-liked="false"]'));await page.waitForURL('**/#discover');await page.getByRole('heading',{name:'Nincs több ajánlás egyelőre.',exact:true}).waitFor();
  assert.deepEqual(server.decisions[0],{propertyId:ids.otherProperty,searchRequestId:ids.search,liked:false,listingKey:propertyKey},'The detail action submits its actual pair and returns to discovery');
  await publicPage('property',propertyKey);assert.match(await page.locator('.public-listing-decision-state').innerText(),/már elutasítottad/);assert.equal(await page.locator('[data-action="public-listing-decision"]:disabled').count(),2);assert.equal(await page.locator('.public-listing-pass.is-selected[aria-pressed="true"]').count(),1);
  server.prior.delete('property');server.partial=true;server.hasUnseenExact=true;
  await page.reload({waitUntil:'domcontentloaded'});await page.locator('.public-listing-decisions').waitFor();
  assert.equal(await page.locator('[data-action="public-listing-approximate"]').count(),0);assert.equal(await page.locator('[data-action="public-listing-decision"]:enabled').count(),2,'A directly viewed partial listing remains actionable despite other unseen exact matches');
  assert.match(await page.locator('.public-listing-match-score').innerText(),/73%/);await interact(page.locator('[data-action="public-listing-decision"][data-liked="true"]'));await page.locator('.public-listing-decision-state').waitFor();assert.equal(await page.locator('.public-listing-decision-state').innerText(),interestSent);assert.equal(await page.locator('#toast').innerText(),interestSent);
  assert.deepEqual(server.decisions.at(-1),{propertyId:ids.otherProperty,searchRequestId:ids.search,liked:true,listingKey:propertyKey});assert.equal(await page.locator('[data-action="public-listing-decision"]:disabled').count(),2);assert.equal(await page.locator('.public-listing-contact.is-selected[aria-pressed="true"]').count(),1);const writesAfterLike=server.decisions.length;await page.reload({waitUntil:'domcontentloaded'});await page.locator('.public-listing-decision-state').waitFor();assert.equal(server.decisions.length,writesAfterLike,'Revisiting a decided listing never resubmits the paid action');assert.equal(await page.locator('.public-listing-contact.is-selected[aria-pressed="true"]').count(),1);
  const privateText=await page.locator('#public-listing').innerText();assert.doesNotMatch(privateText,/Titkos közterület|12\/A|PRIVATE|private-owner@|47\.53312345|21\.62112345/);
  await interact(page.locator('[data-action="public-listing-map"]'));await page.locator('#listing-location-map.location-map-readonly canvas').waitFor();
  assert.equal(new URL(page.url()).hash,`#map-view/property/${propertyKey}`);assert.match(await page.locator('.listing-location-layout aside').innerText(),new RegExp(neighborhood.name||'Vénkert'));
  assert.equal(await page.locator('.location-map-list').isHidden(),true,'A display map cannot add locations to a search');
  await page.waitForFunction(()=>{const map=document.querySelector('#listing-location-map .location-map-canvas')?.__listingBrowserMap;return map?.loaded()&&!map.isMoving()&&map.getStyle().sources['otthonra-outlines']?.data?.features?.length>0;});
  const mapData=await page.locator('#listing-location-map .location-map-canvas').evaluate(element=>{const map=element.__listingBrowserMap;return {data:map.getStyle().sources['otthonra-outlines'].data,label:map.getLayoutProperty('otthonra-place-labels','text-field')};});
  assert.ok(mapData.data.features.some(feature=>(feature.id||feature.properties.id)===neighborhood.id));assert.deepEqual(mapData.label,['get','name']);assert.doesNotMatch(JSON.stringify(mapData),/47\.53312345|21\.62112345|PRIVATE/);
  const readonlyBefore=JSON.stringify(mapData.data);await interact(page.locator('#listing-location-map canvas'));const readonlyAfter=await page.locator('#listing-location-map .location-map-canvas').evaluate(element=>JSON.stringify(element.__listingBrowserMap.getStyle().sources['otthonra-outlines'].data));assert.equal(readonlyAfter,readonlyBefore,'Map clicks cannot change the disclosed location');
  await interact(page.locator('[data-action="listing-map-back"]'));await page.locator('.public-listing-context').waitFor();assert.equal(new URL(page.url()).hash,`#listing/property/${propertyKey}`);
  server.partial=false;server.active={kind:'property',id:ids.property};server.prior.delete('search');
  await page.goto(`${origin}/#incoming`,{waitUntil:'domcontentloaded'});await page.locator('.incoming-card').waitFor();await interact(page.locator('.incoming-card h3'));await page.locator('.public-listing-context').waitFor();
  assert.equal(new URL(page.url()).hash,`#listing/search/${searchKey}`);assert.match(await page.locator('.public-listing-context').innerText(),/Saját eladó ingatlanom/);assert.match(await page.locator('.public-listing-decisions .decision-like-caption').innerText(),/Vegyük fel a kapcsolatot!\s+2 kredit/);
  await openProfiles();assert.equal(await page.locator('.listing-profile-option').count(),2);assert.equal(await page.locator('.listing-profile-option[data-kind="search"]').count(),0);assert.match(await page.locator(`.listing-profile-option[data-id="${ids.alternateProperty}"] .listing-profile-option-score`).innerText(),/86%/);await interact(page.locator(`.listing-profile-option[data-id="${ids.alternateProperty}"]`));await page.waitForFunction(()=>document.querySelector('.public-listing-match-score')?.textContent.includes('86%'));assert.match(await page.locator('.public-listing-context h2').innerText(),/Másik saját ingatlanom/);await switchProfile('property',ids.property);assert.equal(server.credits,20);
  const cost=await page.locator('.public-listing-decisions .decision-like-caption small').boundingBox(),caption=await page.locator('.public-listing-decisions .decision-like-caption>span').first().boundingBox();assert.ok(cost&&caption&&Math.abs(cost.x+cost.width/2-caption.x-caption.width/2)<2,'Seller credit cost remains centered under the action caption');
  await interact(page.locator('[data-action="public-listing-back"]'));await page.locator('.incoming-card').waitFor();assert.equal(new URL(page.url()).hash,'#incoming');
  await interact(page.locator('.incoming-card h3'));await page.locator('.public-listing-context').waitFor();await interact(page.locator('[data-action="public-listing-decision"][data-liked="true"]'));await page.locator('.public-listing-decision-state').waitFor();
  assert.deepEqual(server.decisions.at(-1),{propertyId:ids.property,searchRequestId:ids.otherSearch,liked:true,listingKey:searchKey});assert.equal(server.credits,18);
  server.matchId='77777777-7777-4777-8777-777777777777';await page.reload({waitUntil:'domcontentloaded'});await page.locator('.public-listing-decision-state').waitFor();assert.match(await page.locator('.public-listing-decision-state').innerText(),/Már kapcsolatban vagytok/);assert.equal(await page.locator('[data-action="public-listing-decision"]:disabled').count(),2);assert.equal(await page.locator('.public-listing-contact.is-selected[aria-pressed="true"]').count(),1);server.matchId=null;
  await interact(page.locator('[data-action="public-listing-map"]'));await page.locator('.listing-location-layout aside').waitFor();const searchLocationsText=await page.locator('.listing-location-layout aside').innerText();assert.match(searchLocationsText,/Debrecen/);assert.match(searchLocationsText,/Hajdúszoboszló/);await interact(page.locator('[data-action="listing-map-back"]'));await page.locator('#public-listing').waitFor();
  server.active={kind:'search',id:ids.search};await publicPage('property',visibleKey);await interact(page.locator('[data-action="public-listing-map"]'));await page.waitForURL('https://www.google.com/maps/**');assert.equal(server.google.length,1);assert.equal(new URL(server.google[0]).searchParams.get('query'),'Debrecen Titkos közterület 12/A');assert.doesNotMatch(server.google[0],/47\.53312345|21\.62112345|key=/);
  assert.ok(server.requests.filter(item=>item.path.includes('/context')).every(item=>item.authorization==='Bearer public-listing-browser-session'));assert.ok(server.requests.filter(item=>item.path.startsWith('/public/')).every(item=>!item.authorization),'Public details and map descriptors remain anonymous even with an authenticated viewer');assert.deepEqual(server.unhandled,[]);assert.deepEqual(server.errors,[]);
  console.log(`Public signed-in listings ${viewport.name}: title navigation, interest icon/copy, under-title context, paged opposite-profile selection/cancel/scores, direct create+activation, buyer/seller pairs, direct partial decisions, selected final decisions, history and readonly address-safe maps passed.`);
 }catch(error){await mkdir('.local/browser-tests/screenshots',{recursive:true});await page.screenshot({path:resolve('.local/browser-tests/screenshots',`public-listings-signed-in-${viewport.name}-failure.png`),fullPage:true}).catch(()=>{});throw error;}
 finally{await context.close();}
}
const browser=await chromium.launch({headless:true});
try{for(const viewport of viewports){await verify(browser,viewport);await verifySignedIn(browser,viewport);}}finally{await browser.close();}
