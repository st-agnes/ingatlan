import {assertDescriptionContactFree} from './contact-policy.js';
import { MAX_SEARCH_LOCATIONS, getLocation, resolveLegacyLocations, isPropertyLocation, registerLocations, searchLocations, searchStreets, resolveStreetLocation, isStreetId } from './locations.js';
import {neighborhoodDemoPoints} from './neighborhood-demo-points.js';
import {streetDemoData} from './street-demo-data.js';
import {normalizePropertyAttributes, normalizeSearchAttributes} from './attributes.js';
import {normalizeAccountType,likeCost,canInteract,normalizeReportReason,normalizeListingProfilePagination,normalizeIncomingPagination} from './accounts.js';
import {prepareSearch,evaluateMatch,exactLocationMatch,valueForMoney,searchSpecificity,publicMaxPrice} from './matching.js';
import {publicFirstName,publicTitle} from './public-profile.js';
import {FEEDBACK_OPTIONS,FEEDBACK_QUESTION,FEEDBACK_PACKAGE_SIZES,FEEDBACK_DURATION_DAYS,FEEDBACK_PROMPT_SPACING,FEEDBACK_INVITATION_MINUTES,feedbackTitle} from './feedback.js';
import {sanitizeDraftData,sanitizeTeaserPrefill} from './onboarding.js';

