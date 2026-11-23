import test from 'node:test';
import assert from 'node:assert/strict';
import {createDraft,updateDraft,saveDraft,loadDraft,clearDraft,prepareDraftForAuth,bindDraft,prepareDraftSave,markDraftSaved,prefillFromTeaser,suggestEntityTitle,sanitizeTeaserPrefill,normalizeDraftOrigin,originFromListing,originFromLocations,originBlank,sameDraftOrigin,DRAFT_STORAGE_KEY,DRAFT_TTL_MS,DRAFT_EDITOR_LAYOUT_VERSION} from '../dist/onboarding.js';
import {getLocation,locations} from '../dist/locations.js';
import {createModel,STORAGE_KEY,demoLanding} from '../dist/model.js';
import {ApiModel,findPublicLocations,findPublicStreets,fetchLanding,getModel,connectApi,disconnectApi,API_CONFIG_KEY,AUTH_ATTEMPT_KEY} from '../dist/api.js';

const NOW='2026-11-18T10:00:00Z';
const USER={id:'account-one',email:'anna@example.hu'};
const requestId='1252f520-aefe-4a9c-b1b6-932ef64fe38a';
const store=()=>{const values=new Map();return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,String(value)),removeItem:key=>values.delete(key)};};
const response=(body,status=200)=>({ok:status>=200&&status<300,status,text:async()=>JSON.stringify(body)});
const city=getLocation('city:Debrecen'),district=getLocation('district:Budapest:11');
const deferred=()=>{let resolve;const promise=new Promise(accept=>{resolve=accept;});return {promise,resolve};};
async function authScenario(run) {
  const previous={fetch:globalThis.fetch,storage:globalThis.localStorage,config:globalThis.OTTHONRA_CONFIG};
  globalThis.localStorage=store();globalThis.OTTHONRA_CONFIG={mode:'demo'};
  try {await run(globalThis.localStorage);} finally {globalThis.fetch=previous.fetch;globalThis.localStorage=previous.storage;globalThis.OTTHONRA_CONFIG=previous.config;}
}
function authResponse(url,options) {
  const path=new URL(url).pathname,identity=options.headers.Authorization?.replace('Bearer ','');
  if(path==='/api/me')return response({id:identity,email:identity,name:'Teszt Anna',credits:0});
  if(path==='/api/me/entities')return response({properties:[],searches:[]});
  if(path==='/api/credits/ledger')return response([]);
  throw new Error('Unexpected auth test path: '+path);
}

test('draft reload preserves incomplete form, exact owner-entered address, selection metadata, step and title choice',()=>{
  const storage=store();
  let draft=createDraft('property',{title:'Otthonom',locationId:city.id,price:'-',street:'Kossuth utca',houseNumber:'12/A',postalCode:'4024',condition:'Jó',insulated:false},{now:NOW,editor:{query:'Debre',streetQuery:'Kossuth',locations:[city],completedSteps:[0,1],titleGenerated:true}});
  draft=updateDraft(draft,{step:2,editor:{titleGenerated:false}},{now:NOW});saveDraft(draft,storage);
  const reloaded=loadDraft(storage,{now:NOW});
  assert.equal(reloaded.id,draft.id);assert.equal(reloaded.version,1);assert.equal(reloaded.phase,'editing');assert.equal(reloaded.step,2);
  assert.deepEqual(reloaded.data,draft.data);assert.equal(reloaded.data.price,'-');assert.equal(reloaded.data.insulated,false);
  assert.deepEqual(reloaded.editor,{layoutVersion:DRAFT_EDITOR_LAYOUT_VERSION,query:'Debre',streetQuery:'Kossuth',titleGenerated:false,completedSteps:[0,1],locations:[{id:city.id,label:city.label,city:city.city,district:null,kind:'city',settlementCount:null}]});
  assert.equal(Date.parse(reloaded.expiresAt)-Date.parse(reloaded.updatedAt),DRAFT_TTL_MS);
});

