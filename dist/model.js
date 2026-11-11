import { getLocation, resolveLegacyLocations, isPropertyLocation } from './locations.js';
import {normalizePropertyAttributes, normalizeSearchAttributes} from './attributes.js';
import {normalizeAccountType,likeCost,canInteract,normalizeReportReason,normalizeIncomingPagination} from './accounts.js';
import {prepareSearch,evaluateMatch,valueForMoney,searchSpecificity} from './matching.js';
import {publicFirstName,publicTitle} from './public-profile.js';
import {FEEDBACK_OPTIONS,FEEDBACK_QUESTION,FEEDBACK_PACKAGE_SIZES,FEEDBACK_DURATION_DAYS,FEEDBACK_PROMPT_SPACING,FEEDBACK_INVITATION_MINUTES,feedbackTitle} from './feedback.js';

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
    locations=ids.map(getLocation).filter(Boolean);
    if(strict&&(!ids.length||ids.length>50||locations.length!==ids.length))throw locationError();
    if(!strict){
      if(!Array.isArray(entity.locationIds)||locations.length!==ids.length){invalidSearchIds=entity.locationIds;locations=[];}
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
  state.properties = state.properties.map(entity=>normalizePropertyAttributes(withLocations(entity, 'property')));
  state.searches = state.searches.map(entity=>normalizeSearchAttributes(withLocations(entity, 'search')));
  return state;
}
const visibleEntity = (entity,users,specificity) => {
  const result = clone(entity);
  delete result.email; delete result.phone;
  const owner=users?.find(user=>user.id===entity.ownerId);
  result.ownerAccountType=normalizeAccountType(owner?.accountType);
  result.ownerFirstName=publicFirstName(owner?.name);
  if(Array.isArray(entity.locationIds))result.searchSpecificity=specificity??searchSpecificity(entity);
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
  const property = (id,ownerId,title,district,neighborhood,price,area,rooms,image,extras={}) => ({id,ownerId,title,city:'Budapest',district,neighborhood,type:'Lakás',price,area,rooms,floor:3,condition:'Felújított',building:'Tégla',balcony:true,balconyArea:6,elevator:true,description:'Világos, átgondolt elrendezésű otthon, kellemes környezetben. A nappalit nagy ablakok teszik igazán napfényessé. Kiváló közlekedés, kedvenc kávézók és zöldterületek néhány perc sétára.',images:[photos[image],photos[(image+1)%photos.length],photos[(image+2)%photos.length]],archived:false,createdAt:time,...extras});
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
function samplePublicDemo(items,limit,kind,scope,random) {
  const draw=()=>{const value=Number(random());return Number.isFinite(value)?Math.max(0,Math.min(1-Number.EPSILON,value)):0;};
  const key=kind+':'+scope,previous=publicDemoSelections.get(key)||[];
  // Excluding one previous member guarantees a different set whenever there is a spare candidate.
  const excluded=items.length>limit&&previous.length?previous[Math.floor(draw()*previous.length)]:null;
  const remaining=items.filter(item=>item.id!==excluded).map(item=>{
    const locations=kind==='search'?item.locations:[item.location];
    const budget=kind==='search'?item.maxPrice??item.minPrice:item.price;
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
export function demoLanding(region=null,random=Math.random) {
  const sample=migrateLocations(seed(()=>new Date().toISOString()));
  const available=!region||region.id==='HU110';
  const ownerType=entity=>normalizeAccountType(sample.users.find(user=>user.id===entity.ownerId)?.accountType);
  const ownerFirstName=entity=>publicFirstName(sample.users.find(user=>user.id===entity.ownerId)?.name);
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
  const scope=region?.id||'national';
  const searches=available?samplePublicDemo([...sample.searches,...searchExamples],8,'search',scope,random):[];
  const properties=available?samplePublicDemo([...sample.properties,...propertyExamples],4,'property',scope,random):[];
  return {
    region:clone(region),scope:region?'region':'national',
    searches:searches.map((entity,index)=>({key:`search-${index+1}`,title:publicTitle(entity.title,'Ingatlant keresnek'),type:publicDemoType(entity.type),locations:entity.locations.map(location=>location.label),minPrice:entity.minPrice,maxPrice:entity.maxPrice,minArea:entity.minArea,maxArea:entity.maxArea,minRooms:entity.minRooms,maxRooms:entity.maxRooms,ownerAccountType:ownerType(entity),ownerFirstName:ownerFirstName(entity)})),
    properties:properties.map((entity,index)=>({key:`property-${index+1}`,title:publicTitle(entity.title,'Eladó ingatlan'),type:publicDemoType(entity.type),location:entity.location.label,price:entity.price,area:entity.area,wholeRooms:entity.wholeRooms??null,halfRooms:entity.halfRooms??null,rooms:entity.rooms,lotArea:entity.lotArea??null,ownerAccountType:ownerType(entity),ownerFirstName:ownerFirstName(entity)}))
  };
}

export function isCompatible(property,search) {
  if (!property || !search || property.archived || search.archived || property.ownerId===search.ownerId) return false;
  return evaluateMatch(property,prepareSearch(search)).isExact;
}

export function createModel(storage=globalThis.localStorage, now=()=>new Date().toISOString()) {
  let state;
  try {const saved=JSON.parse(storage?.getItem(STORAGE_KEY)||'null');if(saved?.version===3&&Array.isArray(saved.properties)&&Array.isArray(saved.searches)&&Array.isArray(saved.decisions)&&Array.isArray(saved.matches)&&Array.isArray(saved.users)&&Number.isFinite(saved.credits))state=saved;} catch {}
  state = migrateLocations(state || seed(now));
  const own = (s,kind,id) => (kind==='property'?s.properties:s.searches).find(e=>e.id===id&&e.ownerId===s.userId);
  const ownersCanInteract=(s,property,search)=>canInteract(s.users.find(user=>user.id===property?.ownerId)?.accountType,s.users.find(user=>user.id===search?.ownerId)?.accountType);
  const transact = fn => {
    const draft=clone(state);
    const result=fn(draft);
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
        s.ledger.unshift({id:uid('credit'),amount:decision.charged,type:'like_refund',kind:'like_refund',description:text,refundedDecisionId:decision.id,propertyId:decision.propertyId,searchId:decision.searchId,createdAt:at});
        s.notifications.unshift({id:uid('notification'),userId:s.userId,decisionId:decision.id,kind:'like_refund',amount:decision.charged,text,createdAt:at,readAt:null});
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
        s.ledger.unshift({id:uid('credit'),amount:pkg.refundedCredits,type:'feedback_refund',kind:'feedback_refund',description:text,refundedFeedbackPackageId:pkg.id,propertyId:pkg.propertyId,createdAt:at});
        s.notifications.unshift({id:uid('notification'),userId:s.userId,feedbackPackageId:pkg.id,kind:'feedback_refund',amount:pkg.refundedCredits,text,createdAt:at,readAt:null});
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
    return {...clone(match),property:visibleEntity(property,s.users),search:visibleEntity(search,s.users),partner:clone(partner)};
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
      const preparedCandidate=prepared||prepareSearch(search);
      const evaluation=evaluateMatch(property,preparedCandidate,{includeReasons:false});
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
      if(buyer)data.address='';
      else{
        const person=s.users.find(user=>user.id===candidate.ownerId);
        data.buyerName ||= person?.name?.split(' ').at(-1)||'Érdeklődő';
        data.avatar=person?.avatar;
      }
      const explained=evaluateMatch(property,prepared||prepareSearch(search));
      return {...data,...ranking,reasons:explained.reasons,matchDetails:explained.matchDetails,kind:buyer?'property':'search',pair:{propertyId:property.id,searchId:search.id}};
    }),hasApproximate:approximate.length>0,
      requiresApproximateConsent:!exact.length&&approximate.length>0&&!includeApproximate,
      stage:exact.length?'exact':includeApproximate&&approximate.length?'approximate':'empty'};
  };
  return {
    getState() {
      processRefunds();
      return clone({unreadNotificationCount:state.notifications.filter(item=>item.userId===state.userId&&!item.readAt).length,user:state.users.find(u=>u.id===state.userId),credits:state.credits,active:state.active,properties:state.properties.filter(p=>p.ownerId===state.userId).map(p=>visibleEntity(p,state.users)),searches:state.searches.filter(q=>q.ownerId===state.userId).map(q=>visibleEntity(q,state.users)),decisions:state.decisions.filter(d=>own(state,d.actorKind,d.actorId)).map(d=>({...d,property:visibleEntity(state.properties.find(p=>p.id===d.propertyId),state.users),search:visibleEntity(state.searches.find(q=>q.id===d.searchId),state.users)})),ledger:state.ledger,createdAt:state.createdAt,likeCost:state.active?.id?likeCost(state.users.find(user=>user.id===state.userId)?.accountType,state.active.kind):0,reportedOwnerIds:[...new Set(state.reports.filter(report=>report.reporterId===state.userId).map(report=>report.reportedUserId))],reportedEntities:state.reports.filter(report=>report.reporterId===state.userId&&['property','search'].includes(report.entityKind)&&typeof report.entityId==='string').map(({entityKind,entityId,reason})=>({entityKind,entityId,reason}))});
    },
    recommendations(options={}) {
      processRefunds();
      return recommendationSnapshot(state,options);
    },
    feed(options={}) {
      processRefunds();
      return recommendationSnapshot(state,options).items;
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
        const prepared=preparedActive||prepareSearch(search),specificity=searchSpecificity(prepared);
        const data=visibleEntity(candidate,state.users,specificity);
        if(activeKind==='search')data.address='';
        const mine=state.decisions.find(item=>item.propertyId===property.id&&item.searchId===search.id&&item.actorKind===activeKind);
        const evaluation=evaluateMatch(property,prepared),compatible=evaluation.eligible;
        const match=state.matches.find(item=>item.propertyId===property.id&&item.searchId===search.id);
        return {...data,kind:activeKind==='search'?'property':'search',pair:{propertyId:property.id,searchId:search.id},
          score:evaluation.score,isExact:evaluation.isExact,reasons:evaluation.reasons,matchDetails:evaluation.matchDetails,searchSpecificity:specificity,valueForMoney:valueForMoney(property),
          likedYou:true,likedAt:decision.createdAt,myDecision:mine?(mine.liked?'liked':'passed'):null,matchId:match&&getMatch(state,match)?match.id:null,compatible,_decisionId:String(decision.id)};
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
        const evaluation=evaluateMatch(property,prepareSearch(search));
        if(!evaluation.eligible)throw new Error('Ez az ajánlás már nem érhető el az aktív profilodhoz.');
        if(s.decisions.some(d=>d.propertyId===pair.propertyId&&d.searchId===pair.searchId&&d.actorKind===s.active.kind))throw new Error('Erről az ajánlásról már döntöttél.');
        if(!evaluation.isExact&&(options?.allowApproximate!==true||recommendationSnapshot(s).items.length))
          throw new Error('Előbb nézd végig a tökéletes egyezéseket, majd engedélyezd a részleges találatokat.');
        const charged=liked?likeCost(s.users.find(user=>user.id===s.userId)?.accountType,s.active.kind):0;
        if(s.credits<charged)throw new Error(`Nincs elegendő kredited. A kedveléshez ${charged} kredit szükséges.`);
        s.credits-=charged;
        if(charged)s.ledger.unshift({id:uid('credit'),amount:-charged,type:s.active.kind==='property'?'seller_like':'agent_search_like',description:s.active.kind==='property'?`Ingatlan ajánlása: ${search.title}`:`Közvetítői keresés kedvelése: ${property.title}`,propertyId:property.id,searchId:search.id,createdAt:now()});
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
        s.ledger.unshift({id:uid('credit'),amount:-size,type:'feedback_package',kind:'feedback_package',description:`${size} visszajelzést tartalmazó csomag: ${property.title}`,feedbackPackageId:pkg.id,propertyId,createdAt});
        return {package:feedbackPackageView(pkg,createdAt),charged:size,credits:s.credits};
      });
    },
    recordImpression(propertyId,searchRequestId) {
      const property=state.properties.find(item=>item.id===propertyId),search=own(state,'search',searchRequestId);
      if(state.active?.kind!=='search'||state.active.id!==searchRequestId||!search||!property||!ownersCanInteract(state,property,search)
        ||!evaluateMatch(property,prepareSearch(search),{includeReasons:false}).eligible)throw new Error('Ez az ingatlan nem érhető el az aktív keresésedhez.');
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
      processRefunds();
      const items=state.notifications.filter(item=>item.userId===state.userId).sort((a,b)=>String(b.createdAt).localeCompare(String(a.createdAt))||String(b.id).localeCompare(String(a.id)));
      return clone({items:items.slice(offset,offset+limit).map(({userId,...item})=>item),total:items.length,unreadCount:items.filter(item=>!item.readAt).length,offset,limit,hasMore:offset+limit<items.length});
    },
    markNotificationRead(id) {
      processRefunds();
      return transact(s=>{
        const item=s.notifications.find(notification=>notification.id===id&&notification.userId===s.userId);
        if(!item)throw new Error('Az értesítés nem található.');
        item.readAt ||= now();
        const {userId,...result}=item;
        return result;
      });
    },
    activate(kind,id) {
      if(!['property','search'].includes(kind))throw new Error('Érvénytelen profiltípus.');
      return transact(s=>{const entity=own(s,kind,id);if(!entity||entity.archived)throw new Error('Ez a profil nem aktiválható.');s.active={kind,id};return s.active;});
    },
    saveEntity(kind,data,id) {
      if(!['property','search'].includes(kind))throw new Error('Érvénytelen profiltípus.');
      return transact(s=>{
        const existing=id?own(s,kind,id):null;
        if(id&&!existing)throw new Error('Ez a profil nem szerkeszthető.');
        const title=String(data.title??existing?.title??'').trim();
        if(title.length<3||title.length>150)throw new Error('Adj meg egy 3–150 karakteres nevet.');
        const incoming=clone(data);delete incoming.ownerAccountType;delete incoming.ownerFirstName;
        for(const field of ['searchSpecificity','valueForMoney','isExact','score'])delete incoming[field];
        if(kind==='property'){
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
          if(entity.type==='Ház'){entity.floor=null;entity.balcony=false;entity.elevator=false;}
          else{entity.balcony=!!entity.balcony;entity.elevator=!!entity.elevator;}
        }else{
          for(const [min,max] of [['minPrice','maxPrice'],['minArea','maxArea'],['minRooms','maxRooms']]){entity[min]=numeric(entity[min],null);entity[max]=numeric(entity[max],null);if((entity[min]!=null&&(!Number.isFinite(entity[min])||entity[min]<0))||(entity[max]!=null&&(!Number.isFinite(entity[max])||entity[max]<=0))||(entity[min]!=null&&entity[max]!=null&&entity[max]<entity[min]))throw new Error('A minimum érték nem lehet nagyobb a maximumnál; a korlátok érvényes számok legyenek.');}
          entity.balcony=!!entity.balcony;entity.elevator=!!entity.elevator;entity.moveIn ||= 'Rugalmas';
        }
        const list=kind==='property'?s.properties:s.searches;
        if(existing)list[list.findIndex(e=>e.id===id)]=entity;else list.push(entity);
        return visibleEntity(entity,s.users);
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
      return transact(s=>{const user=s.users.find(u=>u.id===s.userId);const name=String(data.name??user.name).trim(),email=String(data.email??user.email).trim(),phone=String(data.phone??user.phone).trim();if(name.length<3)throw new Error('Add meg a teljes neved.');if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))throw new Error('Érvényes e-mail-címet adj meg.');if(phone&&!/^[+\d ()-]{7,25}$/.test(phone))throw new Error('Érvényes telefonszámot adj meg.');Object.assign(user,{name,email,phone,avatar:name.split(/\s+/).map(n=>n[0]).slice(0,2).join('').toUpperCase()});return user;});
    },
    buyDemoCredits(amount) {
      amount=Number(amount);if(!Number.isInteger(amount)||amount<1||amount>10000)throw new Error('Érvénytelen kreditmennyiség.');
      return transact(s=>{s.credits+=amount;s.ledger.unshift({id:uid('credit'),amount,type:'demo_topup',description:'Demófeltöltés – fizetés nem történt',createdAt:now()});return {credits:s.credits,demo:true};});
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
