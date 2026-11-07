import { getLocation, resolveLegacyLocations, matchesLocations, isPropertyLocation } from './locations.js';
import {normalizePropertyAttributes, normalizePropertyRooms, normalizeSearchAttributes, attributesCompatible} from './attributes.js';
import {normalizeAccountType,likeCost,canInteract,normalizeReportReason,normalizeIncomingPagination} from './accounts.js';

/** Browser-only demonstration store. Real deployments use the authenticated .NET API. */
export const STORAGE_KEY = 'otthonra.demo.v3';
export const SELLER_LIKE_COST = 2;
const clone = value => JSON.parse(JSON.stringify(value));
const uid = prefix => `${prefix}-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
const photos = ['/assets/home.jpg','/assets/living.jpg','/assets/bedroom.jpg','/assets/kitchen.jpg','/assets/terrace.jpg','/assets/living.jpg'];
const normalized = value => String(value || '').trim().toLocaleLowerCase('hu');
const numeric = (value, fallback) => value === '' || value == null ? fallback : typeof value === 'boolean' ? NaN : Number(value);
const locationError = () => new Error('Válassz érvényes települést vagy budapesti kerületet a találati listából.');
function withLocations(entity, kind, strict = false) {
  let locations;
  if (kind === 'property' && ((Object.hasOwn(entity, 'locationId') && (strict || entity.locationId != null)) || entity.location?.id)) {
    const location = getLocation(Object.hasOwn(entity, 'locationId') && (strict || entity.locationId != null) ? entity.locationId : entity.location.id);
    locations = isPropertyLocation(location) ? [location] : [];
    if (strict && !isPropertyLocation(location)) throw locationError();
  } else if (kind === 'search' && Object.hasOwn(entity, 'locationIds') && (strict || entity.locationIds != null)) {
    const ids = Array.isArray(entity.locationIds) ? [...new Set(entity.locationIds)] : [];
    locations = ids.map(getLocation).filter(Boolean);
    if (strict && (!ids.length || ids.length > 50 || locations.length !== ids.length)) throw locationError();
  } else {
    locations = resolveLegacyLocations(entity);
  }
  if (strict && !locations.length) throw locationError();
  if (kind === 'property') {
    const location = locations[0] || null;
    return {...entity, locationId:location?.id || '', location:clone(location), city:location?.city ?? entity.city ?? '', district:location ? location.district || '' : entity.district ?? '', lotArea:entity.type === 'Ház' ? numeric(entity.lotArea, null) : null};
  }
  return {...entity, locationIds:locations.map(location=>location.id), locations:clone(locations), city:locations[0]?.city ?? entity.city ?? '', districts:locations.filter(location=>location.city === locations[0]?.city && location.district).map(location=>location.district)};
}
function migrateLocations(state) {
  state.users=state.users.map(user=>({...user,accountType:normalizeAccountType(user.accountType)}));
  state.reports=Array.isArray(state.reports)?state.reports.map(report=>({...report,reason:report.reason??'suspected_agent'})):[];
  state.properties = state.properties.map(entity=>normalizePropertyAttributes(withLocations(entity, 'property')));
  state.searches = state.searches.map(entity=>normalizeSearchAttributes(withLocations(entity, 'search')));
  return state;
}
const visibleEntity = (entity,users) => {
  const result = clone(entity);
  delete result.email; delete result.phone;
  result.ownerAccountType=normalizeAccountType(users?.find(user=>user.id===entity.ownerId)?.accountType);
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

export function isCompatible(property,search) {
  if (!property || !search || property.archived || search.archived || property.ownerId===search.ownerId) return false;
  if (!matchesLocations(property, search)) return false;
  if (search.type && !['bármilyen','mindegy','összes'].includes(normalized(search.type)) && normalized(property.type)!==normalized(search.type)) return false;
  property = normalizePropertyRooms(property);
  for (const [field,min,max] of [['price','minPrice','maxPrice'],['area','minArea','maxArea'],['rooms','minRooms','maxRooms']]) {
    if (!Number.isFinite(Number(property[field]))) return false;
    if (search[min]!=null && Number(property[field])<Number(search[min])) return false;
    if (search[max]!=null && Number(property[field])>Number(search[max])) return false;
  }
  if (search.type !== 'Ház' && search.balcony && !property.balcony) return false;
  if (search.type !== 'Ház' && search.elevator && !property.elevator) return false;
  return attributesCompatible(property,search);
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
  const getMatch = (s,match) => {
    const property=s.properties.find(p=>p.id===match.propertyId);
    const search=s.searches.find(q=>q.id===match.searchId);
    if(!property||!search||![property.ownerId,search.ownerId].includes(s.userId))return null;
    const reciprocal=s.decisions.some(d=>d.propertyId===property.id&&d.searchId===search.id&&d.actorKind==='property'&&d.liked)&&s.decisions.some(d=>d.propertyId===property.id&&d.searchId===search.id&&d.actorKind==='search'&&d.liked);
    if(!reciprocal)return null;
    const partner=s.users.find(u=>u.id===(property.ownerId===s.userId?search.ownerId:property.ownerId));
    return {...clone(match),property:visibleEntity(property,s.users),search:visibleEntity(search,s.users),partner:clone(partner)};
  };
  return {
    getState() {
      return clone({user:state.users.find(u=>u.id===state.userId),credits:state.credits,active:state.active,properties:state.properties.filter(p=>p.ownerId===state.userId).map(p=>visibleEntity(p,state.users)),searches:state.searches.filter(q=>q.ownerId===state.userId).map(q=>visibleEntity(q,state.users)),decisions:state.decisions.filter(d=>own(state,d.actorKind,d.actorId)).map(d=>({...d,property:visibleEntity(state.properties.find(p=>p.id===d.propertyId),state.users),search:visibleEntity(state.searches.find(q=>q.id===d.searchId),state.users)})),ledger:state.ledger,createdAt:state.createdAt,likeCost:state.active?.id?likeCost(state.users.find(user=>user.id===state.userId)?.accountType,state.active.kind):0,reportedOwnerIds:[...new Set(state.reports.filter(report=>report.reporterId===state.userId).map(report=>report.reportedUserId))],reportedEntities:state.reports.filter(report=>report.reporterId===state.userId&&['property','search'].includes(report.entityKind)&&typeof report.entityId==='string').map(({entityKind,entityId,reason})=>({entityKind,entityId,reason}))});
    },
    feed() {
      const active=own(state,state.active.kind,state.active.id);
      if(!active||active.archived)return [];
      const candidates=state.active.kind==='search'?state.properties:state.searches;
      return candidates.map(candidate=>{
        const property=state.active.kind==='search'?candidate:active;
        const search=state.active.kind==='search'?active:candidate;
        if(!isCompatible(property,search)||!ownersCanInteract(state,property,search))return null;
        if(state.decisions.some(d=>d.propertyId===property.id&&d.searchId===search.id&&d.actorKind===state.active.kind))return null;
        const likedYou=state.decisions.some(d=>d.propertyId===property.id&&d.searchId===search.id&&d.actorKind!==state.active.kind&&d.liked);
        const reasons=['Megfelelő elhelyezkedés','Árkereten belül','Ideális alapterület'];
        if(property.rooms>=3)reasons.push('Elegendő szoba');
        const boundedBudget=search.minPrice!=null&&search.maxPrice!=null;
        const budgetFit=boundedBudget?Math.max(0,1-Math.abs(property.price-(search.minPrice+search.maxPrice)/2)/Math.max(1,search.maxPrice-search.minPrice)):0.75;
        const score=Math.min(99,Math.round(92+budgetFit*5+(likedYou?2:0)));
        const data=visibleEntity(candidate,state.users);
        if(state.active.kind==='property') {
          const person=state.users.find(u=>u.id===candidate.ownerId);
          data.buyerName ||= person?.name?.split(' ').at(-1)||'Érdeklődő';
          data.avatar=person?.avatar;
        }
        return {...data,kind:state.active.kind==='search'?'property':'search',score,reasons,pair:{propertyId:property.id,searchId:search.id},likedYou};
      }).filter(Boolean).sort((a,b)=>Number(b.likedYou)-Number(a.likedYou)||b.score-a.score||a.id.localeCompare(b.id));
    },
    incomingLikes(options={}) {
      const {offset,limit}=normalizeIncomingPagination(options);
      const active=own(state,state.active?.kind,state.active?.id);
      const empty={active:null,items:[],total:0,offset,limit,hasMore:false,likeCost:0};
      if(!active||active.archived)return empty;
      const activeKind=state.active.kind;
      const items=state.decisions.filter(decision=>decision.liked&&decision.actorKind===(activeKind==='property'?'search':'property')&&(activeKind==='property'?decision.propertyId===active.id:decision.searchId===active.id)).map(decision=>{
        const property=state.properties.find(item=>item.id===decision.propertyId),search=state.searches.find(item=>item.id===decision.searchId);
        if(!property||!search||property.archived||search.archived||property.ownerId===search.ownerId||!ownersCanInteract(state,property,search))return null;
        const candidate=activeKind==='search'?property:search;
        if(candidate.ownerId===state.userId)return null;
        const data=visibleEntity(candidate,state.users);
        if(activeKind==='search')data.address='';
        const mine=state.decisions.find(item=>item.propertyId===property.id&&item.searchId===search.id&&item.actorKind===activeKind);
        const compatible=isCompatible(property,search),match=state.matches.find(item=>item.propertyId===property.id&&item.searchId===search.id);
        return {...data,kind:activeKind==='search'?'property':'search',pair:{propertyId:property.id,searchId:search.id},score:compatible?98:0,reasons:compatible?['Megfelelő elhelyezkedés','Árkereten belül','Ideális alapterület']:[],likedYou:true,likedAt:decision.createdAt,myDecision:mine?(mine.liked?'liked':'passed'):null,matchId:match&&getMatch(state,match)?match.id:null,compatible,_decisionId:String(decision.id)};
      }).filter(Boolean).sort((a,b)=>String(a.likedAt)===String(b.likedAt)?(a._decisionId===b._decisionId?0:a._decisionId>b._decisionId?-1:1):(String(a.likedAt)>String(b.likedAt)?-1:1));
      const total=items.length;
      return {active:{kind:activeKind,id:active.id},items:items.slice(offset,offset+limit).map(({_decisionId,...item})=>item),total,offset,limit,hasMore:offset+limit<total,likeCost:likeCost(state.users.find(user=>user.id===state.userId)?.accountType,activeKind)};
    },
    decide(item,liked) {
      if(typeof liked!=='boolean')throw new Error('Érvénytelen döntés.');
      const pair=item?.pair;
      if(!pair?.propertyId||!pair?.searchId)throw new Error('Érvénytelen ajánlás.');
      return transact(s=>{
        const active=own(s,s.active.kind,s.active.id);
        const property=s.properties.find(p=>p.id===pair.propertyId),search=s.searches.find(q=>q.id===pair.searchId);
        if(!active||active.archived||(s.active.kind==='property'?property?.id:search?.id)!==active.id||!isCompatible(property,search)||!ownersCanInteract(s,property,search))throw new Error('Ez az ajánlás már nem érhető el az aktív profilodhoz.');
        if(s.decisions.some(d=>d.propertyId===pair.propertyId&&d.searchId===pair.searchId&&d.actorKind===s.active.kind))throw new Error('Erről az ajánlásról már döntöttél.');
        const charged=liked?likeCost(s.users.find(user=>user.id===s.userId)?.accountType,s.active.kind):0;
        if(s.credits<charged)throw new Error(`Nincs elegendő kredited. A kedveléshez ${charged} kredit szükséges.`);
        s.credits-=charged;
        if(charged)s.ledger.unshift({id:uid('credit'),amount:-charged,type:s.active.kind==='property'?'seller_like':'agent_search_like',description:s.active.kind==='property'?`Ingatlan ajánlása: ${search.title}`:`Közvetítői keresés kedvelése: ${property.title}`,propertyId:property.id,searchId:search.id,createdAt:now()});
        s.decisions.push({id:uid('decision'),actorKind:s.active.kind,actorId:active.id,...pair,liked,charged,createdAt:now()});
        let match=null;
        if(liked&&s.decisions.some(d=>d.propertyId===pair.propertyId&&d.searchId===pair.searchId&&d.actorKind!==s.active.kind&&d.liked)) {
          let record=s.matches.find(m=>m.propertyId===pair.propertyId&&m.searchId===pair.searchId);
          if(!record){record={id:uid('match'),...pair,createdAt:now(),unread:0,messages:[]};s.matches.unshift(record);}
          match=getMatch(s,record);
        }
        return {match,charged};
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
        const incoming=clone(data);delete incoming.ownerAccountType;
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
    matches() {return state.matches.map(m=>getMatch(state,m)).filter(Boolean).sort((a,b)=>b.createdAt.localeCompare(a.createdAt));},
    sendMessage(matchId,text) {
      text=String(text||'').trim();if(!text||text.length>4000)throw new Error('Az üzenet 1–4000 karakter hosszú lehet.');
      return transact(s=>{const record=s.matches.find(m=>m.id===matchId);if(!record||!getMatch(s,record))throw new Error('Csak kölcsönös találat után küldhetsz üzenetet.');const message={id:uid('message'),senderId:s.userId,text,createdAt:now()};record.messages.push(message);record.unread=0;return message;});
    },
    markRead(matchId){return transact(s=>{const record=s.matches.find(m=>m.id===matchId);if(!record||!getMatch(s,record))throw new Error('A találat nem érhető el.');record.unread=0;return true;});},
    reset(){const next=migrateLocations(seed(now));try{storage?.setItem(STORAGE_KEY,JSON.stringify(next));}catch{throw new Error('A demó nem állítható vissza.');}state=next;return this.getState();}
  };
}
export const model=createModel();