test('legacy five-topic drafts migrate only navigation and stay stable across tabs and repeated reloads',()=>{
  for(const kind of ['property','search'])for(let step=0;step<5;step++){
    const storage=store(),data=kind==='property'?{title:'Saját címem',locationId:city.id,type:'Ház',street:'Saját utca',houseNumber:'12/A',postalCode:'4024',price:'-',lotArea:'123',images:'https://images.example.hu/home.jpg'}:{title:'Pontos keresésem',locationIds:[city.id,district.id],type:'Lakás',maxPrice:'',minRooms:'2.5',conditions:['Jó','Átlagos']};
    const original=createDraft(kind,data,{now:NOW,origin:originBlank(kind),editor:{query:'Debre',streetQuery:'Saját',locations:[city],titleGenerated:false}});
    const legacy=structuredClone(original);delete legacy.editor.layoutVersion;legacy.step=step;legacy.editor.completedSteps=[-1,0,2,4,'3',5,2];
    storage.setItem(DRAFT_STORAGE_KEY,JSON.stringify(legacy));const before=storage.getItem(DRAFT_STORAGE_KEY);
    const firstTab=loadDraft(storage,{now:NOW}),otherTab=loadDraft(storage,{now:NOW});
    assert.deepEqual(firstTab,otherTab,'Tabs must agree before the first migrated save');
    assert.equal(firstTab.step,step===0?0:step+1);assert.equal(firstTab.editor.layoutVersion,DRAFT_EDITOR_LAYOUT_VERSION);
    assert.deepEqual(firstTab.editor.completedSteps,[0,1,3,5]);
    for(const field of ['id','creationRequestId','kind','data','origin','phase','createdAt','updatedAt','expiresAt'])assert.deepEqual(firstTab[field],legacy[field],field+' must survive a navigation migration');
    assert.equal(firstTab.editor.query,'Debre');assert.equal(firstTab.editor.streetQuery,'Saját');assert.equal(firstTab.editor.titleGenerated,false);assert.deepEqual(firstTab.editor.locations,original.editor.locations);
    assert.equal(storage.getItem(DRAFT_STORAGE_KEY),before,'Reading a legacy draft must not mutate storage or extend its lifetime');
    saveDraft(firstTab,storage);assert.deepEqual(loadDraft(storage,{now:NOW}),firstTab,'A saved migration must not shift topics again');
  }
});

test('the new type topic and final sixth topic preserve their exact positions and completion state',()=>{
  const storage=store();let draft=createDraft('search',{locationIds:[city.id],type:'Ház'},{now:NOW});
  assert.equal(draft.editor.layoutVersion,DRAFT_EDITOR_LAYOUT_VERSION);
  draft=updateDraft(draft,{step:1,editor:{completedSteps:[0]}},{now:NOW});saveDraft(draft,storage);
  assert.equal(loadDraft(storage,{now:NOW}).step,1,'The new type topic must never become the price topic on reload');
  draft=updateDraft(draft,{step:5,editor:{completedSteps:[0,1,2,3,4,5]}},{now:NOW});saveDraft(draft,storage);
  assert.equal(loadDraft(storage,{now:NOW}).step,5);assert.deepEqual(loadDraft(storage,{now:NOW}).editor.completedSteps,[0,1,2,3,4,5]);
  const identity=draft.creationRequestId;
  draft=updateDraft(draft,{step:1,data:{type:'Lakás'}},{now:NOW});saveDraft(draft,storage);draft=loadDraft(storage,{now:NOW});
  assert.equal(draft.step,1);assert.equal(draft.data.type,'Lakás');assert.equal(draft.creationRequestId,identity);
  assert.equal(updateDraft(draft,{step:99},{now:NOW}).step,5);
});

test('legacy completed and pending drafts keep frozen input, account binding and creation receipts through migration',()=>{
  const data={title:'Mentésre váró keresés',type:'Lakás',locationIds:[city.id],maxPrice:'80',minRooms:'2'};
  const origin=originFromListing('property','property-'+'a'.repeat(64));
  const editing=updateDraft(createDraft('search',data,{now:NOW,origin}),{step:5,editor:{completedSteps:[0,1,2,3,4,5]}},{now:NOW});
  const authenticating=prepareDraftForAuth(editing,USER.email,{now:NOW}),saving=prepareDraftSave(authenticating,USER,{now:NOW}),saved=markDraftSaved(saving,'existing-search',{now:NOW});
  for(const original of [authenticating,saving,saved]){
    const storage=store(),legacy=structuredClone(original);delete legacy.editor.layoutVersion;legacy.step=4;legacy.editor.completedSteps=[0,1,2,3,4];
    storage.setItem(DRAFT_STORAGE_KEY,JSON.stringify(legacy));const restored=loadDraft(storage,{now:NOW});
    assert.equal(restored.step,5);assert.deepEqual(restored.editor.completedSteps,[0,1,2,3,4,5]);
    for(const field of ['id','creationRequestId','phase','expectedEmail','ownerId','savedEntityId','origin','data','completedData','createdAt','updatedAt','expiresAt'])assert.deepEqual(restored[field],original[field],field+' must not change for '+original.phase);
    assert.equal(Object.isFrozen(restored.completedData),true);
    assert.throws(()=>prepareDraftSave(restored,{id:'other',email:'other@example.hu'},{now:NOW}),/másik fiók/);
    const retry=prepareDraftSave(restored,USER,{now:NOW});assert.equal(retry.creationRequestId,original.creationRequestId);assert.deepEqual(retry.completedData,original.completedData);
    saveDraft(restored,storage);assert.deepEqual(loadDraft(storage,{now:NOW}),restored);
  }
});