/** Browser-only demonstration store. Real deployments use the authenticated .NET API. */
export const STORAGE_KEY = 'otthonra.demo.v3';
export const SELLER_LIKE_COST = 2;
export const LIKE_RESPONSE_DAYS = 14;
const LIKE_RESPONSE_WINDOW = LIKE_RESPONSE_DAYS * 86400000;
const clone = value => JSON.parse(JSON.stringify(value));
const uid = prefix => `${prefix}-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
const photos = ['/assets/home.jpg','/assets/living.jpg','/assets/bedroom.jpg','/assets/kitchen.jpg','/assets/terrace.jpg','/assets/living.jpg'];
const numeric = (value, fallback) => value === '' || value == null ? fallback : typeof value === 'boolean' ? NaN : Number(value);
const storedInstant = value => typeof value==='string'&&value.trim()?Date.parse(value):NaN;
const locationError = () => new Error('Válassz érvényes települést vagy budapesti kerületet a találati listából.');
const stablePayload = value => JSON.stringify(value,(_,item)=>item && typeof item==='object' && !Array.isArray(item)?Object.fromEntries(Object.keys(item).sort().map(key=>[key,item[key]])):item);
// This tiny source-backed subset makes the fictional seed usable without downloading the nationwide catalogue.
const demoStreets=registerLocations(streetDemoData);
function withLocations(entity, kind, strict = false) {
  let locations,invalidPropertyId,invalidSearchIds;
  if (kind === 'property' && ((Object.hasOwn(entity, 'locationId') && (strict || entity.locationId != null)) || entity.location?.id)) {
    const id=Object.hasOwn(entity,'locationId')&&(strict||entity.locationId!=null)?entity.locationId:entity.location.id;
    const location=getLocation(id);
    locations=isPropertyLocation(location)?[location]:[];
    if(strict&&!isPropertyLocation(location))throw locationError();
    if(!strict&&!locations.length){
      if(id==null||typeof id==='string'&&!id.trim())locations=resolveLegacyLocations(entity);
      else invalidPropertyId=id;
    }
  } else if (kind === 'search' && Object.hasOwn(entity, 'locationIds') && (strict || entity.locationIds != null)) {
    const ids = Array.isArray(entity.locationIds) ? [...new Set(entity.locationIds)] : [];
    const tooMany = Array.isArray(entity.locationIds) && entity.locationIds.length > MAX_SEARCH_LOCATIONS;
    locations=ids.map(getLocation).filter(Boolean);
    if(strict&&(!ids.length||tooMany||locations.length!==ids.length))throw locationError();
    if(!strict){
      if(!Array.isArray(entity.locationIds)||tooMany||locations.length!==ids.length){invalidSearchIds=entity.locationIds;locations=[];}
      else if(!ids.length)locations=resolveLegacyLocations(entity);
    }
  } else {
    locations = resolveLegacyLocations(entity);
  }
  if (strict && !locations.length) throw locationError();
  if (kind === 'property') {
    const location = locations[0] || null;
    return {...entity, locationId:location?.id ?? invalidPropertyId ?? '', location:clone(location), city:location?.city ?? entity.city ?? '', district:location ? location.district || '' : entity.district ?? '', lotArea:entity.type === 'Ház' ? numeric(entity.lotArea, null) : null};
  }
  return {...entity, locationIds:invalidSearchIds===undefined?locations.map(location=>location.id):clone(invalidSearchIds), locations:clone(locations), city:locations[0]?.city ?? entity.city ?? '', districts:locations.filter(location=>location.city === locations[0]?.city && location.district).map(location=>location.district)};
}
function migrateLocations(state) {
  state.users=state.users.map(user=>({...user,accountType:normalizeAccountType(user.accountType),feedbackPassCounter:Number.isSafeInteger(user.feedbackPassCounter)?Math.max(0,Math.min(FEEDBACK_PROMPT_SPACING,user.feedbackPassCounter)):0}));
  state.reports=Array.isArray(state.reports)?state.reports.map(report=>({...report,reason:report.reason??'suspected_agent'})):[];
  state.notifications=Array.isArray(state.notifications)?state.notifications:[];
  for(const key of ['propertyImpressions','feedbackPackages','feedbackInvitations'])state[key]=Array.isArray(state[key])?state[key]:[];
  // Saved search metadata is the bounded subset chosen from the demo's public catalogue.
  for (const search of state.searches) registerLocations(search.locations);
  state.properties = state.properties.map(entity=>{
    const property=normalizePropertyAttributes(withLocations(entity, 'property'));
    const details=property.addressDetails;
    const savedId=details?.streetId ?? property.streetId;
    const street=getLocation(savedId);
    const exact=details&&resolveStreetLocation(details.street,property.location,details.postalCode,street?[street]:[]);
    // An unchanged private association survives a reload before its public metadata is queried again.
    // Unknown IDs still cannot match until the search/picker registers the real catalogue choice.
    property.streetId=street?exact?.id??null:isStreetId(savedId)?savedId:null;
    if(details)details.streetId=property.streetId;
    return property;
  });
  state.searches = state.searches.map(entity=>normalizeSearchAttributes(withLocations(entity, 'search')));
  return state;
}
const privatePropertyFields = ['streetId','streetMetadata','streetLocation','street','houseNumber','postalCode','latitude','longitude','coordinates','geocodingStatus','geocodingProvider','geocodedAt','formattedAddress','provider','quality','geocodingPlaceId','geocodingAddressKey','geocodingQuality','creationRequestId','creationRequestHash','creationRequestHashVersion','addressDetails'];
const visibleEntity = (entity,users,specificity,viewerId) => {
  if(!entity)return null;
  const result = clone(entity);
  result.publicListingKey=demoSourceKey(Array.isArray(entity.locationIds)?'search':'property',entity.id);
  delete result.email; delete result.phone;
  for(const field of privatePropertyFields)if(field!=='addressDetails')delete result[field];
  if(entity.ownerId!==viewerId){
    for(const field of privatePropertyFields)delete result[field];
    if(Object.hasOwn(entity,'locationId')){const street=entity.hideStreet===false?String(entity.addressDetails?.street||''):'',number=entity.hideStreet===false&&entity.hideHouseNumber===false?String(entity.addressDetails?.houseNumber||''):'';if(entity.hideStreet===false)result.street=street;if(entity.hideStreet===false&&entity.hideHouseNumber===false)result.houseNumber=number;result.address=[street,number].filter(Boolean).join(' ');}
  }
  const owner=users?.find(user=>user.id===entity.ownerId);
  result.ownerAccountType=normalizeAccountType(owner?.accountType);
  result.ownerFirstName=publicFirstName(owner?.name);
  if(Array.isArray(entity.locationIds)){
    const own=entity.ownerId===viewerId;
    if(!own){result.maxPrice=publicMaxPrice(entity);delete result.publicMaxPrice;}
    result.searchSpecificity=specificity??searchSpecificity(entity,{perspective:own?'buyer':'seller'});
  }
  return result;
};

function seed(now) {
  const time = now();
  const users = [
    {id:'me',name:'Nagy Anna',email:'anna@example.hu',phone:'+36 30 555 0123',avatar:'NA'},
    {id:'u1',name:'Kovács Péter',email:'peter@example.hu',phone:'+36 30 555 0141',avatar:'KP'},
    {id:'u2',accountType:'agent',name:'Szabó Eszter',email:'eszter@example.hu',phone:'+36 20 555 0142',avatar:'SZE'},
    {id:'u3',name:'Varga Dániel',email:'daniel@example.hu',phone:'+36 70 555 0143',avatar:'VD'},
    {id:'u4',name:'Tóth Réka',email:'reka@example.hu',phone:'+36 30 555 0144',avatar:'TR'},
    {id:'u5',name:'Farkas Bence',email:'bence@example.hu',phone:'+36 20 555 0145',avatar:'FB'},
    {id:'u6',name:'Molnár Júlia',email:'julia@example.hu',phone:'+36 70 555 0146',avatar:'MJ'}
  ];
  const pointName=value=>String(value).normalize('NFD').replace(/\p{M}/gu,'').toLocaleLowerCase('hu').replace(/[\s-]/g,'');
  let demoAddressNumber=0;
  const property = (id,ownerId,title,district,neighborhood,price,area,rooms,image,extras={}) => {
    // These fictional seed identities explicitly use verified synthetic points; this is never an address lookup.
    const point=neighborhoodDemoPoints.find(value=>value.synthetic&&value.city==='Budapest'&&pointName(value.name)===pointName(neighborhood));
    if(!point)throw new Error('A fiktív demóingatlan városrészi tesztpontja hiányzik.');
    const districtNumber=Number(resolveLegacyLocations({city:'Budapest',district})[0].id.split(':').at(-1));
    const preferredStreet={'Szentimreváros':'Bartók Béla út','Lágymányos':'Karinthy Frigyes út','Albertfalva':'Budafoki út',
      'Újlipótváros':'Pozsonyi út','Vizafogó':'Váci út','Marina-part':'Váci út','Országút':'Margit körút','Pasarét':'Pasaréti út','Rózsadomb':'Fény utca'}[neighborhood];
    const street=demoStreets.find(value=>value.city==='Budapest'&&value.district===district&&value.streetName===preferredStreet);
    const addressDetails={street:street?.streetName??'Fiktív demó utca',streetId:street?.id??null,houseNumber:`99999/${++demoAddressNumber}`,postalCode:street?.postalCodes[0]??String(1001+districtNumber*10),
      latitude:point.latitude,longitude:point.longitude,geocodedAt:null,provider:'synthetic-demo',quality:'synthetic',geocodingStatus:'demo-synthetic'};
    return {id,ownerId,title,city:'Budapest',district,neighborhood,type:'Lakás',price,area,rooms,floor:3,condition:'Felújított',building:'Tégla',balcony:true,balconyArea:6,elevator:true,description:'Világos, átgondolt elrendezésű otthon, kellemes környezetben. A nappalit nagy ablakok teszik igazán napfényessé. Kiváló közlekedés, kedvenc kávézók és zöldterületek néhány perc sétára.',images:[photos[image],photos[(image+1)%photos.length],photos[(image+2)%photos.length]],archived:false,createdAt:time,...extras,addressDetails,neighborhoodIds:[...point.membershipIds]};
  };
  const properties = [
    property('own-p1','me','Napfényes lakás a Bartók-negyedben','XI.','Szentimreváros',67.9,58,2,3),
    property('p1','u1','A következő fejezeted itt kezdődik','XIII.','Újlipótváros',72.9,64,3,0,{address:'Pozsonyi út környéke',description:'Reggeli fények, tágas terek és egy igazán szerethető környék. Ez a felújított, erkélyes újlipótvárosi lakás készen áll a következő történetére. Amerikai konyhás nappali, két külön nyíló hálószoba és rengeteg természetes fény vár. A Duna-part és a Szent István park csak egy rövid séta.'}),
    property('p2','u2','Zöldre néző otthon a Feneketlen-tónál','XI.','Szentimreváros',78.5,71,3,1,{floor:2}),
    property('p3','u3','Csendes sziget a város felett','II.','Országút',81.9,68,3,2,{floor:1}),
    property('p4','u4','Kis ékszerdoboz a Duna közelében','XIII.','Vizafogó',62.5,54,2,4),
    property('p5','u5','Tágas terek, új lehetőségek','XI.','Albertfalva',69.9,76,4,5,{floor:4}),
    property('p6','u6','Letisztult elegancia Pasaréten','II.','Pasarét',84.5,82,3,3),
    property('matched-p1','u2','Otthonos zug a Palatinus-házban','XIII.','Újlipótváros',74.9,66,3,2),
    property('matched-p2','u3','Világos, erkélyes lakás Budán','XI.','Lágymányos',68.9,61,3,1),
    property('matched-p3','u4','Kilátás a Rózsadombra','II.','Rózsadomb',82.9,74,3,4),
    property('incompatible-p1','u5','Belvárosi garzon','V.','Belváros',42.5,29,1,5),
    property('incompatible-p2','u6','Panorámás penthouse','XIII.','Marina-part',129.9,118,4,0)
  ];
  const search = (id,ownerId,title,extras={}) => ({id,ownerId,title,city:'Budapest',districts:['XIII.','XI.','II.'],type:'Lakás',minPrice:55,maxPrice:85,minArea:50,maxArea:85,minRooms:2,maxRooms:4,description:'Egy világos, szerethető otthont keresünk jó közlekedéssel. Fontos a praktikus elrendezés és a kellemes környék.',moveIn:'3 hónapon belül',balcony:false,elevator:false,archived:false,createdAt:time,...extras});
  const searches = [
    search('own-s1','me','Első közös otthonunk'),
    search('own-s2','me','Befektetés Budán',{districts:['XI.','II.'],minPrice:35,maxPrice:65,minArea:25,maxArea:55,minRooms:1,maxRooms:2,description:'Jól kiadható, kisebb lakást keresek Budán, hosszú távú befektetésként.'}),
    search('s1','u1','Közös otthonunkat keressük',{districts:['XI.','XIII.'],maxPrice:75,minArea:50,maxArea:75,maxRooms:3,buyerName:'Péter és Lilla',description:'Fiatal párként a következő közös fejezetünkhöz keresünk napfényes otthont. Szeretünk a környéken sétálni, ezért örülnénk közeli zöldterületnek.',financing:'Előminősített lakáshitel',moveIn:'1–3 hónapon belül'}),
    search('s2','u2','Kisebb, de saját otthon Budán',{districts:['XI.','II.'],minPrice:45,maxPrice:72,minArea:40,maxArea:65,maxRooms:3,buyerName:'Eszter',financing:'Készpénzes vásárló'}),
    search('s3','u3','Lakásból otthont',{districts:['XI.'],minPrice:50,maxPrice:80,minArea:55,maxArea:90,buyerName:'Dániel',balcony:true,financing:'Önerő + lakáshitel'}),
    search('s4','u4','Közelebb a családhoz',{districts:['XI.','XXII.'],minPrice:55,maxPrice:78,minArea:50,maxArea:80,buyerName:'Réka',elevator:true,financing:'Saját megtakarítás'}),
    search('incompatible-s1','u5','Tágas családi ház',{type:'Ház',districts:['II.'],maxPrice:150,minArea:100,maxArea:200,minRooms:4,maxRooms:7})
  ];
  const decisions = [
    {id:'seed-prelike',actorKind:'property',actorId:'p1',propertyId:'p1',searchId:'own-s1',liked:true,createdAt:time},
    {id:'seed-buyer-prelike',actorKind:'search',actorId:'s1',propertyId:'own-p1',searchId:'s1',liked:true,createdAt:time}
  ];
  const matches = [];
  ['matched-p1','matched-p2','matched-p3'].forEach((propertyId,i) => {
    decisions.push({id:`seed-buy-${i}`,actorKind:'search',actorId:'own-s1',propertyId,searchId:'own-s1',liked:true,createdAt:time});
    decisions.push({id:`seed-sell-${i}`,actorKind:'property',actorId:propertyId,propertyId,searchId:'own-s1',liked:true,createdAt:time});
    matches.push({id:`m${i+1}`,propertyId,searchId:'own-s1',createdAt:new Date(new Date(time).getTime()-(i+1)*86400000).toISOString(),unread:i===0?1:0,messages:i===0?[{id:'seed-message',senderId:'u2',text:'Szia Anna! Örülök a találatnak. Szívesen megmutatom a lakást a hétvégén, ha nektek is megfelelő.',createdAt:time}]:[]});
  });
  return {version:3,users,userId:'me',credits:24,active:{kind:'search',id:'own-s1'},properties,searches,decisions,matches,ledger:[{id:'initial-credit',amount:24,type:'demo_grant',description:'Kezdő demókreditek',createdAt:time}],createdAt:time};
}

// Public preview history is in memory only and never touches the saved workspace.
const publicDemoSelections=new Map();
const publicDemoType=type=>['Lakás','Ház'].includes(type)?type:'Ingatlan';
const publicDemoBucket=(value,limits)=>{if(value==null)return 'open';const index=limits.findIndex(limit=>Number(value)<limit);return index<0?limits.length:index;};
// Only fictional browser-demo IDs reach this deterministic identity helper.
// Hosted source identities are SHA256-derived by the backend, never generated from browser input.
function demoSourceKey(kind,id) {
  const value=`otthonra:demo-source:v1:${kind}:${id}`;
  return kind+'-'+Array.from({length:8},(_,salt)=>{
    let hash=(0x811c9dc5^Math.imul(salt+1,0x9e3779b9))>>>0;
    for(let index=0;index<value.length;index++)hash=Math.imul(hash^value.charCodeAt(index),0x01000193)>>>0;
    return hash.toString(16).padStart(8,'0');
  }).join('');
}
function samplePublicDemo(items,limit,kind,scope,random) {
  const draw=()=>{const value=Number(random());return Number.isFinite(value)?Math.max(0,Math.min(1-Number.EPSILON,value)):0;};
  const key=kind+':'+scope,previous=publicDemoSelections.get(key)||[];
  // Excluding one previous member guarantees a different set whenever there is a spare candidate.
  const excluded=items.length>limit&&previous.length?previous[Math.floor(draw()*previous.length)]:null;
  const remaining=items.filter(item=>item.id!==excluded).map(item=>{
    const locations=kind==='search'?item.locations:[item.location];
    const budget=kind==='search'?publicMaxPrice(item)??item.minPrice:item.price;
    const size=kind==='search'?item.minArea??item.maxArea:item.area;
    const rooms=kind==='search'?item.minRooms??item.maxRooms:item.rooms;
    return {item,features:[['type:'+publicDemoType(item.type),3],['budget:'+publicDemoBucket(budget,[30,60,90,150]),2],['area:'+publicDemoBucket(size,[40,70,100,160]),1.5],['rooms:'+publicDemoBucket(rooms,[2,3,4,6]),1],...locations.slice(0,3).map(location=>['location:'+location.id,1])],tie:draw()};
  });
  const selected=[],seen=new Set();
  while(remaining.length&&selected.length<limit) {
    let best=0,bestScore=-1;
    for(let i=0;i<remaining.length;i++) {
      const candidate=remaining[i],score=candidate.features.reduce((sum,[feature,weight])=>sum+(seen.has(feature)?0:weight),0)+candidate.tie*.25;
      if(score>bestScore){best=i;bestScore=score;}
    }
    const [chosen]=remaining.splice(best,1);selected.push(chosen.item);chosen.features.forEach(([feature])=>seen.add(feature));
  }
  // Shuffle the selected set too, so variety is visible in the first cards.
  for(let i=selected.length-1;i>0;i--){const j=Math.floor(draw()*(i+1));[selected[i],selected[j]]=[selected[j],selected[i]];}
  publicDemoSelections.set(key,selected.map(item=>item.id));
  return selected;
}

/** Fictional public preview: real sample titles and first names, never saved users or contacts. */
function demoPublicCatalog() {
  const sample=migrateLocations(seed(()=>new Date().toISOString()));
  // These extra examples belong solely to the public preview, never to the user's stored profiles.
  const searchExamples=[
    ['district:Budapest:8','Lakás',null,35,20,40,1,2],
    ['district:Budapest:22','Ház',60,110,85,160,3,6],
    ['district:Budapest:2','Ház',120,220,140,280,5,9],
    ['district:Budapest:5','Lakás',95,160,90,150,3,5],
    ['district:Budapest:14','Lakás',null,55,30,55,1,3],
    ['district:Budapest:17','Ház',20,null,100,null,4,null]
  ].map(([id,type,minPrice,maxPrice,minArea,maxArea,minRooms,maxRooms],index)=>({id:'public-search-'+index,title:['Első otthonomat keresem a városban','Családi házat keresünk kerttel','Tágas otthont keresünk Budán','Világos, belvárosi lakást szeretnénk','Kis lakást keresek jó közlekedéssel','Nagyobb otthonba költöznénk'][index],ownerId:index%2?'u2':'u1',type,minPrice,maxPrice,minArea,maxArea,minRooms,maxRooms,locations:[getLocation(id)]}));
  const propertyExamples=[
    ['district:Budapest:22','Ház',74.9,95,3,450],
    ['district:Budapest:2','Ház',169,180,5,1000],
    ['district:Budapest:8','Lakás',28.9,25,1,null],
    ['district:Budapest:5','Lakás',219,150,5,null]
  ].map(([id,type,price,area,rooms,lotArea],index)=>({id:'public-property-'+index,title:['Kertkapcsolatos otthon nyugodt környéken','Tágas családi otthon a zöldben','Kompakt városi otthon','Nagy terek a belváros szívében'][index],ownerId:index%2?'u2':'u1',type,price,area,rooms,wholeRooms:rooms,halfRooms:0,lotArea,location:getLocation(id)}));
  const extraSearches=[['district:Budapest:6','Lakás',45,75,35,65,1.5,3],['district:Budapest:9','Lakás',80,140,70,110,3,5],['district:Budapest:19','Ház',40,80,65,120,2,4],['district:Budapest:23','Ház',70,150,110,210,4,7],['district:Budapest:11','Lakás',null,45,20,45,1,2],['district:Budapest:16','Ház',150,300,180,350,6,10]].map(([id,type,minPrice,maxPrice,minArea,maxArea,minRooms,maxRooms],index)=>({id:'public-search-extra-'+index,title:['Központi otthont szeretnék','Több helyet keresünk a családnak','Kertes házat keresünk','Nyugodt kertvárosba költöznénk','Kisebb otthon, nagy lehetőségek','Tágas családi otthont keresünk'][index],ownerId:index%2?'u4':'u5',type,minPrice,maxPrice,minArea,maxArea,minRooms,maxRooms,locations:[getLocation(id)],description:'Nyugodt otthont keresünk jól használható terekkel.'}));
  return {sample,searches:[...sample.searches,...searchExamples,...extraSearches],properties:[...sample.properties,...propertyExamples]};
}
export function demoLanding(region=null,random=Math.random) {
  const {sample,searches:allSearches,properties:allProperties}=demoPublicCatalog();
  const available=!region||region.id==='HU110';
  const ownerType=entity=>normalizeAccountType(sample.users.find(user=>user.id===entity.ownerId)?.accountType);
  const ownerFirstName=entity=>publicFirstName(sample.users.find(user=>user.id===entity.ownerId)?.name);
  const scope=region?.id||'national';
  const searches=available?samplePublicDemo(allSearches,16,'search',scope,random):[];
  const properties=available?samplePublicDemo(allProperties,8,'property',scope,random):[];
  return {
    region:clone(region),scope:region?'region':'national',
    searches:searches.map((entity,index)=>({key:`search-${index+1}`,sourceKey:demoSourceKey('search',entity.id),href:'#listing/search/'+demoSourceKey('search',entity.id),title:publicTitle(entity.title,'Ingatlant keresnek'),type:publicDemoType(entity.type),locations:entity.locations.map(location=>location.label),minPrice:entity.minPrice,maxPrice:publicMaxPrice(entity),minArea:entity.minArea,maxArea:entity.maxArea,minRooms:entity.minRooms,maxRooms:entity.maxRooms,ownerAccountType:ownerType(entity),ownerFirstName:ownerFirstName(entity),prefill:sanitizeTeaserPrefill('search',entity)})),
    properties:properties.map((entity,index)=>({key:`property-${index+1}`,sourceKey:demoSourceKey('property',entity.id),href:'#listing/property/'+demoSourceKey('property',entity.id),image:Array.isArray(entity.images)?entity.images[0]||null:null,title:publicTitle(entity.title,'Eladó ingatlan'),type:publicDemoType(entity.type),location:entity.location.label,price:entity.price,area:entity.area,wholeRooms:entity.wholeRooms??null,halfRooms:entity.halfRooms??null,rooms:entity.rooms,lotArea:entity.lotArea??null,ownerAccountType:ownerType(entity),ownerFirstName:ownerFirstName(entity),prefill:sanitizeTeaserPrefill('property',{...entity,locations:[getLocation(entity.neighborhoodIds?.[0])||entity.location]})}))
  };
}

/** Resolve only the fixed fictional public catalogue, never the visitor's saved private state. */
export function demoPublicListing(kind,key) {
  if(!['property','search'].includes(kind)||typeof key!=='string'||!new RegExp('^'+kind+'-[a-f0-9]{64}$').test(key))throw new Error('A hirdetés nem érhető el.');
  const {sample,searches,properties}=demoPublicCatalog(),entity=(kind==='property'?properties:searches).find(item=>!item.archived&&demoSourceKey(kind,item.id)===key);
  if(!entity)throw new Error('A hirdetés nem érhető el.');
  const owner=sample.users.find(user=>user.id===entity.ownerId),title=publicTitle(entity.title,kind==='property'?'Eladó ingatlan':'Ingatlant keresnek');
  const ownerFirstName=publicFirstName(owner?.name),ownerAccountType=normalizeAccountType(owner?.accountType);
  const fields=kind==='property'?['type','description','price','area','rooms','wholeRooms','halfRooms','lotArea','floor','floorIsUpperRange','buildingFloors','isAttic','condition','building','constructionAge','view','ceilingHeight','heatingType','insulated','energyRating','energyRatingScheme','airConditioning','solarPanels','parkingTypes','parkingType','balcony','elevator','privateGarden','hideStreet','hideHouseNumber','images']:['type','description','minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms','conditions','buildings','constructionAges','views','ceilingHeight','floors','heatingTypes','atticPreference','minEnergyRating','excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden','balcony','elevator','moveIn','financing'];
  const normalized=kind==='property'?normalizePropertyAttributes(entity):{...normalizeSearchAttributes(entity),maxPrice:publicMaxPrice(entity)};
  const listing={title,...Object.fromEntries(fields.filter(field=>Object.hasOwn(normalized,field)).map(field=>[field,clone(normalized[field])]))};
  if(kind==='property'){
    listing.location=entity.location?.label||getLocation(entity.locationId)?.label||'';listing.city=entity.city||'';listing.district=entity.district||'';listing.neighborhood=entity.neighborhood||'';
    listing.street=normalized.hideStreet?'':String(entity.addressDetails?.street||'');listing.houseNumber=normalized.hideHouseNumber?'':String(entity.addressDetails?.houseNumber||'');listing.address=[listing.street,listing.houseNumber].filter(Boolean).join(' ');
  }else listing.locations=(entity.locations||[]).map(location=>location.label);
  const prefill=sanitizeTeaserPrefill(kind,kind==='property'?{...normalized,locations:[getLocation(entity.neighborhoodIds?.[0])||entity.location]}:normalized);
  return {kind,key,sourceKey:key,title,ownerFirstName,ownerAccountType,listing,prefill,...(kind==='search'?{clonePrefill:{...prefill,description:String(entity.description||''),moveIn:String(entity.moveIn||''),financing:String(entity.financing||'')}}:{})};
}

const notificationPages = new Set(['incoming','messages','insights','credits']);
const notificationTarget = (page,entityKind=null,entityId=null,propertyId=null,searchRequestId=null,matchId=null) => ({page,entityKind,entityId,propertyId,searchRequestId,matchId});
function safeNotificationTarget(value,kind='') {
  if(!value||!notificationPages.has(value.page))return ['like_refund','feedback_refund','credit_added'].includes(kind)?notificationTarget('credits'):null;
  const reference=value=>typeof value==='string'&&value?value:null;
  return notificationTarget(value.page,['property','search'].includes(value.entityKind)?value.entityKind:null,reference(value.entityId),reference(value.propertyId),reference(value.searchRequestId),reference(value.matchId));
}
function publicNotification(item) {
  return {id:item.id,kind:item.kind,amount:Number(item.amount||0),text:String(item.text||''),decisionId:item.decisionId??null,feedbackPackageId:item.feedbackPackageId??null,createdAt:item.createdAt,readAt:item.readAt??null,target:safeNotificationTarget(item.target,item.kind)};
}
function newNotificationCount(state) {
  const visited=Date.parse(state.users.find(user=>user.id===state.userId)?.notificationLastVisitAt||'');
  return state.notifications.filter(item=>item.userId===state.userId&&(!Number.isFinite(visited)||Date.parse(item.createdAt)>visited)).length;
}
/** Idempotent migration/live projection of fictional source events, outside the active-profile filter. */
function synchronizeActivityNotifications(s) {
  s.notifications=Array.isArray(s.notifications)?s.notifications:[];
  s.notificationLedgerOwnerId ||= s.userId;
  const existing=new Map();
  for(const item of s.notifications){
    if(!item.eventKey&&item.kind==='like_refund'&&item.decisionId)item.eventKey='like_refund:'+item.decisionId;
    if(!item.eventKey&&item.kind==='feedback_refund'&&item.feedbackPackageId)item.eventKey='feedback_refund:'+item.feedbackPackageId;
    if(item.eventKey)existing.set(item.userId+':'+item.eventKey,item);
    item.target=safeNotificationTarget(item.target,item.kind);
  }
  const propertyById=new Map(s.properties.map(item=>[item.id,item])),searchById=new Map(s.searches.map(item=>[item.id,item]));
  const userIds=new Set(s.users.map(item=>item.id));
  const add=(userId,kind,sourceId,createdAt,text,target,extra={})=>{
    if(!userIds.has(userId)||!sourceId||!Number.isFinite(storedInstant(createdAt)))return;
    const eventKey=kind+':'+sourceId,key=userId+':'+eventKey;
    if(existing.has(key))return;
    const item={id:demoSourceKey('notification',key),userId,eventKey,kind,amount:0,text,createdAt,readAt:null,target,...extra};
    s.notifications.push(item);existing.set(key,item);
  };
  const pair=(propertyId,searchId)=>{const property=propertyById.get(propertyId),search=searchById.get(searchId);return property&&search&&property.ownerId!==search.ownerId?{property,search}:null;};
  for(const decision of s.decisions){
    if(decision.liked!==true||!['property','search'].includes(decision.actorKind))continue;
    const entities=pair(decision.propertyId,decision.searchId);if(!entities)continue;
    const {property,search}=entities;
    if(decision.actorId!==(decision.actorKind==='property'?property.id:search.id))continue;
    const kind=decision.actorKind==='property'?'search':'property',ownEntity=kind==='property'?property:search;
    add(ownEntity.ownerId,'incoming_like',decision.id,decision.createdAt,`Érdeklődés érkezett a(z) „${ownEntity.title}” profilodra.`,notificationTarget('incoming',kind,ownEntity.id,property.id,search.id));
  }
  for(const match of s.matches){
    const entities=pair(match.propertyId,match.searchId);if(!entities)continue;
    const {property,search}=entities;
    if(!['property','search'].every(kind=>s.decisions.some(item=>item.propertyId===property.id&&item.searchId===search.id&&item.actorKind===kind&&item.liked)))continue;
    for(const [kind,ownEntity] of [['property',property],['search',search]])add(ownEntity.ownerId,'match_created',match.id,match.createdAt,`Új párosításod van a(z) „${ownEntity.title}” profilodhoz.`,notificationTarget('messages',kind,ownEntity.id,property.id,search.id,match.id));
    for(const message of match.messages||[]){
      const recipient=message.senderId===property.ownerId?search.ownerId:message.senderId===search.ownerId?property.ownerId:null;
      const kind=recipient===property.ownerId?'property':'search',ownEntity=kind==='property'?property:search;
      if(recipient)add(recipient,'message_received',message.id,message.createdAt,`Új üzenetet kaptál a(z) „${ownEntity.title}” profilodhoz.`,notificationTarget('messages',kind,ownEntity.id,property.id,search.id,match.id));
    }
  }
  for(const invitation of s.feedbackInvitations||[]){
    if(!invitation.answeredAt||!invitation.reason||invitation.reason==='decline')continue;
    const property=propertyById.get(invitation.propertyId);if(!property)continue;
    add(property.ownerId,'feedback_received',invitation.id,invitation.answeredAt,`Új visszajelzés érkezett a(z) „${property.title}” ingatlanodról.`,notificationTarget('insights','property',property.id,property.id),{feedbackPackageId:invitation.packageId??null});
  }
  for(const pkg of s.feedbackPackages||[]){
    const property=propertyById.get(pkg.propertyId);if(!property)continue;
    const target=notificationTarget('insights','property',property.id,property.id);
    if(pkg.receivedCount>=pkg.size){
      const responses=(s.feedbackInvitations||[]).filter(item=>item.packageId===pkg.id&&item.answeredAt&&item.reason&&item.reason!=='decline').sort((a,b)=>String(b.answeredAt).localeCompare(String(a.answeredAt)));
      add(pkg.ownerId,'feedback_completed',pkg.id,responses[0]?.answeredAt||pkg.createdAt,`Összegyűlt a(z) „${property.title}” ingatlanhoz kért összes visszajelzés.`,target,{feedbackPackageId:pkg.id});
    }
    if(pkg.refundedAt)add(pkg.ownerId,'feedback_expired',pkg.id,pkg.refundedAt,`Lejárt a(z) „${property.title}” ingatlan visszajelzés-csomagja.`,target,{feedbackPackageId:pkg.id});
  }
  for(const entry of s.ledger||[]){
    const kind=entry.kind||entry.type;
    if(Number(entry.amount)>0&&!['like_refund','feedback_refund'].includes(kind))add(entry.userId||entry.ownerId||s.notificationLedgerOwnerId,'credit_added',entry.id,entry.createdAt,`${Number(entry.amount)} kreditet jóváírtunk a számládon.`,notificationTarget('credits'),{amount:Number(entry.amount)});
  }
}

export function isCompatible(property,search,options) {
  if (!property || !search || property.archived || search.archived || property.ownerId===search.ownerId) return false;
  return evaluateMatch(property,prepareSearch(search,options)).isExact;
}

let publicStreetCatalog;
async function loadPublicStreetCatalog() {
  if (!publicStreetCatalog) publicStreetCatalog=(async()=>{
    if (typeof DecompressionStream !== 'function') throw new Error('Az utcakeresőhöz frissebb böngésző szükséges.');
    const response=await fetch(new URL('./data/streets.json.gz',import.meta.url));
    if(!response.ok)throw new Error('Az utcakatalógus most nem érhető el. Próbáld újra.');
    const stream=new Blob([await response.arrayBuffer()]).stream().pipeThrough(new DecompressionStream('gzip'));
    const data=await new Response(stream).json();
    const values=Array.isArray(data)?data:data.streets??data.items;
    if(!Array.isArray(values))throw new Error('Az utcakatalógus érvénytelen.');
    return values.filter(street=>isStreetId(street?.id)).map(street=>({...street,kind:'street'}));
  })().catch(error=>{publicStreetCatalog=null;throw error;});
  return publicStreetCatalog;
}

async function loadDemoMatchingGeography(ids,options) {
  // Offline model consumers remain synchronous and need no network. Only a
  // mounted browser demo prepares public, simplified map geometry on demand.
  if(typeof window==='undefined')return null;
  const module=await import('./location-map.js');
  return {geometries:await module.loadDemoMatchingGeometries(ids,getLocation,options),distance:module.demoDistanceToGeometryKm};
}
function demoCoordinates(property) {
  const latitude=property?.addressDetails?.latitude??property?.latitude,longitude=property?.addressDetails?.longitude??property?.longitude;
  return typeof latitude==='number'&&typeof longitude==='number'&&Number.isFinite(latitude)&&Number.isFinite(longitude)
    &&latitude>=-90&&latitude<=90&&longitude>=-180&&longitude<=180?[longitude,latitude]:null;
}
const demoAreaIds=prepared=>[...[...prepared.cities].map(city=>'city:'+city),...prepared.districtIds,...prepared.neighborhoodIds];

export function createModel(storage=globalThis.localStorage, now=()=>new Date().toISOString(), {streetCatalog,streetLoader=loadPublicStreetCatalog,geographyLoader=loadDemoMatchingGeography}={}) {
  if (streetCatalog) registerLocations(streetCatalog);
  let modelStreetCatalog=streetCatalog;
  const findStreetCatalog=async()=>modelStreetCatalog??(modelStreetCatalog=await streetLoader());
  let state;
  try {const saved=JSON.parse(storage?.getItem(STORAGE_KEY)||'null');if(saved?.version===3&&Array.isArray(saved.properties)&&Array.isArray(saved.searches)&&Array.isArray(saved.decisions)&&Array.isArray(saved.matches)&&Array.isArray(saved.users)&&Number.isFinite(saved.credits))state=saved;} catch {}
  state = migrateLocations(state || seed(now));
  synchronizeActivityNotifications(state);
  const own = (s,kind,id) => (kind==='property'?s.properties:s.searches).find(e=>e.id===id&&e.ownerId===s.userId);
  const ownersCanInteract=(s,property,search)=>canInteract(s.users.find(user=>user.id===property?.ownerId)?.accountType,s.users.find(user=>user.id===search?.ownerId)?.accountType);
  let demoGeography=null;
  const distanceCache=new Map();
  const demoLocationDistance=(property,prepared)=>{
    if(exactLocationMatch(property,prepared))return 0;
    const point=demoCoordinates(property),ids=demoAreaIds(prepared);
    if(!point||!prepared.hasNonStreetLocations||!demoGeography||!ids.length||ids.some(id=>!demoGeography.geometries.has(id)))return null;
    const key=JSON.stringify([point,[...ids].sort()]);
    if(distanceCache.has(key))return distanceCache.get(key);
    const distances=ids.map(id=>demoGeography.distance(point,demoGeography.geometries.get(id)));
    const distance=distances.every(value=>typeof value==='number'&&Number.isFinite(value)&&value>=0)?Math.min(...distances):null;
    distanceCache.set(key,distance);
    if(distanceCache.size>256)distanceCache.delete(distanceCache.keys().next().value);
    return distance;
  };
  const evaluateDemoMatch=(property,prepared,options={})=>evaluateMatch(property,prepared,{...options,locationDistanceKm:demoLocationDistance(property,prepared)});
  const transact = fn => {
    const draft=clone(state);
    const result=fn(draft);
    synchronizeActivityNotifications(draft);
    try {storage?.setItem(STORAGE_KEY,JSON.stringify(draft));} catch {throw new Error('A böngésző tárhelye megtelt. A módosítás nem került mentésre.');}
    state=draft;
    return clone(result ?? null);
  };
  const refundDue = (s,at) => {
    const timestamp = new Date(at).getTime();
    if(!Number.isFinite(timestamp))return [];
    return s.decisions.filter(decision=>{
      if(!decision.liked||!own(s,decision.actorKind,decision.actorId)||!Number.isSafeInteger(decision.charged)||decision.charged<=0||decision.refundedAt)return false;
      const created = storedInstant(decision.createdAt),deadline=created+LIKE_RESPONSE_WINDOW;
      if(!Number.isFinite(created)||timestamp<deadline)return false;
      return !s.decisions.some(response=>response.actorKind!==decision.actorKind&&response.propertyId===decision.propertyId&&response.searchId===decision.searchId&&Number.isFinite(storedInstant(response.createdAt))&&storedInstant(response.createdAt)<=deadline);
    });
  };
  const feedbackPackageDue=(s,at)=>s.feedbackPackages.filter(pkg=>pkg.ownerId===s.userId&&!pkg.refundedAt
    &&Number.isFinite(storedInstant(pkg.expiresAt))&&storedInstant(pkg.expiresAt)<=storedInstant(at));
  const feedbackPackageView=(pkg,at)=>pkg?{
    id:pkg.id,size:pkg.size,receivedCount:pkg.receivedCount,remaining:Math.max(0,pkg.size-pkg.receivedCount),
    enabled:!pkg.refundedAt&&storedInstant(pkg.expiresAt)>storedInstant(at)&&pkg.receivedCount<pkg.size,createdAt:pkg.createdAt,expiresAt:pkg.expiresAt,refundedAt:pkg.refundedAt??null,
    refundedCredits:pkg.refundedCredits??0,status:pkg.refundedAt||storedInstant(pkg.expiresAt)<=storedInstant(at)?'expired':pkg.receivedCount>=pkg.size?'completed':'active'
  }:null;
  const activeFeedbackPackage=(s,propertyId,at)=>s.feedbackPackages.find(pkg=>pkg.propertyId===propertyId&&!pkg.refundedAt&&storedInstant(pkg.expiresAt)>storedInstant(at));
  const liveFeedbackInvitation=(s,invitation,at)=>{
    if(invitation.answeredAt||storedInstant(invitation.expiresAt)<=storedInstant(at))return false;
    const pkg=s.feedbackPackages.find(item=>item.id===invitation.packageId);
    return !!pkg&&!pkg.refundedAt&&storedInstant(pkg.expiresAt)>storedInstant(at)&&pkg.receivedCount<pkg.size;
  };
  const pendingFeedbackInvitation=(s,at)=>s.feedbackInvitations.find(item=>item.buyerId===s.userId&&liveFeedbackInvitation(s,item,at));
  const feedbackPrompt=(s,invitation)=>{
    if(!invitation)return null;
    const property=s.properties.find(item=>item.id===invitation.propertyId),seller=s.users.find(item=>item.id===property?.ownerId);
    const sellerFirstName=publicFirstName(seller?.name);
    return {id:invitation.id,propertyId:invitation.propertyId,sellerFirstName,title:feedbackTitle(sellerFirstName),
      question:FEEDBACK_QUESTION,options:clone(FEEDBACK_OPTIONS),expiresAt:invitation.expiresAt};
  };
  const offerFeedback=(s,decision,property)=>{
    if(decision.actorKind!=='search'||decision.liked)return null;
    const at=now(),buyer=s.users.find(user=>user.id===s.userId);
    buyer.feedbackPassCounter=Math.min(FEEDBACK_PROMPT_SPACING,(buyer.feedbackPassCounter||0)+1);
    const pending=pendingFeedbackInvitation(s,at);
    if(pending)return feedbackPrompt(s,pending);
    if(buyer.feedbackPassCounter<FEEDBACK_PROMPT_SPACING)return null;
    const pkg=activeFeedbackPackage(s,property.id,at);
    if(!pkg||pkg.receivedCount>=pkg.size||s.feedbackInvitations.some(item=>item.packageId===pkg.id&&item.buyerId===s.userId))return null;
    const reservations=s.feedbackInvitations.filter(item=>item.packageId===pkg.id&&liveFeedbackInvitation(s,item,at)).length;
    if(pkg.receivedCount+reservations>=pkg.size)return null;
    const invitation={id:uid('feedback'),packageId:pkg.id,propertyId:property.id,decisionId:decision.id,buyerId:s.userId,
      createdAt:at,expiresAt:new Date(Math.min(storedInstant(at)+FEEDBACK_INVITATION_MINUTES*60000,storedInstant(pkg.expiresAt))).toISOString(),answeredAt:null,reason:null};
    s.feedbackInvitations.push(invitation);buyer.feedbackPassCounter=0;
    return feedbackPrompt(s,invitation);
  };
  const processRefunds = () => {
    const at=now();
    if(!refundDue(state,at).length&&!feedbackPackageDue(state,at).length)return 0;
    return transact(s=>{
      const due=refundDue(s,at);
      for(const decision of due) {
        const previous=s.ledger.find(entry=>(entry.type==='like_refund'||entry.kind==='like_refund')&&(entry.refundedDecisionId===decision.id||entry.decisionId===decision.id));
        decision.refundedAt=previous?.createdAt||at;
        if(previous)continue;
        s.credits+=decision.charged;
        const text=`${decision.charged} kreditet visszatérítettünk, mert a kedvelésedre 14 napon belül nem érkezett válasz.`;
        s.ledger.unshift({id:uid('credit'),userId:s.userId,amount:decision.charged,type:'like_refund',kind:'like_refund',description:text,refundedDecisionId:decision.id,propertyId:decision.propertyId,searchId:decision.searchId,createdAt:at});
        s.notifications.unshift({id:uid('notification'),userId:s.userId,eventKey:'like_refund:'+decision.id,decisionId:decision.id,kind:'like_refund',amount:decision.charged,text,createdAt:at,readAt:null});
      }
      const packages=feedbackPackageDue(s,at);
      for(const pkg of packages){
        const previous=s.ledger.find(entry=>entry.refundedFeedbackPackageId===pkg.id);
        pkg.refundedAt=previous?.createdAt||at;pkg.refundedCredits=previous?.amount??Math.max(0,pkg.size-pkg.receivedCount);
        if(previous||pkg.refundedCredits===0)continue;
        const balance=s.credits+pkg.refundedCredits;
        if(!Number.isSafeInteger(balance))throw new Error('A kreditegyenleg nem növelhető tovább.');
        s.credits=balance;
        const text=`Visszakaptál ${pkg.refundedCredits} kreditet, mert a visszajelzés-csomagod 14 nap alatt nem telt be.`;
        s.ledger.unshift({id:uid('credit'),userId:s.userId,amount:pkg.refundedCredits,type:'feedback_refund',kind:'feedback_refund',description:text,refundedFeedbackPackageId:pkg.id,propertyId:pkg.propertyId,createdAt:at});
        s.notifications.unshift({id:uid('notification'),userId:s.userId,eventKey:'feedback_refund:'+pkg.id,feedbackPackageId:pkg.id,kind:'feedback_refund',amount:pkg.refundedCredits,text,createdAt:at,readAt:null});
      }
      return due.length+packages.length;
    });
  };
  const getMatch = (s,match) => {
    const property=s.properties.find(p=>p.id===match.propertyId);
    const search=s.searches.find(q=>q.id===match.searchId);
    if(!property||!search||![property.ownerId,search.ownerId].includes(s.userId))return null;
    const reciprocal=s.decisions.some(d=>d.propertyId===property.id&&d.searchId===search.id&&d.actorKind==='property'&&d.liked)&&s.decisions.some(d=>d.propertyId===property.id&&d.searchId===search.id&&d.actorKind==='search'&&d.liked);
    if(!reciprocal)return null;
    const partner=s.users.find(u=>u.id===(property.ownerId===s.userId?search.ownerId:property.ownerId));
    return {...clone(match),property:visibleEntity(property,s.users,undefined,s.userId),search:visibleEntity(search,s.users,undefined,s.userId),partner:clone(partner)};
  };
  const incomingNotificationItem=(s,property,search,kind,decision)=>{
    if(property.archived||search.archived||!ownersCanInteract(s,property,search))return null;
    const candidate=kind==='search'?property:search,prepared=prepareSearch(search,{perspective:kind==='property'?'seller':'buyer'}),specificity=searchSpecificity(prepared);
    const data=visibleEntity(candidate,s.users,specificity);
    const mine=s.decisions.find(item=>item.propertyId===property.id&&item.searchId===search.id&&item.actorKind===kind);
    const evaluation=evaluateDemoMatch(property,prepared),match=s.matches.find(item=>item.propertyId===property.id&&item.searchId===search.id);
    return {...data,kind:kind==='search'?'property':'search',pair:{propertyId:property.id,searchId:search.id},score:evaluation.score,isExact:evaluation.isExact,reasons:evaluation.reasons,matchDetails:evaluation.matchDetails,searchSpecificity:specificity,valueForMoney:valueForMoney(property),likedYou:true,likedAt:decision.createdAt,myDecision:mine?(mine.liked?'liked':'passed'):null,matchId:match&&getMatch(s,match)?match.id:null,compatible:evaluation.eligible};
  };
  const recommendationSnapshot = (s, options={}) => {
    const includeApproximate=options?.includeApproximate===true;
    const active=own(s,s.active?.kind,s.active?.id);
    const empty={items:[],hasApproximate:false,requiresApproximateConsent:false,stage:'empty'};
    if(!active||active.archived)return empty;
    const buyer=s.active.kind==='search';
    const candidates=buyer?s.properties:s.searches;
    const seen=new Set(),liked=new Set();
    for(const decision of s.decisions){
      if((buyer?decision.searchId:decision.propertyId)!==active.id)continue;
      const candidateId=buyer?decision.propertyId:decision.searchId;
      if(decision.actorKind===s.active.kind)seen.add(candidateId);
      else if(decision.liked)liked.add(candidateId);
    }
    const prepared=buyer?prepareSearch(active):null;
    const activeSpecificity=buyer?searchSpecificity(prepared):null;
    const activeValue=buyer?null:valueForMoney(active);
    const exact=[],approximate=[];
    for(const candidate of candidates){
      if(candidate.ownerId===s.userId||candidate.archived||seen.has(candidate.id))continue;
      const property=buyer?candidate:active,search=buyer?active:candidate;
      if(!ownersCanInteract(s,property,search))continue;
      const preparedCandidate=prepared||prepareSearch(search,{perspective:buyer?'buyer':'seller'});
      const evaluation=evaluateDemoMatch(property,preparedCandidate,{includeReasons:false});
      if(!evaluation.eligible)continue;
      const item={candidate,property,search,score:evaluation.score,isExact:evaluation.isExact,reasons:evaluation.reasons,matchDetails:evaluation.matchDetails,
        likedYou:liked.has(candidate.id),valueForMoney:activeValue??valueForMoney(property),
        searchSpecificity:activeSpecificity??searchSpecificity(preparedCandidate)};
      (evaluation.isExact?exact:approximate).push(item);
    }
    const selected=exact.length?exact:includeApproximate?approximate:[];
    selected.sort((a,b)=>(buyer?b.score-a.score||Number(b.likedYou)-Number(a.likedYou)
      :Number(b.likedYou)-Number(a.likedYou)||b.score-a.score)
      ||(buyer?b.valueForMoney-a.valueForMoney:b.searchSpecificity-a.searchSpecificity)
      ||String(a.property.id).localeCompare(String(b.property.id))||String(a.search.id).localeCompare(String(b.search.id)));
    return {items:selected.slice(0,50).map(item=>{
      const {candidate,property,search,...ranking}=item;
      const data=visibleEntity(candidate,s.users,ranking.searchSpecificity);
      if(!buyer){
        const person=s.users.find(user=>user.id===candidate.ownerId);
        data.buyerName ||= person?.name?.split(' ').at(-1)||'Érdeklődő';
        data.avatar=person?.avatar;
      }
      const explained=evaluateDemoMatch(property,prepared||prepareSearch(search,{perspective:buyer?'buyer':'seller'}));
      return {...data,...ranking,reasons:explained.reasons,matchDetails:explained.matchDetails,kind:buyer?'property':'search',pair:{propertyId:property.id,searchId:search.id}};
    }),hasApproximate:approximate.length>0,
      requiresApproximateConsent:!exact.length&&approximate.length>0&&!includeApproximate,
      stage:exact.length?'exact':includeApproximate&&approximate.length?'approximate':'empty'};
  };
  return {
    prepareRecommendations(options={}) {
      if(options.signal?.aborted)return false;
      if(geographyLoader===loadDemoMatchingGeography&&typeof window==='undefined')return false;
      const active=own(state,state.active?.kind,state.active?.id);
      if(!active||active.archived)return false;
      const buyer=state.active.kind==='search',targets=new Set(),activePrepared=buyer?prepareSearch(active):null;
      for(const candidate of buyer?state.properties:state.searches){
        const property=buyer?candidate:active,search=buyer?active:candidate;
        if(candidate.archived||candidate.ownerId===state.userId||!ownersCanInteract(state,property,search)||!demoCoordinates(property))continue;
        const prepared=activePrepared||prepareSearch(search,{perspective:'seller'});
        if(prepared.type&&prepared.type!==String(property.type??'').normalize('NFD').replace(/\p{M}/gu,'').trim().toUpperCase())continue;
        if(!prepared.hasNonStreetLocations||exactLocationMatch(property,prepared))continue;
        for(const id of demoAreaIds(prepared))targets.add(id);
      }
      if(!targets.size)return true;
      if(demoGeography&&[...targets].every(id=>demoGeography.geometries.has(id)))return true;
      return (async()=>{try{
        const result=await geographyLoader([...targets],options);
        if(options.signal?.aborted||!(result?.geometries instanceof Map)||typeof result.distance!=='function')return false;
        demoGeography=result;distanceCache.clear();
        return true;
      }catch{return false;}})(); // Missing demo assets never invent coordinates or make an outside location exact.
    },
    async findLocations(query,limit=8,{kind='search'}={}) {
      if(!['search','property'].includes(kind))throw new Error('Érvénytelen helyszínválasztó-típus.');
      if(kind==='property')return searchLocations(query,limit,{kind});
      if(!String(query??'').trim()||Number(limit)===0)return [];
      const streets=await findStreetCatalog();
      const selected=searchLocations(query,limit,{kind,streets});
      registerLocations(selected);
      return selected.map(location=>getLocation(location.id)).filter(Boolean);
    },
    async findStreets(query,locationId,limit=8) {
      if(!isPropertyLocation(getLocation(locationId))||!String(query??'').trim())return [];
      const selected=searchStreets(query,locationId,limit,await findStreetCatalog());
      return registerLocations(selected);
    },
    getState() {
      processRefunds();
      return clone({unreadNotificationCount:state.notifications.filter(item=>item.userId===state.userId&&!item.readAt).length,newNotificationCount:newNotificationCount(state),notificationLastVisitAt:state.users.find(user=>user.id===state.userId)?.notificationLastVisitAt??null,user:state.users.find(u=>u.id===state.userId),credits:state.credits,active:state.active,properties:state.properties.filter(p=>p.ownerId===state.userId).map(p=>visibleEntity(p,state.users,undefined,state.userId)),searches:state.searches.filter(q=>q.ownerId===state.userId).map(q=>visibleEntity(q,state.users,undefined,state.userId)),decisions:state.decisions.filter(d=>own(state,d.actorKind,d.actorId)).map(d=>({...d,property:visibleEntity(state.properties.find(p=>p.id===d.propertyId),state.users,undefined,state.userId),search:visibleEntity(state.searches.find(q=>q.id===d.searchId),state.users,undefined,state.userId)})),ledger:state.ledger,createdAt:state.createdAt,likeCost:state.active?.id?likeCost(state.users.find(user=>user.id===state.userId)?.accountType,state.active.kind):0,reportedOwnerIds:[...new Set(state.reports.filter(report=>report.reporterId===state.userId).map(report=>report.reportedUserId))],reportedEntities:state.reports.filter(report=>report.reporterId===state.userId&&['property','search'].includes(report.entityKind)&&typeof report.entityId==='string').map(({entityKind,entityId,reason})=>({entityKind,entityId,reason}))});
    },
    recommendations(options={}) {
      processRefunds();
      return recommendationSnapshot(state,options);
    },
    feed(options={}) {
      processRefunds();
      return recommendationSnapshot(state,options).items;
    },
    getListingContext(kind,key) {
      processRefunds();
      const active=own(state,state.active?.kind,state.active?.id),activeKind=state.active?.kind;
      const candidate=(kind==='property'?state.properties:kind==='search'?state.searches:[]).find(entity=>!entity.archived&&demoSourceKey(kind,entity.id)===key);
      const empty={active:null,item:null,myDecision:null,matchId:null,compatible:false,isExact:false,compatibilityScore:0,likeCost:0,credits:state.credits,canDecide:false,requiresApproximateConsent:false,hasUnseenExact:false,unavailableReason:null};
      if(!candidate)return empty;
      if(candidate.ownerId===state.userId)return {...empty,unavailableReason:'own_listing'};
      if(!active||active.archived)return {...empty,unavailableReason:'no_active_profile'};
      if(activeKind===kind)return {...empty,unavailableReason:'opposite_profile_required'};
      const property=kind==='property'?candidate:active,search=kind==='search'?candidate:active;
      if(!ownersCanInteract(state,property,search))return {...empty,unavailableReason:'agent_pair_forbidden'};
      const prepared=prepareSearch(search,{perspective:activeKind==='property'?'seller':'buyer'}),evaluation=evaluateDemoMatch(property,prepared);
      const mine=state.decisions.find(decision=>decision.propertyId===property.id&&decision.searchId===search.id&&decision.actorKind===activeKind);
      const other=state.decisions.find(decision=>decision.propertyId===property.id&&decision.searchId===search.id&&decision.actorKind!==activeKind&&decision.liked);
      const match=state.matches.find(item=>item.propertyId===property.id&&item.searchId===search.id),cost=likeCost(state.users.find(user=>user.id===state.userId)?.accountType,activeKind);
      const item={...visibleEntity(candidate,state.users),kind,pair:{propertyId:property.id,searchId:search.id},score:evaluation.score,isExact:evaluation.isExact,compatible:evaluation.eligible,likedYou:!!other,searchSpecificity:searchSpecificity(prepared),reasons:evaluation.reasons,matchDetails:evaluation.matchDetails};
      // Only the owner's active search is copied here; the candidate above is already public-price sanitized.
      const activeView={...visibleEntity(active,state.users,undefined,state.userId),kind:activeKind};
      return {...empty,active:activeView,item,myDecision:mine?(mine.liked?'liked':'passed'):null,matchId:match&&getMatch(state,match)?match.id:null,compatible:evaluation.eligible,isExact:evaluation.isExact,compatibilityScore:evaluation.score,likeCost:cost,canDecide:evaluation.eligible&&!mine&&!match};
    },
    getListingMap(kind,key) {
      const detail=demoPublicListing(kind,key),candidate=(kind==='property'?state.properties:state.searches).find(entity=>demoSourceKey(kind,entity.id)===key);
      if(kind==='search'){
        const ids=(candidate?.locationIds||detail.prefill?.locationIds||[]).filter(id=>getLocation(id)&&!isStreetId(id));
        return {kind,available:ids.length>0,locationIds:ids,externalUrl:null};
      }
      const listing=detail.listing;
      if(listing.hideStreet===false&&listing.hideHouseNumber===false&&listing.street&&listing.houseNumber){
        const address=[listing.city,listing.district,listing.street,listing.houseNumber,'Magyarország'].filter(Boolean).join(', ');
        return {kind,available:true,locationIds:[],externalUrl:'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(address)};
      }
      const id=candidate?.neighborhoodIds?.find(id=>getLocation(id))||detail.prefill?.locationIds?.find(id=>getLocation(id))||candidate?.locationId;
      return {kind,available:!!id,locationIds:id?[id]:[],externalUrl:null};
    },
    getListingProfiles(kind,key,options={}) {
      const page=normalizeListingProfilePagination(options),opposite=kind==='property'?'search':'property';
      const candidate=(kind==='property'?state.properties:kind==='search'?state.searches:[]).find(entity=>!entity.archived&&demoSourceKey(kind,entity.id)===key);
      if(!candidate)throw new Error('A hirdetés már nem érhető el.');
      const empty={kind:opposite,items:[],total:0,...page,hasMore:false,unavailableReason:null};
      if(candidate.ownerId===state.userId)return {...empty,unavailableReason:'own_listing'};
      const viewer=state.users.find(user=>user.id===state.userId),owner=state.users.find(user=>user.id===candidate.ownerId);
      if(!canInteract(viewer?.accountType,owner?.accountType))return {...empty,unavailableReason:'agent_pair_forbidden'};
      const owned=(opposite==='property'?state.properties:state.searches).filter(entity=>entity.ownerId===state.userId&&!entity.archived)
        .sort((a,b)=>Number(state.active?.kind===opposite&&b.id===state.active.id)-Number(state.active?.kind===opposite&&a.id===state.active.id)||String(a.title).localeCompare(String(b.title),'hu')||String(a.id).localeCompare(String(b.id)));
      const items=owned.slice(page.offset,page.offset+page.limit).map(entity=>{
        const property=kind==='property'?candidate:entity,search=kind==='search'?candidate:entity,evaluation=evaluateDemoMatch(property,prepareSearch(search,{perspective:opposite==='property'?'seller':'buyer'}));
        const view=visibleEntity(entity,state.users,undefined,state.userId),profile={kind:opposite,id:view.id,title:view.title,type:view.type,locations:(opposite==='search'?view.locations:[view.location]).filter(Boolean).map(place=>place.label),locationIds:opposite==='search'?view.locationIds:[view.locationId],
          ...(opposite==='search'?{minPrice:view.minPrice,maxPrice:view.maxPrice,minArea:view.minArea,maxArea:view.maxArea,minRooms:view.minRooms,maxRooms:view.maxRooms}:{price:view.price})};
        return {profile,score:evaluation.eligible?evaluation.score:0,isExact:evaluation.eligible&&evaluation.isExact,compatible:evaluation.eligible,isActive:state.active?.kind===opposite&&state.active.id===entity.id};
      });
      return {...empty,items,total:owned.length,hasMore:page.offset+items.length<owned.length};
    },
    incomingLikes(options={}) {
      const {offset,limit}=normalizeIncomingPagination(options);
      processRefunds();
      const active=own(state,state.active?.kind,state.active?.id);
      const empty={active:null,items:[],total:0,offset,limit,hasMore:false,likeCost:0};
      if(!active||active.archived)return empty;
      const activeKind=state.active.kind;
      const preparedActive=activeKind==='search'?prepareSearch(active):null;
      const items=state.decisions.filter(decision=>decision.liked&&decision.actorKind===(activeKind==='property'?'search':'property')&&(activeKind==='property'?decision.propertyId===active.id:decision.searchId===active.id)).map(decision=>{
        const property=state.properties.find(item=>item.id===decision.propertyId),search=state.searches.find(item=>item.id===decision.searchId);
        if(!property||!search||property.archived||search.archived||property.ownerId===search.ownerId||!ownersCanInteract(state,property,search))return null;
        const candidate=activeKind==='search'?property:search;
        if(candidate.ownerId===state.userId)return null;
        const mine=state.decisions.find(item=>item.propertyId===property.id&&item.searchId===search.id&&item.actorKind===activeKind);
        if(mine||state.matches.some(item=>item.propertyId===property.id&&item.searchId===search.id))return null;
        const prepared=preparedActive||prepareSearch(search,{perspective:activeKind==='property'?'seller':'buyer'}),specificity=searchSpecificity(prepared);
        const data=visibleEntity(candidate,state.users,specificity);
        const evaluation=evaluateDemoMatch(property,prepared),compatible=evaluation.eligible;
        return {...data,kind:activeKind==='search'?'property':'search',pair:{propertyId:property.id,searchId:search.id},
          score:evaluation.score,isExact:evaluation.isExact,reasons:evaluation.reasons,matchDetails:evaluation.matchDetails,searchSpecificity:specificity,valueForMoney:valueForMoney(property),
          likedYou:true,likedAt:decision.createdAt,myDecision:null,matchId:null,compatible,_decisionId:String(decision.id)};
      }).filter(Boolean).sort((a,b)=>String(a.likedAt)===String(b.likedAt)?(a._decisionId===b._decisionId?0:a._decisionId>b._decisionId?-1:1):(String(a.likedAt)>String(b.likedAt)?-1:1));
      const total=items.length;
      return {active:{kind:activeKind,id:active.id},items:items.slice(offset,offset+limit).map(({_decisionId,...item})=>item),total,offset,limit,hasMore:offset+limit<total,likeCost:likeCost(state.users.find(user=>user.id===state.userId)?.accountType,activeKind)};
    },
    decide(item,liked,options={}) {
      processRefunds();
      if(typeof liked!=='boolean')throw new Error('Érvénytelen döntés.');
      const pair=item?.pair;
      if(!pair?.propertyId||!pair?.searchId)throw new Error('Érvénytelen ajánlás.');
      return transact(s=>{
        const active=own(s,s.active.kind,s.active.id);
        const property=s.properties.find(p=>p.id===pair.propertyId),search=s.searches.find(q=>q.id===pair.searchId);
        if(!active||active.archived||!property||!search||property.archived||search.archived
          ||(s.active.kind==='property'?property.id:search.id)!==active.id||!ownersCanInteract(s,property,search))throw new Error('Ez az ajánlás már nem érhető el az aktív profilodhoz.');
        const counterpartKind=s.active.kind==='property'?'search':'property',counterpart=counterpartKind==='property'?property:search;
        const directListing=options.listingKey!=null;
        if(directListing&&options.listingKey!==demoSourceKey(counterpartKind,counterpart.id))throw new Error('Érvénytelen hirdetésazonosító.');
        const evaluation=evaluateDemoMatch(property,prepareSearch(search,{perspective:s.active.kind==='property'?'seller':'buyer'}));
        if(!evaluation.eligible)throw new Error('Ez az ajánlás már nem érhető el az aktív profilodhoz.');
        if(s.decisions.some(d=>d.propertyId===pair.propertyId&&d.searchId===pair.searchId&&d.actorKind===s.active.kind))throw new Error('Erről az ajánlásról már döntöttél.');
        if(!evaluation.isExact&&!directListing&&(options?.allowApproximate!==true||recommendationSnapshot(s).items.length))
          throw new Error('Előbb nézd végig a tökéletes egyezéseket, majd engedélyezd a részleges találatokat.');
        const charged=liked?likeCost(s.users.find(user=>user.id===s.userId)?.accountType,s.active.kind):0;
        if(s.credits<charged)throw new Error(`Nincs elegendő kredited. A kedveléshez ${charged} kredit szükséges.`);
        s.credits-=charged;
        if(charged)s.ledger.unshift({id:uid('credit'),userId:s.userId,amount:-charged,type:s.active.kind==='property'?'seller_like':'agent_search_like',description:s.active.kind==='property'?`Ingatlan ajánlása: ${search.title}`:`Közvetítői keresés kedvelése: ${property.title}`,propertyId:property.id,searchId:search.id,createdAt:now()});
        const decision={id:uid('decision'),actorKind:s.active.kind,actorId:active.id,...pair,liked,charged,createdAt:now()};
        s.decisions.push(decision);
        const offeredFeedback=offerFeedback(s,decision,property);
        let match=null;
        if(liked&&s.decisions.some(d=>d.propertyId===pair.propertyId&&d.searchId===pair.searchId&&d.actorKind!==s.active.kind&&d.liked)) {
          let record=s.matches.find(m=>m.propertyId===pair.propertyId&&m.searchId===pair.searchId);
          if(!record){record={id:uid('match'),...pair,createdAt:now(),unread:0,messages:[]};s.matches.unshift(record);}
          match=getMatch(s,record);
        }
        return {match,charged,feedbackPrompt:offeredFeedback};
      });
    },
    getPropertyInsights(propertyId,options={}) {
      const {offset,limit}=normalizeIncomingPagination(options);processRefunds();
      const property=own(state,'property',propertyId);
      if(!property)throw new Error('Az ingatlan nem található.');
      const searchOwner=id=>state.searches.find(item=>item.id===id)?.ownerId;
      const viewers=new Set(state.propertyImpressions.filter(item=>item.propertyId===propertyId).map(item=>item.viewerUserId));
      const buyerLikes=new Set(state.decisions.filter(item=>item.propertyId===propertyId&&item.actorKind==='search'&&item.liked)
        .map(item=>searchOwner(item.searchId)).filter(id=>id&&id!==property.ownerId)).size;
      const sellerLikes=new Set(state.decisions.filter(item=>item.propertyId===propertyId&&item.actorKind==='property'&&item.liked).map(item=>item.searchId)).size;
      const matchedViewers=new Set(state.matches.filter(item=>item.propertyId===propertyId).map(item=>searchOwner(item.searchId)).filter(id=>viewers.has(id))).size;
      const answers=state.feedbackInvitations.filter(item=>item.propertyId===propertyId&&item.answeredAt&&item.reason&&item.reason!=='decline')
        .sort((a,b)=>String(b.answeredAt).localeCompare(String(a.answeredAt))||String(b.id).localeCompare(String(a.id)));
      const label=reason=>FEEDBACK_OPTIONS.find(option=>option.value===reason)?.label||'';
      const at=now();
      return clone({propertyId,stats:{uniqueViewers:viewers.size,buyerLikes,sellerLikes,matchedViewers,
        matchRate:viewers.size?Math.round(matchedViewers/viewers.size*10000)/100:0},
        feedback:{total:answers.length,items:answers.slice(offset,offset+limit).map(item=>({id:item.id,reason:item.reason,label:label(item.reason),createdAt:item.answeredAt})),
          reasonCounts:FEEDBACK_OPTIONS.filter(option=>option.value!=='decline').map(option=>({reason:option.value,label:option.label,count:answers.filter(item=>item.reason===option.value).length})),
          offset,limit,hasMore:offset+limit<answers.length},
        activePackage:feedbackPackageView(activeFeedbackPackage(state,propertyId,at),at),
        packages:state.feedbackPackages.filter(pkg=>pkg.propertyId===propertyId).sort((a,b)=>String(b.createdAt).localeCompare(String(a.createdAt))||String(b.id).localeCompare(String(a.id))).slice(0,20).map(pkg=>feedbackPackageView(pkg,at)),
        packageSizes:[...FEEDBACK_PACKAGE_SIZES],durationDays:FEEDBACK_DURATION_DAYS,creditCostPerFeedback:1});
    },
    buyFeedbackPackage(propertyId,size,requestId) {
      if(!FEEDBACK_PACKAGE_SIZES.includes(size))throw new Error('Válassz 10, 20 vagy 50 visszajelzést tartalmazó csomagot.');
      if(typeof requestId!=='string'||!/^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i.test(requestId)||/^0{8}-(?:0{4}-){3}0{12}$/.test(requestId))throw new Error('Érvényes vásárlási azonosító szükséges.');
      requestId=requestId.toLowerCase();processRefunds();
      return transact(s=>{
        const property=own(s,'property',propertyId);
        if(!property)throw new Error('Az ingatlan nem található.');
        const previous=s.feedbackPackages.find(pkg=>pkg.ownerId===s.userId&&pkg.requestId===requestId);
        if(previous){
          if(previous.propertyId!==propertyId||previous.size!==size)throw new Error('Ezt a vásárlási azonosítót már másik csomaghoz használtad.');
          return {package:feedbackPackageView(previous,now()),charged:0,credits:s.credits};
        }
        if(property.archived)throw new Error('Archivált ingatlanhoz nem vásárolhatsz új visszajelzés-csomagot.');
        if(activeFeedbackPackage(s,propertyId,now()))throw new Error('Ehhez az ingatlanhoz már van aktív visszajelzés-csomag.');
        if(s.credits<size)throw new Error(`Nincs elegendő kredited. A csomag ára ${size} kredit.`);
        const createdAt=now(),pkg={id:uid('feedback-package'),propertyId,ownerId:s.userId,requestId,size,receivedCount:0,enabled:true,
          createdAt,expiresAt:new Date(storedInstant(createdAt)+FEEDBACK_DURATION_DAYS*86400000).toISOString(),refundedAt:null,refundedCredits:0};
        s.credits-=size;s.feedbackPackages.push(pkg);
        s.ledger.unshift({id:uid('credit'),userId:s.userId,amount:-size,type:'feedback_package',kind:'feedback_package',description:`${size} visszajelzést tartalmazó csomag: ${property.title}`,feedbackPackageId:pkg.id,propertyId,createdAt});
        return {package:feedbackPackageView(pkg,createdAt),charged:size,credits:s.credits};
      });
    },
    recordImpression(propertyId,searchRequestId) {
      const property=state.properties.find(item=>item.id===propertyId),search=own(state,'search',searchRequestId);
      if(state.active?.kind!=='search'||state.active.id!==searchRequestId||!search||!property||!ownersCanInteract(state,property,search)
        ||!evaluateDemoMatch(property,prepareSearch(search),{includeReasons:false}).eligible)throw new Error('Ez az ingatlan nem érhető el az aktív keresésedhez.');
      if(state.propertyImpressions.some(item=>item.propertyId===propertyId&&item.viewerUserId===state.userId))return {recorded:false};
      return transact(s=>{s.propertyImpressions.push({id:uid('impression'),propertyId,viewerUserId:s.userId,searchRequestId,createdAt:now()});return {recorded:true};});
    },
    pendingFeedback() {
      processRefunds();return clone(feedbackPrompt(state,pendingFeedbackInvitation(state,now())));
    },
    answerFeedback(invitationId,reason) {
      if(!FEEDBACK_OPTIONS.some(option=>option.value===reason))throw new Error('Válassz egy visszajelzési lehetőséget.');processRefunds();
      return transact(s=>{
        const invitation=s.feedbackInvitations.find(item=>item.id===invitationId&&item.buyerId===s.userId);
        if(!invitation)throw new Error('A visszajelzés-kérés nem található.');
        if(invitation.answeredAt)return {accepted:invitation.reason!=='decline',alreadyAnswered:true};
        if(!liveFeedbackInvitation(s,invitation,now()))return {accepted:false,alreadyAnswered:false};
        const pkg=s.feedbackPackages.find(item=>item.id===invitation.packageId);
        invitation.answeredAt=now();invitation.reason=reason;
        if(reason!=='decline')pkg.receivedCount++;
        return {accepted:reason!=='decline',alreadyAnswered:false};
      });
    },
    notifications(options={}) {
      const {offset,limit}=normalizeIncomingPagination(options);
      const visitThrough=now();
      processRefunds();
      const items=state.notifications.filter(item=>item.userId===state.userId).sort((a,b)=>String(b.createdAt).localeCompare(String(a.createdAt))||String(b.id).localeCompare(String(a.id)));
      return clone({items:items.slice(offset,offset+limit).map(publicNotification),total:items.length,unreadCount:items.filter(item=>!item.readAt).length,newCount:newNotificationCount(state),visitThrough,visitedAt:state.users.find(user=>user.id===state.userId)?.notificationLastVisitAt??null,offset,limit,hasMore:offset+limit<items.length});
    },
    markNotificationsVisited({through}={}) {
      if(typeof through!=='string'||!Number.isFinite(Date.parse(through)))throw new Error('Érvénytelen értesítési időpont.');
      let savedVisit;
      try{savedVisit=JSON.parse(storage?.getItem(STORAGE_KEY)||'null')?.users?.find(user=>user.id===state.userId)?.notificationLastVisitAt;}catch{}
      processRefunds();
      return transact(s=>{
        const owner=s.users.find(user=>user.id===s.userId),current=Date.parse(owner.notificationLastVisitAt||''),persisted=Date.parse(savedVisit||''),cutoff=Math.max(Math.min(Date.parse(through),Date.parse(now())),Number.isFinite(current)?current:-Infinity,Number.isFinite(persisted)?persisted:-Infinity);
        owner.notificationLastVisitAt=new Date(cutoff).toISOString();
        return {newCount:newNotificationCount(s),visitedAt:owner.notificationLastVisitAt};
      });
    },
    markNotificationRead(id) {
      processRefunds();
      return transact(s=>{
        const item=s.notifications.find(notification=>notification.id===id&&notification.userId===s.userId);
        if(!item)throw new Error('Az értesítés nem található.');
        item.readAt ||= now();
        return {...publicNotification(item),unreadCount:s.notifications.filter(notification=>notification.userId===s.userId&&!notification.readAt).length};
      });
    },
    getNotificationContext(id) {
      const notification=state.notifications.find(item=>item.id===id&&item.userId===state.userId);
      if(!notification)throw new Error('Az értesítés nem található.');
      const target=safeNotificationTarget(notification.target,notification.kind);
      const result={notification:publicNotification(notification),available:false,target,canActivate:false,item:null};
      if(!target)return clone(result);
      if(target.page==='credits')return clone({...result,available:true});
      if(!['property','search'].includes(target.entityKind))return clone(result);
      const entity=own(state,target.entityKind,target.entityId);
      if(!entity)return clone(result);
      const canActivate=!entity.archived;
      if(target.page==='messages'){
        const record=state.matches.find(item=>item.id===target.matchId&&item.propertyId===target.propertyId&&item.searchId===target.searchRequestId);
        const belongs=target.entityKind==='property'?target.entityId===target.propertyId:target.entityId===target.searchRequestId;
        const available=!!record&&belongs&&!!getMatch(state,record);
        return clone({...result,available,canActivate:available&&canActivate});
      }
      if(!canActivate)return clone(result);
      if(target.page==='insights')return clone({...result,available:target.entityKind==='property'&&target.propertyId===entity.id,canActivate:target.entityKind==='property'&&target.propertyId===entity.id});
      const property=state.properties.find(item=>item.id===target.propertyId),search=state.searches.find(item=>item.id===target.searchRequestId);
      const belongs=target.entityKind==='property'?property?.id===entity.id:search?.id===entity.id;
      const decision=property&&search&&state.decisions.find(item=>item.propertyId===property.id&&item.searchId===search.id&&item.liked&&item.actorKind!==target.entityKind);
      if(!belongs||!decision)return clone(result);
      const item=incomingNotificationItem(state,property,search,target.entityKind,decision);
      return clone({...result,available:!!item,canActivate:!!item,item});
    },

    activate(kind,id) {
      if(!['property','search'].includes(kind))throw new Error('Érvénytelen profiltípus.');
      return transact(s=>{const entity=own(s,kind,id);if(!entity||entity.archived)throw new Error('Ez a profil nem aktiválható.');s.active={kind,id};return s.active;});
    },
    saveEntity(kind,data,id,{creationRequestId}={}) {
      if(!['property','search'].includes(kind))throw new Error('Érvénytelen profiltípus.');
      if(creationRequestId!=null){
        if(id||typeof creationRequestId!=='string'||!/^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i.test(creationRequestId)||/^0{8}-(?:0{4}-){3}0{12}$/.test(creationRequestId))throw new Error('Érvénytelen létrehozási azonosító.');
        creationRequestId=creationRequestId.toLowerCase();
        // A second tab must see the first tab's receipt before attempting the same creation.
        try{const latest=JSON.parse(storage?.getItem(STORAGE_KEY)||'null');if(latest?.version===3&&latest.userId===state.userId&&Array.isArray(latest.properties)&&Array.isArray(latest.searches)&&Array.isArray(latest.users))state=migrateLocations(latest);}catch{}
      }
      const signature=creationRequestId?stablePayload(sanitizeDraftData(data,kind)):null;
      return transact(s=>{
        if(creationRequestId){
          s.creationRequests ||= [];
          const previous=s.creationRequests.find(receipt=>receipt.ownerId===s.userId&&receipt.requestId===creationRequestId);
          if(previous){
            if(previous.kind!==kind||previous.signature!==signature)throw new Error('Ezt a létrehozási azonosítót már másik kitöltéshez használtad.');
            const saved=own(s,kind,previous.entityId);if(!saved)throw new Error('A korábban létrehozott profil már nem érhető el.');
            return visibleEntity(saved,s.users,undefined,s.userId);
          }
        }
        const existing=id?own(s,kind,id):null;
        assertDescriptionContactFree(data.description ?? existing?.description);
        if(id&&!existing)throw new Error('Ez a profil nem szerkeszthető.');
        const title=String(data.title??existing?.title??'').trim();
        if(title.length<3||title.length>150)throw new Error('Adj meg egy 3–150 karakteres nevet.');
        const incoming=clone(data);delete incoming.ownerAccountType;delete incoming.ownerFirstName;
        for(const field of ['searchSpecificity','valueForMoney','isExact','score'])delete incoming[field];
        if(kind==='property'){
          for(const field of [...privatePropertyFields,'neighborhoodIds','neighborhood'])delete incoming[field];
          const countsSupplied=[incoming.wholeRooms,incoming.halfRooms].some(count=>count!=null&&String(count).trim()!=='');
          if(countsSupplied){
            if(!Object.hasOwn(incoming,'wholeRooms'))incoming.wholeRooms=0;
            if(!Object.hasOwn(incoming,'halfRooms'))incoming.halfRooms=0;
            if(!Object.hasOwn(incoming,'rooms'))incoming.rooms=0;
          }else if(Object.hasOwn(incoming,'rooms')){incoming.wholeRooms=null;incoming.halfRooms=null;}
          if(!Object.hasOwn(incoming,'parkingTypes')&&Object.hasOwn(incoming,'parkingType'))incoming.parkingTypes=null;
        }
        const entity=withLocations({...existing,...incoming,id:existing?.id||uid(kind==='property'?'p':'s'),ownerId:s.userId,title,type:String(data.type??existing?.type??'Lakás'),archived:existing?.archived??false,createdAt:existing?.createdAt||now()},kind,true);
        Object.assign(entity,kind==='property'?normalizePropertyAttributes(entity,{strict:true,previous:existing}):normalizeSearchAttributes(entity,{strict:true}));
        if(kind==='property'){
          for(const field of ['price','area','rooms']){entity[field]=numeric(entity[field],NaN);if(!Number.isFinite(entity[field])||entity[field]<=0||(field==='rooms'&&entity[field]>1000))throw new Error('Az ár, az alapterület és a szobaszám legyen pozitív szám.');}
          entity.district=String(entity.district||'').trim();entity.neighborhood=String(entity.neighborhood||'');
          if(entity.type==='Ház'&&(!Number.isFinite(entity.lotArea)||entity.lotArea<=0||entity.lotArea>10000000))throw new Error('A telekméret pozitív szám legyen.');
          entity.images=Array.isArray(entity.images)?entity.images.filter(u=>typeof u==='string'&&/^(https?:\/\/|\/assets\/|data:image\/(png|jpe?g|webp|gif);base64,)/i.test(u)):[];
          if(entity.type==='Ház'){entity.floor=null;entity.balcony=null;entity.elevator=false;}
          else{entity.elevator=!!entity.elevator;}
          const street=String(data.street??data.addressDetails?.street??existing?.addressDetails?.street??'').trim();
          const houseNumber=String(data.houseNumber??data.addressDetails?.houseNumber??existing?.addressDetails?.houseNumber??'').trim();
          const postalCode=String(data.postalCode??data.addressDetails?.postalCode??existing?.addressDetails?.postalCode??'').trim();
          if(!street||!houseNumber)throw new Error('Add meg az ingatlan utcáját és házszámát.');
          if(street.length>180||/\p{Cc}/u.test(street)||!/^\d[\p{L}\d./ -]{0,31}$/u.test(houseNumber)||postalCode&&!/^\d{4}$/.test(postalCode))throw new Error('Adj meg érvényes utcát, házszámot és négyjegyű irányítószámot.');
          const unchanged=existing?.locationId===entity.locationId&&existing?.addressDetails?.street===street&&existing?.addressDetails?.houseNumber===houseNumber&&String(existing?.addressDetails?.postalCode||'')===postalCode;
          const selectedId=data.streetId??data.addressDetails?.streetId;
          const selected=getLocation(selectedId);
          const resolved=selectedId?resolveStreetLocation(street,entity.location,postalCode,selected?[selected]:[]):resolveStreetLocation(street,entity.location,postalCode);
          const previousStreetId=existing?.addressDetails?.streetId;
          const streetId=resolved?.id??(unchanged&&isStreetId(previousStreetId)&&!getLocation(previousStreetId)
            &&(selectedId==null||selectedId===previousStreetId)?previousStreetId:null);
          if(resolved?.district&&!entity.location.district){
            const district=resolveLegacyLocations({city:resolved.city,district:resolved.district})[0];
            entity.locationId=district.id;entity.location=clone(district);entity.district=district.district;
          }
          // Demo edits never pretend to perform Google geocoding. New addresses have no verified membership.
          entity.addressDetails=unchanged?clone(existing.addressDetails):{street,houseNumber,postalCode,latitude:null,longitude:null,geocodedAt:null,provider:'',quality:'',geocodingStatus:'demo-unverified'};
          entity.addressDetails.streetId=streetId;
          entity.neighborhoodIds=unchanged?clone(existing.neighborhoodIds||[]):[];
          entity.neighborhood=unchanged?String(existing.neighborhood||''):'';
          for(const field of privatePropertyFields)if(field!=='addressDetails')delete entity[field];
          entity.streetId=streetId;
        }else{
          for(const [min,max] of [['minPrice','maxPrice'],['minArea','maxArea'],['minRooms','maxRooms']]){entity[min]=numeric(entity[min],null);entity[max]=numeric(entity[max],null);if((entity[min]!=null&&(!Number.isFinite(entity[min])||entity[min]<0))||(entity[max]!=null&&(!Number.isFinite(entity[max])||entity[max]<=0))||(entity[min]!=null&&entity[max]!=null&&entity[max]<entity[min]))throw new Error('A minimum érték nem lehet nagyobb a maximumnál; a korlátok érvényes számok legyenek.');}
          entity.publicMaxPrice=numeric(entity.publicMaxPrice,null);
          if(entity.publicMaxPrice!=null&&(!Number.isFinite(entity.publicMaxPrice)||entity.publicMaxPrice<=0||entity.publicMaxPrice>1000000||entity.maxPrice!=null&&entity.publicMaxPrice>entity.maxPrice||entity.minPrice!=null&&entity.publicMaxPrice<entity.minPrice))throw new Error('A publikus maximumár a minimumár és a saját maximumár közé essen.');
          entity.balcony=!!entity.balcony;entity.elevator=!!entity.elevator;entity.moveIn=String(entity.moveIn??'').trim();
        }
        const list=kind==='property'?s.properties:s.searches;
        if(existing)list[list.findIndex(e=>e.id===id)]=entity;else list.push(entity);
        if(creationRequestId)s.creationRequests.push({ownerId:s.userId,requestId:creationRequestId,kind,entityId:entity.id,signature});
        return visibleEntity(entity,s.users,undefined,s.userId);
      });
    },
    reportAccount(entityKind,entityId,reason) {
      if(!['property','search'].includes(entityKind))throw new Error('Érvénytelen profiltípus.');
      reason=normalizeReportReason(reason);
      return transact(s=>{
        const entity=(entityKind==='property'?s.properties:s.searches).find(item=>item.id===entityId&&!item.archived);
        if(!entity)throw new Error('A jelenteni kívánt profil nem érhető el.');
        if(entity.ownerId===s.userId)throw new Error('A saját profilodat nem jelentheted.');
        const owner=s.users.find(user=>user.id===entity.ownerId);
        if(!owner)throw new Error('A jelenteni kívánt fiók nem található.');
        if(reason==='suspected_agent'&&normalizeAccountType(owner.accountType)!=='private')throw new Error('Csak magánszemélyként megjelölt fiókot jelenthetsz emiatt.');
        const previous=s.reports.find(report=>report.reporterId===s.userId&&report.entityKind===entityKind&&report.entityId===entityId&&report.reason===reason);
        if(previous)return {id:previous.id,reported:true,reportedOwnerId:owner.id,alreadyReported:true};
        const report={id:uid('report'),reporterId:s.userId,reportedUserId:owner.id,entityKind,entityId,reason,createdAt:now()};
        s.reports.push(report);
        return {id:report.id,reported:true,reportedOwnerId:owner.id,alreadyReported:false};
      });
    },
    deleteEntity(kind,id) {
      return transact(s=>{const entity=own(s,kind,id);if(!entity)throw new Error('A profil nem található.');entity.archived=true;if(s.active.kind===kind&&s.active.id===id){const next=s.searches.find(e=>e.ownerId===s.userId&&!e.archived)||s.properties.find(e=>e.ownerId===s.userId&&!e.archived);s.active=next?{kind:s.searches.includes(next)?'search':'property',id:next.id}:{kind:'search',id:null};}return true;});
    },
    updateProfile(data) {
      return transact(s=>{const user=s.users.find(u=>u.id===s.userId);const name=String(data.name??user.name).trim(),email=String(data.email??user.email).trim(),phone=String(data.phone??user.phone).trim();if(name.length<3)throw new Error('Add meg a teljes neved.');if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))throw new Error('Érvényes e-mail-címet adj meg.');if(!phone)throw new Error('A telefonszám megadása kötelező.');if(!/^[+\d ()-]{7,25}$/.test(phone))throw new Error('Érvényes telefonszámot adj meg.');Object.assign(user,{name,email,phone,avatar:name.split(/\s+/).map(n=>n[0]).slice(0,2).join('').toUpperCase()});return user;});
    },
    buyDemoCredits(amount) {
      amount=Number(amount);if(!Number.isInteger(amount)||amount<1||amount>10000)throw new Error('Érvénytelen kreditmennyiség.');
      return transact(s=>{s.credits+=amount;s.ledger.unshift({id:uid('credit'),userId:s.userId,amount,type:'demo_topup',description:'Demófeltöltés – fizetés nem történt',createdAt:now()});return {credits:s.credits,demo:true};});
    },
    matches() {processRefunds();return state.matches.map(m=>getMatch(state,m)).filter(Boolean).sort((a,b)=>b.createdAt.localeCompare(a.createdAt));},
    sendMessage(matchId,text) {
      text=String(text||'').trim();if(!text||text.length>4000)throw new Error('Az üzenet 1–4000 karakter hosszú lehet.');
      return transact(s=>{const record=s.matches.find(m=>m.id===matchId);if(!record||!getMatch(s,record))throw new Error('Csak kölcsönös találat után küldhetsz üzenetet.');const message={id:uid('message'),senderId:s.userId,text,createdAt:now()};record.messages.push(message);record.unread=0;return message;});
    },
    markRead(matchId){return transact(s=>{const record=s.matches.find(m=>m.id===matchId);if(!record||!getMatch(s,record))throw new Error('A találat nem érhető el.');record.unread=0;return true;});},
    reset(){const next=migrateLocations(seed(now));try{storage?.setItem(STORAGE_KEY,JSON.stringify(next));}catch{throw new Error('A demó nem állítható vissza.');}state=next;return this.getState();}
  };
}
export const model=createModel();