test('draft allowlist excludes credentials, source identity and all geocoding metadata',()=>{
  const storage=store(),draft=createDraft('property',{id:'source-property',ownerId:'other-owner',password:'secret',token:'secret',accessToken:'secret',latitude:47,longitude:19,provider:'Google',neighborhoodIds:['secret'],street:'Saját utca',houseNumber:'1',addressDetails:{street:'Saját utca',houseNumber:'1',latitude:47,longitude:19,provider:'Google',placeId:'private'},locations:[{...city,latitude:47,longitude:19}]},{now:NOW});
  saveDraft(draft,storage);const raw=JSON.parse(storage.getItem(DRAFT_STORAGE_KEY));
  for (const field of ['id','ownerId','password','token','accessToken','latitude','longitude','provider','neighborhoodIds']) assert.equal(field in raw.data,false,field);
  assert.deepEqual(raw.data.addressDetails,{street:'Saját utca',houseNumber:'1'});
  assert.equal('latitude' in raw.data.locations[0],false);
  assert.equal(loadDraft(store(),{now:NOW}),null);
});

test('draft storage preserves the full supported description and twelve image URLs while stripping secrets',()=>{
  const storage=store(),description='Á'.repeat(6000),image='https://images.example.hu/'+ 'a'.repeat(2000-'https://images.example.hu/'.length),images=Array(12).fill(image).join('\n');
  const draft=createDraft('property',{title:'Teljes leírás',description,images,password:'do-not-store',token:'do-not-store',addressDetails:{street:'Saját utca',houseNumber:'12',latitude:47}},{now:NOW});
  saveDraft(draft,storage);const loaded=loadDraft(storage,{now:NOW});
  assert.equal(loaded.data.description,description);assert.equal(loaded.data.description.length,6000);assert.equal(loaded.data.images,images);
  assert.equal('password' in loaded.data,false);assert.equal('token' in loaded.data,false);assert.equal('latitude' in loaded.data.addressDetails,false);
});

test('corrupt/expired drafts recover safely and cleanup cannot erase a replacement draft',()=>{
  const storage=store();storage.setItem(DRAFT_STORAGE_KEY,'invalid JSON');assert.equal(loadDraft(storage,{now:NOW}),null);
  const first=createDraft('search',{title:'Első'},{now:NOW}),second=createDraft('search',{title:'Második'},{now:NOW});
  saveDraft(first,storage);saveDraft(second,storage);assert.equal(clearDraft(first.id,storage),false);assert.equal(loadDraft(storage,{now:NOW}).id,second.id);
  assert.equal(loadDraft(storage,{now:Date.parse(NOW)+DRAFT_TTL_MS}),null);assert.equal(storage.getItem(DRAFT_STORAGE_KEY),null);
});

test('completed draft freezes its payload and creation identity across reload, retry and auth interruption',()=>{
  const storage=store();let draft=createDraft('search',{title:'Lakás keresés',locationIds:[city.id],maxPrice:'80',minRooms:null},{now:NOW});
  draft=prepareDraftForAuth(draft,' ANNA@EXAMPLE.HU ',{now:NOW});
  assert.equal(draft.phase,'awaiting-auth');assert.equal(draft.expectedEmail,USER.email);assert.equal(Object.isFrozen(draft.completedData),true);
  const identity=draft.creationRequestId;saveDraft(draft,storage);draft=loadDraft(storage,{now:NOW});
  assert.throws(()=>{draft.completedData.maxPrice=90;},TypeError);
  assert.throws(()=>updateDraft(draft,{data:{maxPrice:90}},{now:NOW}),/lezárt/);
  draft=prepareDraftSave(draft,USER,{now:NOW});assert.equal(draft.phase,'saving');assert.equal(draft.ownerId,USER.id);assert.equal(draft.creationRequestId,identity);
  draft=prepareDraftForAuth(draft,USER.email,{now:NOW});draft=prepareDraftSave(draft,USER,{now:NOW});assert.equal(draft.creationRequestId,identity);assert.equal(draft.completedData.maxPrice,'80');
  const saved=markDraftSaved(draft,'saved-search',{now:NOW});assert.equal(saved.phase,'saved');assert.equal(saved.savedEntityId,'saved-search');
  const reopened=updateDraft(draft,{phase:'editing',data:{maxPrice:90}},{now:NOW});assert.equal(reopened.creationRequestId,identity);assert.equal(reopened.completedData,undefined);
  assert.equal(prepareDraftSave(reopened,USER,{now:NOW}).creationRequestId,identity);
});

test('editing after an uncertain creation retains the lifetime request ID and cannot duplicate the saved entity',()=>{
  const storage=store(),model=createModel(storage),user=model.getState().user,before=model.getState().searches.length;
  let draft=createDraft('search',{title:'Válasz nélkül mentett keresés',locationIds:[city.id],maxPrice:80},{now:NOW});
  const identity=draft.creationRequestId;assert.equal(identity,draft.id);
  draft=prepareDraftSave(draft,user,{now:NOW});
  const saved=model.saveEntity(draft.kind,draft.completedData,undefined,{creationRequestId:identity});
  // The response was lost: reopening and reloading may change the form, never its creation identity.
  draft=updateDraft(draft,{phase:'editing',data:{maxPrice:81}},{now:NOW});saveDraft(draft,storage);draft=loadDraft(storage,{now:NOW});
  assert.equal(draft.completedData,undefined);assert.equal(draft.creationRequestId,identity);
  draft=prepareDraftSave(prepareDraftForAuth(draft,user.email,{now:NOW}),user,{now:NOW});
  assert.equal(draft.creationRequestId,identity);
  assert.throws(()=>model.saveEntity(draft.kind,draft.completedData,undefined,{creationRequestId:draft.creationRequestId}),/másik kitöltés/);
  assert.equal(model.getState().searches.length,before+1);assert.equal(model.getState().searches.filter(item=>item.id===saved.id).length,1);
  assert.notEqual(createDraft('search',{}, {now:NOW}).creationRequestId,identity);
});

test('draft binding refuses another account or another registration address',()=>{
  const draft=prepareDraftForAuth(createDraft('search',{}, {now:NOW}),USER.email,{now:NOW});
  assert.throws(()=>prepareDraftSave(draft,{id:'other',email:'other@example.hu'},{now:NOW}),/másik fiók/);
  assert.throws(()=>prepareDraftForAuth(draft,'other@example.hu',{now:NOW}),/másik e-mail/);
  const bound=bindDraft(draft,USER,{now:NOW});assert.throws(()=>prepareDraftSave(bound,{id:'different-account',email:USER.email},{now:NOW}),/másik fiók/);
});

test('listing-origin drafts retain one opaque source identity across edits, reload and authentication',()=>{
  const storage=store(),propertyKey='property-'+'a'.repeat(64),otherPropertyKey='property-'+'b'.repeat(64);
  const origin=originFromListing('property',propertyKey);
  let draft=createDraft('search',{title:'Saját keresésem',locationIds:[city.id],maxPrice:80},{now:NOW,origin});
  const identity=draft.creationRequestId;
  assert.deepEqual(draft.origin,{kind:'property',key:propertyKey});
  assert.equal(sameDraftOrigin(draft,'search',origin),true);
  draft=updateDraft(draft,{data:{title:'Átírt saját keresés',locationIds:[district.id],maxPrice:90},step:3,origin:originFromListing('property',otherPropertyKey)},{now:NOW});
  assert.deepEqual(draft.origin,origin,'Changing the current criteria must not rewrite the original listing identity');
  assert.equal(sameDraftOrigin(draft,'search',origin),true,'The same source resumes even after criteria or source display values change');
  assert.equal(sameDraftOrigin(draft,'search',originFromListing('property',otherPropertyKey)),false);
  assert.equal(sameDraftOrigin(draft,'property',origin),false);
  saveDraft(draft,storage);draft=loadDraft(storage,{now:NOW});
  assert.deepEqual(draft.origin,origin);assert.equal(draft.step,3);assert.equal(draft.creationRequestId,identity);
  draft=prepareDraftSave(prepareDraftForAuth(draft,USER.email,{now:NOW}),USER,{now:NOW});
  assert.deepEqual(draft.origin,origin);assert.equal(draft.creationRequestId,identity);
  assert.equal('origin' in draft.data,false);assert.equal('origin' in draft.completedData,false);assert.equal('sourceKey' in draft.completedData,false);
  assert.equal(JSON.stringify(draft.completedData).includes(propertyKey),false,'Public source identity is local draft metadata, never creation input');
  assert.notEqual(createDraft('search',{}, {now:NOW,origin:originFromListing('property',otherPropertyKey)}).creationRequestId,identity);
  const searchOrigin=originFromListing('search','search-'+'c'.repeat(64));
  assert.equal(sameDraftOrigin(createDraft('property',{}, {now:NOW,origin:searchOrigin}),'property',searchOrigin),true);
});

test('location starts compare the current exact canonical set independently of order, duplicates and original source',()=>{
  const origin=originFromLocations([district,city,district]);
  assert.deepEqual(origin,{kind:'locations',locationIds:[city.id,district.id].sort()});
  const original=originFromListing('property','property-'+'d'.repeat(64));
  let draft=createDraft('search',{locationIds:[district.id,city.id,city.id]},{now:NOW,origin:original});
  assert.equal(sameDraftOrigin(draft,'search',origin),true,'A location start may resume a search originally seeded from a listing');
  assert.equal(sameDraftOrigin(draft,'search',originFromLocations([city.id])),false,'A subset is a different search');
  assert.equal(sameDraftOrigin(draft,'search',originFromLocations([city.id,district.id,'city:Szeged'])),false,'An extra selected location starts a new draft');
  draft=updateDraft(draft,{data:{locationIds:[city.id]}},{now:NOW});
  assert.equal(sameDraftOrigin(draft,'search',origin),false,'The old originating choices do not override edited current choices');
  assert.equal(sameDraftOrigin(draft,'search',originFromLocations([city.id])),true);
  assert.equal(sameDraftOrigin({...draft,data:{locationIds:[city.id,'unknown-location']}},'search',originFromLocations([city.id])),false);
  assert.equal(sameDraftOrigin(createDraft('property',{locationId:city.id},{now:NOW}),'search',originFromLocations([city.id])),false);
  const storage=store(),fromPicker=createDraft('search',{locationIds:[city.id]},{now:NOW,origin});
  saveDraft(fromPicker,storage);assert.deepEqual(loadDraft(storage,{now:NOW}).origin,origin);
});

test('origin sanitization rejects positional keys and private IDs while preserving older drafts without false listing matches',()=>{
  const sourceId='1252f520-aefe-4a9c-b1b6-932ef64fe38a',opaque='property-'+'e'.repeat(64);
  for(const key of ['property-1',sourceId,'property-'+sourceId,'property-'+'E'.repeat(64),'search-'+'e'.repeat(64),opaque+'extra',null])assert.equal(originFromListing('property',key),null);
  assert.equal(normalizeDraftOrigin({kind:'property',key:opaque},'property'),null,'A property draft originates from a search teaser, never another property');
  assert.equal(normalizeDraftOrigin({kind:'locations',locationIds:[city.id]},'property'),null);
  assert.equal(originFromLocations([]),null);assert.equal(originFromLocations([city.id,'unknown-location']),null);assert.equal(originFromLocations(new Array(1)),null);
  assert.equal(originFromLocations(Array(51).fill(city.id)),null);
  const storage=store(),draft=createDraft('search',{title:'Régebbi piszkozat',locationIds:[city.id],origin:{key:sourceId},sourceKey:sourceId},{now:NOW,origin:{kind:'property',key:opaque,id:sourceId,ownerId:USER.id,street:'Titkos utca',latitude:47}});
  saveDraft(draft,storage);const raw=JSON.parse(storage.getItem(DRAFT_STORAGE_KEY));
  assert.deepEqual(raw.origin,{kind:'property',key:opaque});assert.equal(JSON.stringify(raw).includes(sourceId),false);assert.equal('origin' in raw.data,false);assert.equal('sourceKey' in raw.data,false);
  delete raw.origin;storage.setItem(DRAFT_STORAGE_KEY,JSON.stringify(raw));const legacy=loadDraft(storage,{now:NOW});
  assert.ok(legacy);assert.equal(legacy.origin,undefined);assert.equal(sameDraftOrigin(legacy,'search',originFromListing('property',opaque)),false);
  assert.equal(sameDraftOrigin(legacy,'search',originFromLocations([city.id])),true,'A legacy draft still has verifiable current location choices');
  assert.equal(sameDraftOrigin(legacy,'search',originBlank('search')),false,'Missing provenance never silently becomes a blank-source identity');
});

test('blank-origin drafts resume only the same empty-start flow and retain their original request identity',()=>{
  const origin=originBlank('search'),draft=createDraft('search',{title:'Elkezdett keresés',locationIds:[city.id]},{now:NOW,origin});
  assert.deepEqual(origin,{kind:'blank',entityKind:'search'});assert.equal(sameDraftOrigin(draft,'search',origin),true);
  assert.equal(sameDraftOrigin(draft,'property',originBlank('property')),false);
  assert.equal(sameDraftOrigin(draft,'search',originFromListing('property','property-'+'f'.repeat(64))),false);
  const reopened=updateDraft(prepareDraftForAuth(draft,USER.email,{now:NOW}),{phase:'editing',data:{maxPrice:90}},{now:NOW});
  assert.equal(reopened.creationRequestId,draft.creationRequestId);assert.deepEqual(reopened.origin,origin);
  assert.equal(originBlank('unknown'),null);assert.equal(normalizeDraftOrigin({kind:'blank',entityKind:'property'},'search'),null);
});

test('property teaser seeds a relaxed search using chosen canonical locations and safe attributes',()=>{
  const source={prefill:{locations:[district],type:'Lakás',price:72.9,area:64,rooms:3,condition:'Felújított',building:'Tégla',constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m feletti',floor:14,heatingType:'Hőszivattyú',balcony:true,elevator:false},title:'Más címe',description:'Más leírása',address:'Titkos cím',id:'source'};
  const data=prefillFromTeaser('search',source,{locations:[city,district]});
  assert.deepEqual(data.locationIds,[city.id,district.id]);assert.deepEqual([data.minPrice,data.maxPrice,data.minRooms,data.maxRooms],[null,85,3,null]);assert.deepEqual([data.minArea,data.maxArea],[55,null]);
  assert.deepEqual(data.conditions,['Új/felújított']);assert.deepEqual(data.buildings,['Tégla']);assert.deepEqual(data.heatingTypes,['Hőszivattyú']);assert.deepEqual(data.floors,[11]);
  assert.equal(data.balcony,true);assert.equal(data.elevator,false);assert.equal('address' in data,false);assert.equal('description' in data,false);assert.notEqual(data.title,source.title);assert.ok(data.title.includes('+1'));
});

test('property-to-search rounds relaxed price upward and area downward without inventing upper room or area bounds',()=>{
  for (const [price,area,maxPrice,minArea] of [[165,64,185,55],[50,60,55,50],[100,50,110,45],[45.454545,100,50,90],[45.454546,100,55,90],[0.000001,5,5,null],[null,null,null,null]]) {
    const data=prefillFromTeaser('search',{prefill:{type:'Lakás',locations:[city],price,area,rooms:2.5}});
    assert.deepEqual([data.maxPrice,data.minArea],[maxPrice,minArea],`price=${price}, area=${area}`);
    assert.deepEqual([data.minPrice,data.maxArea,data.minRooms,data.maxRooms],[null,null,2.5,null]);
    if(maxPrice!=null)assert.equal(maxPrice%5,0);if(minArea!=null)assert.equal(minArea%5,0);
  }
  const source=sanitizeTeaserPrefill('property',{locations:[city],type:'Lakás',price:165000000,area:64,rooms:3},{pricesInHuf:true});
  const converted=prefillFromTeaser('search',{prefill:source});
  assert.equal(converted.maxPrice,185,'API HUF prices convert once, then round in million-HUF units');
  const empty=prefillFromTeaser('search');
  assert.equal(empty.type,undefined);assert.deepEqual([empty.minPrice,empty.maxPrice,empty.minArea,empty.maxArea,empty.minRooms,empty.maxRooms],[null,null,null,null,null,null]);
  const invalid=prefillFromTeaser('search',{prefill:{price:-5,area:0}});
  assert.deepEqual([invalid.maxPrice,invalid.minArea],[null,null]);
});

test('suggested editable names summarize canonical place and entered price/size within seventy characters',()=>{
  const search=suggestEntityTitle('search',{type:'Lakás',locations:[city],maxPrice:'85',minArea:'55',minRooms:'3'});
  assert.match(search,/Lakás keresés/);assert.match(search,/Debrecen/);assert.match(search,/85 M Ft-ig/);assert.match(search,/55\+ m²/);assert.ok(search.length<=70);
  const property=suggestEntityTitle('property',{type:'Ház',locationId:city.id,price:'165',area:'120'});
  assert.match(property,/Ház eladó/);assert.match(property,/Debrecen/);assert.match(property,/165 M Ft/);assert.match(property,/120 m²/);assert.ok(property.length<=70);
  assert.equal(suggestEntityTitle('search',{type:'Lakás',locations:[city],maxPrice:'',minArea:null,minRooms:''}),'Lakás keresés – Debrecen');
  assert.match(suggestEntityTitle('search',{type:'Lakás',locations:[city],minRooms:2.5}),/2,5\+ szoba/);
  const longPlace=locations.filter(location=>location.kind==='neighborhood').sort((a,b)=>b.label.length-a.label.length)[0];
  const compact=suggestEntityTitle('search',{type:'Üzlethelyiség',locations:[longPlace,city,district],maxPrice:999.99,minArea:12345});
  assert.ok(compact.length<=70);assert.match(compact,/\+2 helyszín/);assert.equal(compact.includes('NaN'),false);
  assert.ok(suggestEntityTitle('property',{type:'Üzlethelyiség',locationId:city.id,price:1e50,area:1e50}).length<=70);
});

test('search teaser copies only unambiguous property values and never invents an exact address',()=>{
  const neighborhood=locations.find(location=>location.kind==='neighborhood');
  const source={prefill:{locations:[city,district],type:'Ház',minPrice:60,maxPrice:90,minArea:100,maxArea:100,minRooms:3,maxRooms:3,conditions:['Jó'],buildings:['Tégla','Panel'],constructionAges:[],views:['Panorámás'],heatingTypes:['Gázkazán'],floors:[11],balcony:true,elevator:true},title:'Más neve',description:'Más szövege',buyerName:'Más neve',street:'Titkos utca'};
  const data=prefillFromTeaser('property',source);
  assert.equal(data.type,'Ház');assert.equal(data.locationId,undefined);assert.equal(data.price,undefined);assert.equal(data.area,100);assert.equal(data.rooms,3);assert.equal(data.condition,'Jó');assert.equal(data.building,undefined);assert.equal(data.view,'Panorámás');assert.equal(data.floor,undefined);assert.equal(data.balcony,false);
  for (const field of ['description','buyerName','street','address','houseNumber']) assert.equal(field in data,false,field);
  assert.equal(prefillFromTeaser('property',{prefill:{...source.prefill,locations:[neighborhood]}}).locationId,undefined);
  assert.equal(prefillFromTeaser('property',{prefill:{...source.prefill,locations:[city]}}).locationId,city.id);
});

test('public seed normalization converts HUF once, strips private data and generates short editable names',()=>{
  const safe=sanitizeTeaserPrefill('property',{...city,locations:[city],type:'Lakás',price:72900000,condition:'Ismeretlen',building:'Tégla',street:'Titkos',id:'source',latitude:47},{pricesInHuf:true});
  assert.equal(safe.price,72.9);assert.equal(safe.condition,'');assert.equal(safe.building,'Tégla');assert.equal('street' in safe,false);assert.equal('id' in safe,false);assert.equal('latitude' in safe,false);
  const name=suggestEntityTitle('search',{type:'Lakás',locations:[city,district]});assert.ok(name.includes('Lakás'));assert.ok(name.includes('Debrecen'));assert.ok(name.includes('+1'));assert.ok(name.length<=70);
  for (const teaser of [...demoLanding().properties,...demoLanding().searches]) {assert.ok(teaser.prefill.locations.length);assert.equal('id' in teaser.prefill,false);assert.equal('addressDetails' in teaser.prefill,false);}
});

test('demo creation requests survive reload and another tab without duplicating or accepting changed payload',()=>{
  const storage=store(),first=createModel(storage),otherTab=createModel(storage),data={title:'Új keresési igény',locationIds:[city.id],maxPrice:80,minRooms:null};
  const before=first.getState().searches.length,saved=first.saveEntity('search',data,undefined,{creationRequestId:requestId});
  const replay=otherTab.saveEntity('search',{...data},undefined,{creationRequestId:requestId});assert.equal(replay.id,saved.id);assert.equal(otherTab.getState().searches.length,before+1);
  assert.equal(createModel(storage).saveEntity('search',data,undefined,{creationRequestId:requestId}).id,saved.id);
  assert.throws(()=>otherTab.saveEntity('search',{...data,maxPrice:81},undefined,{creationRequestId:requestId}),/másik kitöltés/);
  const raw=JSON.parse(storage.getItem(STORAGE_KEY));raw.userId='u1';storage.setItem(STORAGE_KEY,JSON.stringify(raw));
  const otherOwner=createModel(storage).saveEntity('search',data,undefined,{creationRequestId:requestId});assert.notEqual(otherOwner.id,saved.id);assert.equal(otherOwner.ownerId,'u1');
});

test('API sends creation identity on POST only and reads live stored sessions',async()=>{
  const calls=[];globalThis.fetch=async(url,options)=>{calls.push({url,options});return response({id:'saved-search',...JSON.parse(options.body)});};
  const api=new ApiModel({baseUrl:'https://api.example.hu',token:'token'}),data={title:'Keresés',locationIds:[city.id],maxPrice:80,minRooms:null};
  await api.saveEntity('search',data,undefined,{creationRequestId:requestId});assert.equal(JSON.parse(calls[0].options.body).creationRequestId,requestId);assert.equal(JSON.parse(calls[0].options.body).maxPrice,80000000);
  await assert.rejects(api.saveEntity('search',data,'existing',{creationRequestId:requestId}),/létrehozási/);
  const previousStorage=globalThis.localStorage,previousConfig=globalThis.OTTHONRA_CONFIG;globalThis.localStorage=store();globalThis.OTTHONRA_CONFIG={mode:'demo'};
  try {globalThis.localStorage.setItem(API_CONFIG_KEY,JSON.stringify({baseUrl:'https://api.example.hu',token:'first'}));assert.equal(getModel().token,'first');globalThis.localStorage.setItem(API_CONFIG_KEY,JSON.stringify({baseUrl:'https://api.example.hu',token:'second'}));assert.equal(getModel().token,'second');} finally {globalThis.localStorage=previousStorage;globalThis.OTTHONRA_CONFIG=previousConfig;}
});

test('last initiated login wins when older authentication responses arrive after a newer login',async()=>authScenario(async storage=>{
  const oldGate=deferred(),newGate=deferred();
  globalThis.fetch=async(url,options)=>{
    if(new URL(url).pathname==='/api/auth/login'){const identity=JSON.parse(options.body).email;await (identity==='old@example.hu'?oldGate:newGate).promise;return response({token:identity});}
    return authResponse(url,options);
  };
  const oldLogin=connectApi('https://api.example.hu','old@example.hu','old-password');
  const oldRejected=assert.rejects(oldLogin,error=>error.code==='AUTH_ATTEMPT_SUPERSEDED');
  const newLogin=connectApi('https://api.example.hu','new@example.hu','new-password');
  newGate.resolve();const newest=await newLogin;assert.equal(newest.token,'new@example.hu');
  oldGate.resolve();await oldRejected;
  assert.equal(getModel().token,'new@example.hu');assert.equal(JSON.parse(storage.getItem(API_CONFIG_KEY)).token,'new@example.hu');
  const marker=storage.getItem(AUTH_ATTEMPT_KEY);assert.ok(marker);assert.equal(marker.includes('@'),false);assert.equal(marker.includes('password'),false);
}));

test('an older login cannot become active while a newer initiated login is still pending',async()=>authScenario(async storage=>{
  const oldGate=deferred(),newGate=deferred();
  globalThis.fetch=async(url,options)=>{
    if(new URL(url).pathname==='/api/auth/login'){const identity=JSON.parse(options.body).email;await (identity==='old@example.hu'?oldGate:newGate).promise;return response({token:identity});}
    return authResponse(url,options);
  };
  const oldLogin=connectApi('https://api.example.hu','old@example.hu','old-password'),oldRejected=assert.rejects(oldLogin,error=>error.code==='AUTH_ATTEMPT_SUPERSEDED');
  const newLogin=connectApi('https://api.example.hu','new@example.hu','new-password');
  oldGate.resolve();await oldRejected;assert.equal(storage.getItem(API_CONFIG_KEY),null);
  newGate.resolve();assert.equal((await newLogin).token,'new@example.hu');assert.equal(getModel().token,'new@example.hu');
}));

test('logout invalidates a pending login even while authenticated account verification is delayed',async()=>authScenario(async storage=>{
  const verifying=deferred(),release=deferred();
  globalThis.fetch=async(url,options)=>{
    const path=new URL(url).pathname;
    if(path==='/api/auth/login')return response({token:'delayed@example.hu'});
    if(path==='/api/me'){verifying.resolve();await release.promise;}
    return authResponse(url,options);
  };
  const login=connectApi('https://api.example.hu','delayed@example.hu','test-password'),rejected=assert.rejects(login,error=>error.code==='AUTH_ATTEMPT_SUPERSEDED');
  await verifying.promise;const oldMarker=storage.getItem(AUTH_ATTEMPT_KEY);disconnectApi();assert.notEqual(storage.getItem(AUTH_ATTEMPT_KEY),oldMarker);
  release.resolve();await rejected;assert.equal(storage.getItem(API_CONFIG_KEY),null);assert.notEqual(getModel().mode,'api');
}));

test('an external session change also invalidates an older pending login without updating the auth nonce',async()=>authScenario(async storage=>{
  const verifying=deferred(),release=deferred();
  globalThis.fetch=async(url,options)=>{
    const path=new URL(url).pathname;
    if(path==='/api/auth/login')return response({token:'old@example.hu'});
    if(path==='/api/me'){verifying.resolve();await release.promise;}
    return authResponse(url,options);
  };
  const login=connectApi('https://api.example.hu','old@example.hu','test-password'),rejected=assert.rejects(login,error=>error.code==='AUTH_ATTEMPT_SUPERSEDED');
  await verifying.promise;const marker=storage.getItem(AUTH_ATTEMPT_KEY),newer=JSON.stringify({baseUrl:'https://api.example.hu',token:'external-newer-token'});storage.setItem(API_CONFIG_KEY,newer);
  release.resolve();await rejected;assert.equal(storage.getItem(API_CONFIG_KEY),newer);assert.equal(storage.getItem(AUTH_ATTEMPT_KEY),marker);assert.equal(getModel().token,'external-newer-token');
}));

test('anonymous API lookups and landing seeds use public endpoints without authentication',async()=>{
  const previousConfig=globalThis.OTTHONRA_CONFIG,previousLocation=globalThis.location,previousFetch=globalThis.fetch,calls=[];
  globalThis.OTTHONRA_CONFIG={mode:'api'};globalThis.location={origin:'https://otthonra.example.hu'};
  globalThis.fetch=async(url,options)=>{calls.push({url,options});return response(new URL(url).pathname.endsWith('/public/landing')?{properties:[{prefill:{locations:[city],type:'Lakás',price:72900000,area:64,rooms:3}}],searches:[{prefill:{locations:[city],type:'Lakás',minPrice:null,maxPrice:80000000,minRooms:null,maxRooms:3}}]}:{items:[city]});};
  try {
    assert.equal((await findPublicLocations('Debrecen',12,{kind:'property'}))[0].id,city.id);assert.deepEqual(await findPublicStreets('utca',city.id),[]);
    const landing=await fetchLanding();assert.equal(landing.properties[0].prefill.price,72.9);assert.equal(landing.searches[0].prefill.maxPrice,80);assert.equal(landing.searches[0].prefill.minPrice,null);
    assert.ok(calls.every(call=>!call.options.headers.Authorization));assert.ok(calls.some(call=>call.url.includes('/api/locations?')));assert.ok(calls.some(call=>call.url.includes('/api/streets?')));assert.ok(calls.every(call=>!call.url.includes('.gz')));
  } finally {globalThis.OTTHONRA_CONFIG=previousConfig;globalThis.location=previousLocation;globalThis.fetch=previousFetch;}
});
