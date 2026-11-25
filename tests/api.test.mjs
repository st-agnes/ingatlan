import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import {locations} from '../dist/locations.js';
import { ApiModel, API_CONFIG_KEY, connectApi, getModel, disconnectApi, hostedMode, deploymentEnvironment, fetchLanding, fetchPublicListing, publicListingFromApi, detectLandingRegion } from '../dist/api.js';

const creditsTarget={page:'credits',entityKind:null,entityId:null,propertyId:null,searchRequestId:null,matchId:null};
const exactAddress={street:'Fiktív teszt utca',houseNumber:'12',postalCode:'1234'};
const originalFetch = globalThis.fetch;
const originalStorage = globalThis.localStorage;
const originalRuntime = globalThis.OTTHONRA_CONFIG;
const originalLocation = globalThis.location;
afterEach(() => { globalThis.fetch = originalFetch; globalThis.localStorage = originalStorage;globalThis.OTTHONRA_CONFIG=originalRuntime;globalThis.location=originalLocation; });
const storage = () => {
  const values = new Map();
  return { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
};
const ids = {
  user: '11111111-1111-1111-1111-111111111111',
  property: '22222222-2222-2222-2222-222222222222',
  search: '33333333-3333-3333-3333-333333333333',
  match: '44444444-4444-4444-4444-444444444444'
};
const property = { id: ids.property, ownerId: 'other', title: 'Újlipótvárosi lakás', city: 'Budapest', district: 'XIII.', type: 'Lakás', price: 72900000, area: 64, rooms: 3, balcony: true, elevator: true, images: [], archived: false };
const search = { id: ids.search, ownerId: ids.user, title: 'Első közös otthonunk', city: 'Budapest', districts: ['XIII.'], type: 'Lakás', minPrice: 55000000, maxPrice: 85000000, minArea: 50, maxArea: 85, minRooms: 2, maxRooms: 4, balcony: false, elevator: false };
const profile = { id: ids.user, name: 'Nagy Anna', email: 'anna@example.hu', phone: '', credits: 24, activeKind: 'search', activeEntityId: ids.search };
const match = { id: ids.match, property, searchRequest: search, contact: { id: 'other', name: 'Kovács Péter', email: 'peter@example.hu', phone: '+36 30 555 0101' }, messages: [{ id: 'msg', matchId: ids.match, senderId: 'other', text: 'Szia!', createdAt: '2026-11-01T08:00:00Z' }], unread: 0 };
const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, text: async () => body == null ? '' : JSON.stringify(body) });
const adapter = () => new ApiModel({ baseUrl: 'https://api.example.hu', token: 'sample-token' });

// All requests are intercepted; these tests do not connect to the network.
function routes(values) {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    const path = new URL(url).pathname;
    calls.push({ path, ...options });
    assert.ok(path in values, `Unexpected API request: ${path}`);
    const value = values[path];
    return typeof value === 'function' ? value(options) : response(value);
  };
  return calls;
}
function accountRoutes(extra = {}) {
  return {
    '/api/me': profile,
    '/api/me/entities': { properties: [], searchRequests: [search], active: { kind: 'search', id: ids.search } },
    '/api/credits/ledger': [{ id: 'credit', amount: 24, description: 'Demó', createdAt: '2026-11-01T08:00:00Z' }],
    ...extra
  };
}

test('property form strings become correctly typed .NET JSON and prices round-trip in HUF', async () => {
  const calls = routes({ '/api/properties': options => response({ id: ids.property, ...JSON.parse(options.body) }, 201) });
  const result = await adapter().saveEntity('property', {...exactAddress,  title: 'Otthon', city: 'Budapest', district: 'XI.', type: 'Lakás', price: '72.9', area: '64.5', rooms: '2.5', floor: '3', balcony: false, elevator: 'false', images: ['https://images.example.hu/home.jpg'], ownerId: 'not-authoritative' });
  const body = JSON.parse(calls[0].body);
  assert.deepEqual([body.price, body.area, body.rooms, body.floor], [72900000, 64.5, 2.5, 3]);
  assert.equal(body.balcony, false);
  assert.equal(body.elevator, false);
  assert.equal('ownerId' in body, false);
  assert.equal(result.price, 72.9);
  assert.equal(body.locationId, 'district:Budapest:11');
  assert.equal(result.location.label, 'Budapest XI. kerület');
  assert.equal(calls[0].headers.Authorization, 'Bearer sample-token');
  await assert.rejects(adapter().saveEntity('property', {...exactAddress,  price: 'invalid', area: 5, rooms: 1 }), /érvényes szám/);
  await assert.rejects(adapter().saveEntity('property', {...exactAddress,  price: 5, area: 5, rooms: 1, floor: 1.5 }), /emelet|magasföldszint/);
  await assert.rejects(adapter().saveEntity('property', {...exactAddress,  price: 5, area: 5, rooms: 1, images: ['/assets/home.jpg'] }), /HTTPS/);
  assert.equal(calls.length, 1, 'invalid form data is rejected before sending');
});

test('search form serializes nullable bounds, district arrays, and boolean DTO fields', async () => {
  const calls = routes({ '/api/searches': options => response({ id: ids.search, ...JSON.parse(options.body) }, 201) });
  await adapter().saveEntity('search', { title: 'Keresés', city: 'Budapest', type: 'Lakás', districts: 'XI., XIII.', minPrice: '55', maxPrice: '85', minArea: '', maxArea: '85', minRooms: '2', maxRooms: '4', balcony: 'on', elevator: false });
  const body = JSON.parse(calls[0].body);
  assert.deepEqual(body.districts, ['XI.', 'XIII.']);
  assert.deepEqual(body.locationIds, ['district:Budapest:11', 'district:Budapest:13']);
  assert.deepEqual([body.minPrice, body.maxPrice, body.minArea, body.maxArea, body.minRooms, body.maxRooms], [55000000, 85000000, null, 85, 2, 4]);
  assert.equal(body.balcony, true);
  assert.equal(body.elevator, false);
});

test('authentication accepts accessToken and saves no password after verifying account routes', async () => {
  globalThis.localStorage = storage();
  const calls = routes(accountRoutes({ '/api/auth/login': { accessToken: 'verified-token', expiresIn: 43200, user: profile } }));
  const api = await connectApi('https://api.example.hu/api', ' anna@example.hu ', 'sample-password');
  assert.equal(api.mode, 'api');
  assert.equal(api.baseUrl, 'https://api.example.hu');
  assert.deepEqual(JSON.parse(calls[0].body), { email: 'anna@example.hu', password: 'sample-password' });
  const saved = JSON.parse(globalThis.localStorage.getItem(API_CONFIG_KEY));
  assert.deepEqual(saved, { baseUrl: 'https://api.example.hu', token: 'verified-token' });
  assert.equal(getModel().mode, 'api');
  disconnectApi();
  assert.equal(globalThis.localStorage.getItem(API_CONFIG_KEY), null);
  assert.notEqual(getModel().mode, 'api');
});

test('profile state maps active GUIDs and historical decision snapshots from HUF to UI units', async () => {
  routes(accountRoutes({ '/api/me/entities': { properties: [property], searchRequests: [search], active: { kind: 'search', id: ids.search }, decisions: [{ id: 'decision', actorKind: 'search', actorId: ids.search, propertyId: ids.property, searchRequestId: ids.search, liked: true, property, searchRequest: search }] } }));
  const state = await adapter().getState();
  assert.equal(state.user.id, ids.user);
  assert.equal(state.credits, 24);
  assert.deepEqual(state.active, { kind: 'search', id: ids.search });
  assert.equal(state.properties[0].price, 72.9);
  assert.equal(state.properties[0].locationId, 'district:Budapest:13');
  assert.deepEqual(state.searches[0].locationIds, ['district:Budapest:13']);
  assert.equal(state.searches[0].maxPrice, 85);
  assert.equal(state.decisions[0].property.price, 72.9);
  assert.equal(state.decisions[0].search.minPrice, 55);
  assert.equal(state.decisions[0].searchId, ids.search);
  assert.equal(state.decisions[0].liked, true);
  assert.equal(state.ledger[0].amount, 24);
});

test('feed keeps GUID pairs and resolves matchId to contact and message DTOs after a decision', async () => {
  const calls = routes(accountRoutes({
    '/api/feed': { items: [{ property: { ...property, owner: { email: 'private@example.hu' } }, searchRequest: search, propertyId: ids.property, searchRequestId: ids.search, compatibilityScore: 98, reasons: ['Árkereten belül'], likedYou: true }], sellerLikeCost: 2 },
    '/api/decisions': { matchId: ids.match, charged: 0, credits: 24 },
    '/api/matches': [match]
  }));
  const api = adapter();
  const card = (await api.feed())[0];
  assert.equal(card.price, 72.9);
  assert.equal(card.score, 98);
  assert.equal(card.likedYou, true);
  assert.deepEqual(card.pair, { propertyId: ids.property, searchId: ids.search });
  assert.equal('owner' in card, false);
  assert.equal('email' in card, false);
  const result = await api.decide(card, true);
  assert.deepEqual(JSON.parse(calls.find(call => call.path === '/api/decisions').body), { propertyId: ids.property, searchRequestId: ids.search, liked: true });
  assert.equal(result.charged, 0);
  assert.equal(result.matchId, ids.match);
  assert.equal(result.match.id, ids.match);
  assert.equal(result.match.partner.email, 'peter@example.hu');
  assert.equal(result.match.messages[0].senderId, 'other');
  assert.equal(result.match.search.id, ids.search);
});

test('checkout uses numeric credit amount and accepts only a secure redirect URL', async () => {
  const calls = routes({ '/api/credits/checkout': { checkoutUrl: 'https://checkout.stripe.com/c/pay/example' } });
  const api = adapter();
  assert.deepEqual(await api.createCheckout('50'), { checkoutUrl: 'https://checkout.stripe.com/c/pay/example' });
  assert.deepEqual(JSON.parse(calls[0].body), { amount: 50 });
  await assert.rejects(api.createCheckout('5.5'), /pozitív egész/);
  assert.equal(calls.length, 1);
  routes({ '/api/credits/checkout': { checkoutUrl: 'javascript:alert(1)' } });
  await assert.rejects(api.createCheckout(50), /HTTPS/);
});

test('expired-session and network failures surface while preserving configured API mode', async () => {
  globalThis.localStorage = storage();
  globalThis.localStorage.setItem(API_CONFIG_KEY, JSON.stringify({ baseUrl: 'https://api.example.hu', token: 'expired' }));
  routes({ '/api/me': () => response({ message: 'Expired' }, 401), '/api/me/entities': {}, '/api/credits/ledger': [] });
  await assert.rejects(getModel().getState(), /munkameneted lejárt/);
  assert.equal(getModel().mode, 'api');
  globalThis.fetch = async () => { throw new TypeError('Network error'); };
  await assert.rejects(getModel().getState(), /API nem érhető el/);
  assert.equal(getModel().mode, 'api');
  assert.ok(globalThis.localStorage.getItem(API_CONFIG_KEY));
});

test('a failed connection check never replaces a previously working saved connection', async () => {
  globalThis.localStorage = storage();
  const original = JSON.stringify({ baseUrl: 'https://old.example.hu', token: 'old-token' });
  globalThis.localStorage.setItem(API_CONFIG_KEY, original);
  routes(accountRoutes({ '/api/auth/login': { accessToken: 'new-token' }, '/api/me': () => response({ message: 'Unavailable' }, 503) }));
  await assert.rejects(connectApi('https://api.example.hu', 'anna@example.hu', 'sample-password'), /Unavailable/);
  assert.equal(globalThis.localStorage.getItem(API_CONFIG_KEY), original);
});

test('mixed canonical locations and blank optional limits round-trip without changing their meaning', async () => {
  const calls = routes({ '/api/searches': options => response({ id: ids.search, ...JSON.parse(options.body) }, 201) });
  const selected = ['district:Budapest:5', 'district:Budapest:9', 'city:Solymár', 'city:Pilisvörösvár'];
  const result = await adapter().saveEntity('search', { title: 'Több helyen keresek', locationIds: selected, city: 'Szeged', type: 'Ház', minPrice: '', maxPrice: '99.9', minArea: '60', maxArea: null, minRooms: '2', maxRooms: '' });
  const body = JSON.parse(calls[0].body);
  assert.deepEqual(body.locationIds, selected);
  assert.deepEqual(body.districts, ['V.', 'IX.']);
  assert.equal(body.city, 'Budapest');
  assert.deepEqual([body.minPrice, body.maxPrice, body.maxArea, body.maxRooms], [null, 99900000, null, null]);
  assert.deepEqual(result.locationIds, selected);
  assert.deepEqual(result.locations.map(location => location.label), ['Budapest V. kerület', 'Budapest IX. kerület', 'Solymár', 'Pilisvörösvár']);
  assert.deepEqual([result.minPrice, result.maxPrice, result.maxArea, result.maxRooms], [null, 99.9, null, null]);
  const towns = ['city:Debrecen', 'city:Hajdúszoboszló', 'city:Hajdúsámson'];
  const townResult = await adapter().saveEntity('search', { title: 'Hajdúsági otthon', locationIds: towns, maxPrice: 80 });
  assert.deepEqual(townResult.locationIds, towns);
  assert.deepEqual(townResult.districts, []);
});

test('unknown and unselected canonical locations cannot be posted, even alongside valid legacy fields', async () => {
  const calls = routes({});
  const data = { title: 'Hibás választás', city: 'Budapest', price: 70, area: 60, rooms: 3 };
  for (const locationId of ['', 'city:Nemlétező']) await assert.rejects(adapter().saveEntity('property', {...exactAddress,  ...data, locationId }), /találati listából/);
  for (const locationIds of [[], ['city:Nemlétező'], ['city:Debrecen', 'city:Nemlétező']]) await assert.rejects(adapter().saveEntity('search', { ...data, locationIds }), /találati listából/);
  await assert.rejects(adapter().saveEntity('search', { title: 'Nincs kiválasztva' }), /találati listából/);
  assert.equal(calls.length, 0);
});

test('house plot area is required on save and is cleared for apartments', async () => {
  const calls = routes({ '/api/properties': options => response({ id: ids.property, ...JSON.parse(options.body) }, 201) });
  const data = { title: 'Kertes ház', locationId: 'city:Solymár', type: 'Ház', price: '105.5', area: '115', rooms: '4', lotArea: '720.5' };
  const house = await adapter().saveEntity('property', {...exactAddress,...data});
  assert.equal(JSON.parse(calls[0].body).lotArea, 720.5);
  assert.equal(house.lotArea, 720.5);
  assert.equal(house.locationId, 'city:Solymár');
  for (const lotArea of ['',null,undefined]) await assert.rejects(adapter().saveEntity('property', {...exactAddress,  ...data, lotArea }), /telekméret/);
  const apartment = await adapter().saveEntity('property', {...exactAddress,  ...data, type: 'Lakás' });
  assert.equal(apartment.lotArea, null);
  await assert.rejects(adapter().saveEntity('property', {...exactAddress,  ...data, lotArea: 0 }), /telekméret/);
  await assert.rejects(adapter().saveEntity('property', {...exactAddress,  ...data, lotArea: 'hibás' }), /érvényes szám/);
  assert.equal(calls.length, 2);
});

test('canonical location DTO objects work when reading an API response without legacy fields', async () => {
  routes(accountRoutes({ '/api/me/entities': { properties: [{ ...property, city: undefined, district: undefined, location: { id: 'district:Budapest:9' } }], searchRequests: [{ ...search, city: undefined, districts: undefined, locations: [{ id: 'city:Debrecen' }, { id: 'city:Hajdúszoboszló' }], minPrice: null, maxArea: null, maxRooms: null }] } }));
  const state = await adapter().getState();
  assert.equal(state.properties[0].locationId, 'district:Budapest:9');
  assert.equal(state.properties[0].city, 'Budapest');
  assert.deepEqual(state.searches[0].locationIds, ['city:Debrecen', 'city:Hajdúszoboszló']);
  assert.deepEqual([state.searches[0].minPrice, state.searches[0].maxArea, state.searches[0].maxRooms], [null, null, null]);
});

function hostedSession(){
  globalThis.OTTHONRA_CONFIG={mode:'api',environment:'test'};
  globalThis.location={origin:'https://test.example.hu'};
  globalThis.localStorage=storage();
}

test('hosted runtime starts unauthenticated without falling back to browser demo data',()=>{
  hostedSession();let calls=0;globalThis.fetch=async()=>{calls++;throw new Error('Guest must not fetch before login');};
  assert.equal(hostedMode(),true);assert.equal(deploymentEnvironment(),'test');
  assert.equal(getModel(),null);assert.equal(disconnectApi(),null);assert.equal(calls,0);
});

test('hosted sessions cannot send a saved bearer token to another origin',()=>{
  hostedSession();
  globalThis.localStorage.setItem(API_CONFIG_KEY,JSON.stringify({baseUrl:'https://foreign.example.hu',token:'foreign-token'}));
  assert.equal(getModel(),null);
  globalThis.localStorage.setItem(API_CONFIG_KEY,JSON.stringify({baseUrl:'https://test.example.hu',token:'own-token'}));
  assert.equal(getModel().baseUrl,'https://test.example.hu');assert.equal(getModel().token,'own-token');
});

test('hosted login rejects a different API address before sending credentials',async()=>{
  hostedSession();const calls=routes({});
  await assert.rejects(connectApi('https://foreign.example.hu','anna@example.hu','password1234'),/saját webcímén/);
  assert.equal(calls.length,0);assert.equal(globalThis.localStorage.getItem(API_CONFIG_KEY),null);
});

test('hosted registration and logout use a verified same-origin API session',async()=>{
  hostedSession();
  const calls=routes(accountRoutes({'/api/auth/register':{accessToken:'new-user-token'}}));
  const api=await connectApi(globalThis.location.origin,'anna@example.hu','password1234',{name:'Teszt Anna',phone:' +36 30 555 0199 '});
  assert.equal(api.baseUrl,globalThis.location.origin);assert.equal(api.mode,'api');
  assert.deepEqual(JSON.parse(calls[0].body),{name:'Teszt Anna',phone:'+36 30 555 0199',accountType:'private',email:'anna@example.hu',password:'password1234'});
  const saved=JSON.parse(globalThis.localStorage.getItem(API_CONFIG_KEY));
  assert.deepEqual(saved,{baseUrl:'https://test.example.hu',token:'new-user-token'});
  assert.equal(getModel().mode,'api');assert.equal(disconnectApi(),null);assert.equal(getModel(),null);
});

test('hosted API errors preserve HTTP status for login expiry and never downgrade to demo',async()=>{
  hostedSession();globalThis.localStorage.setItem(API_CONFIG_KEY,JSON.stringify({baseUrl:globalThis.location.origin,token:'expired'}));
  routes(accountRoutes({'/api/me':()=>response({message:'Expired'},401)}));
  await assert.rejects(getModel().getState(),error=>error.status===401&&/lejárt/.test(error.message));
  assert.equal(getModel().mode,'api');
  routes(accountRoutes({'/api/me':()=>response({message:'Unavailable'},503)}));
  await assert.rejects(getModel().getState(),error=>error.status===503&&error.message==='Unavailable');
  assert.equal(getModel().mode,'api');
});

test('a new authenticated account without an active entity has an empty feed',async()=>{
  const calls=routes(accountRoutes({'/api/me/entities':{properties:[],searchRequests:[],active:{kind:'search',id:null}}}));
  const api=adapter();assert.deepEqual(await api.feed(),[]);
  assert.equal(calls.some(call=>call.path==='/api/feed'),false);
});

test('all optional seller details round-trip through DTOs preserving null, false, ground floor and modern or legacy text',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201)});
 const result=await adapter().saveEntity('property',{...exactAddress,title:'Részletes lakás',locationId:'district:Budapest:13',type:'Lakás',price:78,area:68,rooms:3,condition:'Jó állapotú',building:'Tégla',constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m feletti',floor:'0',heatingType:'Hőszivattyú',secondaryHeatingType:'Klíma',insulated:'false',energyRating:'BB',airConditioning:'true',solarPanels:null,parkingType:'Udvari beálló'});
 const body=JSON.parse(calls[0].body);
 assert.deepEqual([body.condition,body.building,body.floor],['Jó','Tégla',0]);
 assert.deepEqual([body.insulated,body.airConditioning,body.solarPanels],[false,true,null]);
 for(const field of ['condition','building','constructionAge','view','ceilingHeight','floor','heatingType','insulated','energyRating','airConditioning','solarPanels','parkingType'])assert.deepEqual(result[field],body[field],field);
 const blank=await adapter().saveEntity('property',{...exactAddress,title:'Ismeretlen részletek',locationId:'city:Debrecen',type:'Lakás',price:40,area:50,rooms:2,insulated:'',airConditioning:'',solarPanels:''});
 assert.deepEqual([blank.condition,blank.building,blank.floor,blank.insulated,blank.airConditioning,blank.solarPanels],['','',null,null,null,null]);
});

test('multiselect search attributes serialize as deduplicated arrays and can all be cleared',async()=>{
 const calls=routes({'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 const result=await adapter().saveEntity('search',{title:'Szűrt keresés',locationIds:['city:Budapest'],conditions:['Jó','Felújított','Jó'],buildings:['Panel','Tégla'],constructionAges:['10 évnél fiatalabb','10–30 év közötti'],views:['Kertre néző','Panorámás'],ceilingHeight:'3 m alatti',floors:['-1','0','11']});
 const body=JSON.parse(calls[0].body);
 assert.deepEqual(body.conditions,['Jó','Új/felújított']);assert.deepEqual(body.buildings,['Panel','Tégla']);assert.deepEqual(body.floors,[-1,0,9]);
 for(const field of ['conditions','buildings','constructionAges','views','ceilingHeight','floors'])assert.deepEqual(result[field],body[field],field);
 const cleared=await adapter().saveEntity('search',{...result,conditions:[],buildings:[],constructionAges:[],views:[],ceilingHeight:'',floors:[]});
 assert.deepEqual([cleared.conditions,cleared.buildings,cleared.constructionAges,cleared.views,cleared.floors],[[],[],[],[],[]]);assert.equal(cleared.ceilingHeight,'');
});

test('new invalid enums and malformed selections are rejected before sending while an update can preserve server-owned legacy labels',async()=>{
 const calls=routes({['/api/properties/'+ids.property]:options=>response({id:ids.property,...JSON.parse(options.body)})});
 const base={title:'Meglévő lakás',locationId:'city:Budapest',price:50,area:60,rooms:3};
 await assert.rejects(adapter().saveEntity('property',{...exactAddress,...base,view:'Ismeretlen'}),/Érvénytelen/);
 await assert.rejects(adapter().saveEntity('property',{...exactAddress,...base,condition:'Ismeretlen'}),/Érvénytelen/);
 await assert.rejects(adapter().saveEntity('property',{...exactAddress,...base,insulated:'talán'}),/igen, nem/);
 await assert.rejects(adapter().saveEntity('search',{title:'Hibás keresés',locationIds:['city:Budapest'],conditions:'Jó'}),/listaként/);
 await assert.rejects(adapter().saveEntity('search',{title:'Hibás keresés',locationIds:['city:Budapest'],floors:[12]}),/Érvénytelen/);
 assert.equal(calls.length,0);
 const updated=await adapter().saveEntity('property',{...exactAddress,...base,condition:'Régi egyedi állapot',building:'Régi egyedi szerkezet'},ids.property);
 assert.equal(updated.condition,'Régi egyedi állapot');assert.equal(updated.building,'Régi egyedi szerkezet');assert.equal(calls.length,1);
});


test('area searches post stable compact IDs and retain counted labels on API reads',async()=>{
 const selected=['area:Budapest','area:Debrecen','district:Budapest:5','city:Szeged'];
 const calls=routes({'/api/searches':options=>response({...search,...JSON.parse(options.body),id:ids.search},201)});
 const saved=await adapter().saveEntity('search',{title:'Nagyvárosok és környékük',locationIds:selected,maxPrice:100});
 const body=JSON.parse(calls[0].body);assert.deepEqual(body.locationIds,selected);assert.equal(body.locationIds.length,4);
 assert.deepEqual(saved.locationIds,selected);assert.equal(saved.locations[0].kind,'area');assert.equal(saved.locations[0].settlementCount,81);
 assert.equal(saved.locations[1].settlementCount,13);assert.match(saved.locations[1].label,/Debrecen és környéke \(13 település\)/);
});

test('the API adapter rejects area property locations and over fifty choices before a request',async()=>{
 const calls=routes({});const api=adapter();const data={title:'Lakás pontos településsel',locationId:'area:Budapest',city:'Budapest',price:60,area:60,rooms:3};
 await assert.rejects(api.saveEntity('property',{...exactAddress,...data}),/találati listából/);
 const towns=locations.filter(value=>value.kind==='city').slice(0,50).map(value=>value.id);
 await assert.rejects(api.saveEntity('search',{title:'Túl sok hely',locationIds:['area:Budapest',...towns]}),/találati listából/);
 assert.equal(calls.length,0);
});

test('a property response with an invalid area ID does not become an exact town location',async()=>{
 routes(accountRoutes({'/api/me/entities':{properties:[{...property,locationId:'area:Budapest',city:'Budapest'}],searchRequests:[{...search,locationIds:['area:Budapest']}],active:{kind:'search',id:ids.search}}}));
 const state=await adapter().getState();assert.equal(state.properties[0].location,null);assert.equal(state.properties[0].locationId,'area:Budapest');
 assert.equal(state.searches[0].locations[0].kind,'area');assert.equal(state.searches[0].locations[0].settlementCount,81);
});

test('new seller details use typed arrays and explicit room composition throughout API round trips',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201)});
 const saved=await adapter().saveEntity('property',{...exactAddress,title:'Fél szobás lakás',locationId:'city:Debrecen',type:'Lakás',price:'65.5',area:'80',wholeRooms:'2',halfRooms:'3',heatingType:'Gázkazán',secondaryHeatingType:'Kandalló',parkingTypes:['Garázs','Udvari beálló','Garázs']});
 const body=JSON.parse(calls[0].body);
 assert.deepEqual([body.wholeRooms,body.halfRooms,body.rooms],[2,3,3.5]);
 assert.deepEqual([saved.wholeRooms,saved.halfRooms,saved.rooms],[2,3,3.5]);
 assert.deepEqual(body.parkingTypes,['Garázs','Udvari beálló']);assert.deepEqual(saved.parkingTypes,body.parkingTypes);
 assert.equal(saved.secondaryHeatingType,'Kandalló');
 const legacy=await adapter().saveEntity('property',{...exactAddress,title:'Régi API adat',locationId:'city:Debrecen',price:55,area:50,rooms:3.2});
 const legacyBody=JSON.parse(calls[1].body);
 assert.deepEqual([legacyBody.rooms,legacyBody.wholeRooms,legacyBody.halfRooms],[3.2,null,null]);
 assert.deepEqual([legacy.rooms,legacy.wholeRooms,legacy.halfRooms],[3.2,null,null]);
});

test('legacy-only API updates leave explicit composition to the server and allow unchanged public legacy descriptions',async()=>{
 const calls=routes({['/api/properties/'+ids.property]:options=>response({id:ids.property,...JSON.parse(options.body)})});
 const updated=await adapter().saveEntity('property',{...exactAddress,title:'Változatlan részletek',locationId:'city:Debrecen',price:55,area:50,rooms:3.5,heatingType:'Hőszivattyú és padlófűtés',parkingType:'Régi garázs, kapubeállóval'},ids.property);
 const body=JSON.parse(calls[0].body);
 assert.deepEqual([body.wholeRooms,body.halfRooms],[null,null],'do not invent a different breakdown for old-client updates');
 assert.equal(updated.heatingType,'Hőszivattyú és padlófűtés');assert.deepEqual(updated.parkingTypes,['Régi garázs, kapubeállóval']);
});

test('invalid counts, negative numeric values and newly introduced heating or parking choices do not reach the API',async()=>{
 const calls=routes({}),api=adapter(),base={title:'Érvényes lakás',locationId:'city:Debrecen',price:55,area:50,wholeRooms:2,halfRooms:1};
 for(const changes of [{price:-1},{area:-1},{wholeRooms:-1},{halfRooms:-1},{halfRooms:1.5},{wholeRooms:0,halfRooms:0},{rooms:4},{rooms:-1},{heatingType:'Új egyedi fűtés'},{secondaryHeatingType:'Új egyedi fűtés'},{parkingTypes:['Ismeretlen']},{parkingTypes:['Garázs',null]}])await assert.rejects(api.saveEntity('property',{...exactAddress,...base,...changes}));
 for(const key of ['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms'])await assert.rejects(api.saveEntity('search',{title:'Hibás keresés',locationIds:['city:Debrecen'],[key]:-1}));
 await assert.rejects(api.saveEntity('search',{title:'Hibás fűtés',locationIds:['city:Debrecen'],heatingTypes:['Ismeretlen']}));
 assert.equal(calls.length,0);
});

test('house API saves remove hidden controls while search heating remains an optional multi-selection',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201),'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 const house=await adapter().saveEntity('property',{...exactAddress,title:'Kertes ház',locationId:'city:Solymár',type:'Ház',price:95,area:110,wholeRooms:4,halfRooms:0,lotArea:700,floor:'invalid',balcony:true,elevator:true});
 assert.deepEqual([house.floor,house.balcony,house.elevator],[null,null,false]);
 const saved=await adapter().saveEntity('search',{title:'Házat keresünk',locationIds:['city:Solymár'],type:'Ház',floors:[3],balcony:true,elevator:true,heatingTypes:['Gázkazán','Klíma','Gázkazán'],minRooms:2.5,maxRooms:4.5});
 assert.deepEqual([saved.floors,saved.balcony,saved.elevator],[[],false,false]);
 assert.deepEqual(saved.heatingTypes,['Gázkazán / cirkó','Fűtő klíma']);
 assert.deepEqual([saved.minRooms,saved.maxRooms],[2.5,4.5]);
 const body=JSON.parse(calls[1].body);assert.deepEqual(body.heatingTypes,saved.heatingTypes);
});

test('agent declarations register explicitly while invalid choices never send credentials',async()=>{
 globalThis.localStorage=storage();
 const calls=routes(accountRoutes({'/api/auth/register':{accessToken:'registered-agent-token'},'/api/me':{...profile,accountType:'agent'}}));
 const api=await connectApi('https://api.example.hu','agent@example.hu','password1234',{name:'Közvetítő Anna',phone:'+36 30 555 0199',accountType:'agent'});
 assert.equal(JSON.parse(calls[0].body).accountType,'agent');assert.equal((await api.getState()).user.accountType,'agent');assert.equal((await api.getState()).likeCost,1);
 const before=calls.length;for(const accountType of ['',false,'unknown'])await assert.rejects(connectApi('https://api.example.hu','agent@example.hu','password1234',{name:'Közvetítő Anna',accountType}),/fióktípust/);
 assert.equal(calls.length,before);
});

test('API owner metadata persists through own lists, public feeds, history and matches without using the viewer account type',async()=>{
 const agentProperty={...property,ownerAccountType:'agent',ownerFirstName:'Péter'},privateSearch={...search,ownerAccountType:'private',ownerFirstName:'Anna'};
 routes(accountRoutes({'/api/me':{...profile,accountType:'agent'},'/api/me/entities':{properties:[agentProperty],searchRequests:[privateSearch],reportedOwnerIds:['other','other'],active:{kind:'search',id:ids.search},decisions:[{id:'choice',actorId:ids.search,actorKind:'search',propertyId:ids.property,searchRequestId:ids.search,property:agentProperty,searchRequest:privateSearch}]},'/api/feed':{likeCost:1,items:[{property:agentProperty,searchRequest:privateSearch}]},'/api/matches':[{...match,property:agentProperty,searchRequest:privateSearch,contact:{...match.contact,accountType:'agent'}}]}));
 const api=adapter(),state=await api.getState();assert.equal(state.user.accountType,'agent');assert.equal(state.likeCost,1);assert.deepEqual(state.reportedOwnerIds,['other']);
 assert.equal(state.properties[0].ownerAccountType,'agent');assert.equal(state.searches[0].ownerAccountType,'private');assert.equal(state.decisions[0].property.ownerAccountType,'agent');assert.equal(state.decisions[0].search.ownerAccountType,'private');
 const card=(await api.feed())[0];assert.equal(card.ownerAccountType,'agent');assert.equal(card.ownerFirstName,'Péter');assert.equal(state.searches[0].ownerFirstName,'Anna');assert.equal(state.decisions[0].property.ownerFirstName,'Péter');assert.equal('email' in card,false);assert.equal('phone' in card,false);
 const result=(await api.matches())[0];assert.equal(result.partner.accountType,'agent');assert.equal(result.property.ownerAccountType,'agent');assert.equal(result.search.ownerAccountType,'private');assert.equal(result.property.ownerFirstName,'Péter');
});

test('legacy API responses retain private/free defaults and no-active accounts have no like cost',async()=>{
 routes(accountRoutes());let state=await adapter().getState();assert.equal(state.user.accountType,'private');assert.equal(state.likeCost,0);assert.deepEqual(state.reportedOwnerIds,[]);
 routes(accountRoutes({'/api/me':{...profile,accountType:'agent',activeKind:null,activeEntityId:null},'/api/me/entities':{properties:[],searchRequests:[],active:null}}));state=await adapter().getState();assert.equal(state.likeCost,0);
 routes(accountRoutes({'/api/me':{...profile,accountType:'agent'},'/api/me/entities':{properties:[property],searchRequests:[],active:{kind:'property',id:ids.property}}}));state=await adapter().getState();assert.equal(state.likeCost,2);assert.equal(state.properties[0].ownerAccountType,'private','a viewer declaration cannot label another owner');
});

test('report requests use source entities only and preserve idempotent acknowledgements and retryable API failures',async()=>{
 const receipt={id:'receipt',reported:true,reportedOwnerId:'other',alreadyReported:false};let sent=0;
 const calls=routes({'/api/reports':options=>{sent++;return response({...receipt,alreadyReported:sent>1},sent===1?201:200);}}),api=adapter();
 assert.deepEqual(await api.reportAccount('property',ids.property),receipt);assert.deepEqual(JSON.parse(calls[0].body),{entityKind:'property',entityId:ids.property,reason:'suspected_agent'});
 assert.equal((await api.reportAccount('search',ids.search)).alreadyReported,true);assert.equal('createdAt' in receipt,false);
 const before=calls.length;for(const [kind,id] of [['user','other'],['property',''],['search',null]])await assert.rejects(api.reportAccount(kind,id),/jelentési profil/);assert.equal(calls.length,before);
 routes({'/api/reports':()=>response({message:'Átmeneti hiba'},503)});await assert.rejects(api.reportAccount('property',ids.property),error=>error.status===503&&error.message==='Átmeneti hiba');
});

test('owner declarations cannot be set through property or search save payloads or profile updates',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201),'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201),'/api/me':options=>response({...profile,...JSON.parse(options.body)})});
 const api=adapter();await api.saveEntity('property',{...exactAddress,title:'Saját ingatlan',locationId:'city:Debrecen',price:50,area:50,rooms:2,ownerAccountType:'agent'});
 await api.saveEntity('search',{title:'Saját keresés',locationIds:['city:Debrecen'],ownerAccountType:'agent'});await api.updateProfile({name:'Nagy Anna',email:'anna@example.hu',phone:'+36 30 555 0199',accountType:'agent'});
 for(const call of calls){const body=JSON.parse(call.body);assert.equal('ownerAccountType' in body,false);assert.equal('accountType' in body,false);}
});

test('report reasons and contextual summaries round-trip without exposing audit timestamps',async()=>{
 const calls=routes(accountRoutes({'/api/me/entities':{properties:[],searchRequests:[search],active:{kind:'search',id:ids.search},reportedOwnerIds:['other'],reportedEntities:[{entityKind:'property',entityId:ids.property,reason:'misleading_content',createdAt:'PRIVATE-TIME',reporterId:'PRIVATE-REPORTER'},{entityKind:'property',entityId:ids.property,reason:'misleading_content'},{entityKind:'user',entityId:'other',reason:'other_violation'}]},'/api/reports':options=>response({id:'receipt',reported:true,reportedOwnerId:'other',alreadyReported:false},201)}));
 const api=adapter(),state=await api.getState();assert.deepEqual(state.reportedEntities,[{entityKind:'property',entityId:ids.property,reason:'misleading_content'}]);assert.equal(JSON.stringify(state).includes('PRIVATE-TIME'),false);assert.equal(JSON.stringify(state).includes('PRIVATE-REPORTER'),false);
 await api.reportAccount('property',ids.property,'misleading_content');assert.deepEqual(JSON.parse(calls.at(-1).body),{entityKind:'property',entityId:ids.property,reason:'misleading_content'});
 await api.reportAccount('search',ids.search,'other_violation');assert.equal(JSON.parse(calls.at(-1).body).reason,'other_violation');const before=calls.length;
 for(const reason of ['',false,'unknown'])await assert.rejects(api.reportAccount('property',ids.property,reason),/jelentési ok/);assert.equal(calls.length,before);
});

test('incoming API pages preserve server-active context and handled status while exposing only public candidate fields',async()=>{
 const incoming={active:{kind:'search',id:ids.search},total:3,offset:1,limit:2,hasMore:false,likeCost:1,items:[{property:{...property,ownerAccountType:'agent',address:'Private street',email:'hidden@example.test',phone:'+36 30 0000000'},searchRequest:search,propertyId:ids.property,searchRequestId:ids.search,likedAt:'2026-11-07T12:00:00Z',likedYou:true,myDecision:'passed',matchId:null,compatible:false,compatibilityScore:95,reasons:['Megfelelő méret']},{property,searchRequest:search,propertyId:ids.property,searchRequestId:ids.search,likedAt:'2026-11-06T12:00:00Z',myDecision:'liked',matchId:ids.match,compatible:true}]};
 let requested;routes({'/api/incoming-likes':options=>{requested=options;return response(incoming);}});const api=adapter();api.active={kind:'property',id:'stale-active'};
 const page=await api.incomingLikes({offset:1,limit:2});assert.deepEqual(page.active,{kind:'search',id:ids.search});assert.deepEqual([page.total,page.offset,page.limit,page.hasMore,page.likeCost],[3,1,2,false,1]);assert.equal(page.items.length,2);
 const item=page.items[0];assert.equal(item.kind,'property');assert.deepEqual(item.pair,{propertyId:ids.property,searchId:ids.search});assert.equal(item.address,'');assert.equal(item.ownerAccountType,'agent');assert.equal(item.myDecision,'passed');assert.equal(item.compatible,false);assert.equal(item.likedAt,incoming.items[0].likedAt);assert.equal('phone' in item,false);assert.equal('email' in item,false);assert.equal('contact' in item,false);assert.equal(page.items[1].matchId,ids.match);assert.equal(page.items[1].myDecision,'liked');assert.equal(requested.method,'GET');
 const before=JSON.stringify(page);item.title='Tampered';assert.equal(JSON.stringify(incoming).includes('Tampered'),false);assert.ok(before.includes('Újlipótvárosi lakás'));
});

test('incoming pagination uses encoded query parameters, validates before requests and retains empty active state',async()=>{
 const calls=[];globalThis.fetch=async(url,options)=>{calls.push({url,options});return response({active:null,items:[],total:0,offset:10,limit:5,hasMore:false,likeCost:0});};
 const api=adapter();assert.deepEqual(await api.incomingLikes({offset:10,limit:5}),{active:null,items:[],total:0,offset:10,limit:5,hasMore:false,likeCost:0});const url=new URL(calls[0].url);assert.equal(url.pathname,'/api/incoming-likes');assert.equal(url.searchParams.get('offset'),'10');assert.equal(url.searchParams.get('limit'),'5');
 for(const options of [{offset:-1},{offset:1000001},{offset:'1'},{limit:0},{limit:101}])await assert.rejects(api.incomingLikes(options),/lapozási/);assert.equal(calls.length,1);
});

test('notification pages map only recipient-safe fields, retain pagination and expose the profile unread count',async()=>{
 const notification={id:'refund-notification',kind:'like_refund',amount:2,text:'2 kredit visszatérítve.',decisionId:'paid-decision',createdAt:'2026-11-15T12:00:00Z',readAt:null,userId:'PRIVATE-OWNER',privateField:'PRIVATE-AUDIT'};
 const calls=routes(accountRoutes({'/api/me':{...profile,unreadNotificationCount:3},'/api/notifications':{items:[notification],total:8,unreadCount:3,offset:2,limit:1,hasMore:true}}));
 const api=adapter();assert.equal((await api.getState()).unreadNotificationCount,3);
 const page=await api.notifications({offset:2,limit:1});
 assert.deepEqual(page,{items:[{id:notification.id,kind:'like_refund',amount:2,text:notification.text,decisionId:'paid-decision',feedbackPackageId:null,createdAt:notification.createdAt,readAt:null,target:creditsTarget}],total:8,unreadCount:3,offset:2,limit:1,hasMore:true});
 assert.equal(JSON.stringify(page).includes('PRIVATE-'),false);
 const request=calls.find(call=>call.path==='/api/notifications');assert.equal(request.headers.Authorization,'Bearer sample-token');
 const before=calls.length;for(const options of [{offset:-1},{limit:0},{limit:101}])await assert.rejects(api.notifications(options),/lapozási/);assert.equal(calls.length,before);
});

test('notification read calls are authenticated and encoded, preserve the server timestamp, and surface access failures',async()=>{
 const item={id:'notice/id',kind:'like_refund',amount:1,text:'Visszatérítés',decisionId:'decision',createdAt:'2026-11-15T12:00:00Z',readAt:'2026-11-16T12:00:00Z'};
 const calls=routes({'/api/notifications/notice%2Fid/read':item}),api=adapter();
 assert.deepEqual(await api.markNotificationRead('notice/id'),{...item,feedbackPackageId:null,target:creditsTarget});assert.equal(calls[0].method,'PUT');assert.equal(calls[0].headers.Authorization,'Bearer sample-token');assert.equal(calls[0].body,undefined);
 for(const id of ['',null,1])await assert.rejects(api.markNotificationRead(id),/értesítés/);assert.equal(calls.length,1);
 routes({'/api/notifications/unknown/read':()=>response({message:'Az értesítés nem található.'},404)});
 await assert.rejects(api.markNotificationRead('unknown'),error=>error.status===404&&/nem található/.test(error.message));
});

test('notification context opens the exact inactive-profile like without loading state or leaking private source fields',async()=>{
 const target={page:'incoming',entityKind:'search',entityId:ids.search,propertyId:ids.property,searchRequestId:ids.search,matchId:null};
 const notice={id:'notice/id',kind:'incoming_like',text:'Új kedvelés',createdAt:'2026-11-19T10:00:00Z',target,eventKey:'PRIVATE-RECEIPT',userId:'PRIVATE-RECIPIENT'};
 const raw={notification:notice,target:{...target,privateField:'PRIVATE-TARGET'},available:true,canActivate:true,
  item:{propertyId:ids.property,searchRequestId:ids.search,property:{...property,address:'PRIVATE-ADDRESS',email:'PRIVATE-EMAIL',phone:'PRIVATE-PHONE',addressDetails:{street:'PRIVATE-STREET',houseNumber:'PRIVATE-HOUSE'},latitude:47.123,longitude:19.123},likedAt:notice.createdAt,myDecision:'passed',matchId:null,compatible:false,compatibilityScore:68,partner:{email:'PRIVATE-PARTNER'}}};
 const calls=routes({'/api/notifications/notice%2Fid/context':raw}),api=adapter();api.active={kind:'property',id:'another-profile'};
 const before={...api.active},context=await api.getNotificationContext('notice/id');
 assert.deepEqual(context.target,target);assert.deepEqual(context.notification.target,target);assert.equal(context.available,true);assert.equal(context.canActivate,true);
 assert.deepEqual(context.item.pair,{propertyId:ids.property,searchId:ids.search});assert.equal(context.item.id,ids.property);assert.equal(context.item.kind,'property');
 assert.equal(context.item.price,72.9);assert.equal(context.item.score,68);assert.equal(context.item.myDecision,'passed');assert.equal(context.item.compatible,false);assert.equal(context.item.address,'');
 assert.doesNotMatch(JSON.stringify(context),/PRIVATE-|latitude|longitude|addressDetails|eventKey|userId/);
 assert.equal(calls.length,1);assert.equal(calls[0].method,'GET');assert.equal(calls[0].headers.Authorization,'Bearer sample-token');assert.deepEqual(api.active,before);
 for(const id of ['',null,1])await assert.rejects(api.getNotificationContext(id),/értesítés/);assert.equal(calls.length,1);
});

test('notification contexts map both profile sides and retain unavailable history with safe known destinations',async()=>{
 const target={page:'incoming',entityKind:'property',entityId:ids.property,propertyId:ids.property,searchRequestId:ids.search,matchId:null};
 const notice={id:'incoming',kind:'incoming_like',target};
 routes({'/api/notifications/incoming/context':{notification:notice,target,available:true,canActivate:true,item:{propertyId:ids.property,searchRequestId:ids.search,searchRequest:{...search,phone:'PRIVATE-PHONE'},myDecision:'liked',matchId:ids.match,compatible:true}}});
 const api=adapter(),context=await api.getNotificationContext('incoming');assert.equal(context.item.kind,'search');assert.equal(context.item.id,ids.search);assert.equal(context.item.maxPrice,85);assert.equal(context.item.matchId,ids.match);assert.doesNotMatch(JSON.stringify(context),/PRIVATE-/);
 const archivedTarget={...target,page:'messages',matchId:ids.match};
 routes({'/api/notifications/history/context':{notification:{id:'history',kind:'message_received',target:archivedTarget},target:archivedTarget,available:true,canActivate:false,item:{partner:{email:'PRIVATE-CONTACT'}}}});
 const history=await api.getNotificationContext('history');assert.equal(history.available,true);assert.equal(history.canActivate,false);assert.equal(history.item,null);assert.equal(history.target.matchId,ids.match);
 routes({'/api/notifications/gone/context':{notification:notice,target,available:false,canActivate:true,item:{property}}});
 const gone=await api.getNotificationContext('gone');assert.equal(gone.available,false);assert.equal(gone.canActivate,false);assert.equal(gone.item,null);
 routes({'/api/notifications/invalid/context':{notification:{id:'invalid',kind:'incoming_like'},target:{page:'https://foreign.invalid',entityKind:'search',entityId:ids.search},available:true,canActivate:true,item:{property}}});
 const invalid=await api.getNotificationContext('invalid');assert.equal(invalid.target,null);assert.equal(invalid.available,false);assert.equal(invalid.canActivate,false);
 routes({'/api/notifications/foreign/context':()=>response({message:'Az értesítés nem található.'},404)});
 await assert.rejects(api.getNotificationContext('foreign'),error=>error.status===404);
});

test('notification read responses preserve only authoritative nonnegative integer unread counts',async()=>{
 for(const count of [0,5,-1,1.5,'5',null]){
  routes({'/api/notifications/read-count/read':{id:'read-count',kind:'credit_added',amount:10,unreadCount:count,ownerId:'PRIVATE-OWNER',target:{...creditsTarget,addressDetails:'PRIVATE-ADDRESS'}}});
  const item=await adapter().markNotificationRead('read-count');assert.equal('unreadCount' in item,Number.isSafeInteger(count)&&count>=0);
  if('unreadCount' in item)assert.equal(item.unreadCount,count);assert.deepEqual(item.target,creditsTarget);assert.doesNotMatch(JSON.stringify(item),/PRIVATE-/);
 }
});

test('hosted landing is anonymous and same-origin, converts HUF and discards private or raw listing fields',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'api',environment:'test'};globalThis.location={origin:'https://dev.otthonra.hu'};
 globalThis.localStorage={getItem:()=>{throw new Error('Anonymous landing must not read authentication storage');}};
 let captured;
 globalThis.fetch=async(url,options)=>{captured={url,options};return response({regions:[{id:'untrusted',label:'Private'}],region:{id:'HU110',label:'wrong'},scope:'region',searches:[{key:'search-1',title:'Lakást keresnek',type:'Lakás',locations:['Budapest XI. kerület'],minPrice:null,maxPrice:85000000,minArea:50,maxArea:null,minRooms:2,maxRooms:null,ownerAccountType:'agent',id:'PRIVATE-ID',ownerId:'PRIVATE-OWNER',description:'PRIVATE-CONTACT',phone:'PRIVATE-PHONE'}],properties:[{key:'property-1',title:'Eladó lakás',type:'Lakás',location:'Budapest',price:72900000,area:64,wholeRooms:2,halfRooms:2,rooms:3,lotArea:null,ownerAccountType:'private',address:'PRIVATE-ADDRESS',images:['PRIVATE-IMAGE'],email:'PRIVATE-EMAIL'}]});};
 const data=await fetchLanding({region:'HU110'});
 assert.equal(captured.url,'https://dev.otthonra.hu/api/public/landing?region=HU110');assert.equal(captured.options.headers.Authorization,undefined);
 assert.equal(data.regions.length,20);assert.deepEqual(data.region,{id:'HU110',label:'Budapest'});assert.equal(data.scope,'region');
 assert.equal(data.searches[0].maxPrice,85);assert.equal(data.searches[0].minPrice,null);assert.equal(data.properties[0].price,72.9);
 assert.equal(JSON.stringify(data).includes('PRIVATE-'),false);assert.equal('id' in data.searches[0],false);assert.equal('images' in data.properties[0],false);
});

test('public landing errors never turn into hosted demo data and invalid regions never make a request',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'api',environment:'test'};globalThis.location={origin:'https://dev.otthonra.hu'};
 let requests=0;globalThis.fetch=async()=>{requests++;return response({message:'A szolgáltatás nem érhető el.'},503);};
 await assert.rejects(fetchLanding(),error=>error.status===503);assert.equal(requests,1);
 for(const region of ['unknown','HU110&private=1',false,123])await assert.rejects(fetchLanding({region}),/régió/);assert.equal(requests,1);
 globalThis.fetch=async()=>{throw new TypeError('offline');};await assert.rejects(fetchLanding(),/API nem érhető/);
});

test('local public preview uses fictional safe catalog data, prioritizes searches, and returns honest regional emptiness',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'demo'};globalThis.fetch=async()=>{throw new Error('Local preview must not fetch');};
 globalThis.localStorage={getItem:()=>{throw new Error('Public preview must not read saved users');}};
 const national=await fetchLanding();assert.equal(national.scope,'national');assert.equal(national.region,null);assert.equal(national.regions.length,20);
 assert.ok(national.searches.length>national.properties.length);assert.ok(national.searches.length<=16);assert.ok(national.properties.length<=8);
 assert.equal(JSON.stringify(national).includes('@'),false);assert.equal(JSON.stringify(national).includes('Pozsonyi'),false);
 const selected=await fetchLanding({region:'HU110'});assert.equal(selected.scope,'region');assert.ok(selected.searches.length);
 const empty=await fetchLanding({region:'HU321'});assert.equal(empty.region.label,'Hajdú-Bihar vármegye');assert.deepEqual(empty.searches,[]);assert.deepEqual(empty.properties,[]);
});

test('coarse region detection uses only Hungarian country and region, with privacy-preserving request settings',async()=>{
 let captured;globalThis.localStorage={setItem:()=>{throw new Error('IP payload must not be persisted');}};
 const privatePayload={country_code:'HU',region:'Hajdu-Bihar County',ip:'PRIVATE-IP',latitude:'PRIVATE-LAT',longitude:'PRIVATE-LONG',city:'PRIVATE-CITY'};
 globalThis.fetch=async(url,options)=>{captured={url,options};return {ok:true,json:async()=>privatePayload};};
 assert.equal(await detectLandingRegion(),'HU321');assert.equal(captured.url,'https://get.geojs.io/v1/ip/geo.json');
 for(const [key,value] of Object.entries({credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',redirect:'error'}))assert.equal(captured.options[key],value);
 assert.equal(captured.options.headers.Authorization,undefined);assert.ok(captured.options.signal instanceof AbortSignal);
 for(const region of ['Csongrad County','Csongrád-Csanád vármegye']){globalThis.fetch=async()=>({ok:true,json:async()=>({country_code:'HU',region})});assert.equal(await detectLandingRegion(),'HU333');}
 globalThis.fetch=async()=>({ok:true,json:async()=>({country_code:'HU',region:'Budapest'})});assert.equal(await detectLandingRegion([{id:'HU110',label:'Budapest'}]),'HU110');
 assert.equal(await detectLandingRegion([{id:'HU321',label:'Hajdú-Bihar vármegye'}]),null);
});

test('coarse region lookup fails closed to national for foreign, unknown, malformed, blocked and unavailable providers',async()=>{
 for(const payload of [{country_code:'US',region:'Budapest'},{country_code:'HU',region:'Unknown'},{country_code:'HU',region:null},null]){
  globalThis.fetch=async()=>({ok:true,json:async()=>payload});assert.equal(await detectLandingRegion(),null);
 }
 globalThis.fetch=async()=>({ok:false,json:async()=>{throw new Error('must not parse');}});assert.equal(await detectLandingRegion(),null);
 globalThis.fetch=async()=>{throw new TypeError('network blocked');};assert.equal(await detectLandingRegion(),null);
 globalThis.fetch=async()=>({ok:true,json:async()=>{throw new SyntaxError('invalid JSON');}});assert.equal(await detectLandingRegion(),null);
});

test('coarse region detection aborts after three seconds and leaves timeout failures as national',async()=>{
 const originalSetTimeout=globalThis.setTimeout,originalClearTimeout=globalThis.clearTimeout;let cleared;
 try {
  globalThis.setTimeout=(callback,ms)=>{assert.equal(ms,3000);queueMicrotask(callback);return 'coarse-region-timeout';};
  globalThis.clearTimeout=id=>{cleared=id;};
  globalThis.fetch=async(url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true}));
  assert.equal(await detectLandingRegion(),null);assert.equal(cleared,'coarse-region-timeout');
 } finally {globalThis.setTimeout=originalSetTimeout;globalThis.clearTimeout=originalClearTimeout;}
});

test('recommendation stages preserve consent metadata, zero scores and specialization without exposing private fields',async()=>{
 const calls=[];
 globalThis.fetch=async(url,options)=>{const target=new URL(url);calls.push({target,options});return response(target.searchParams.get('includeApproximate')==='true'?{
  active:{kind:'search',id:ids.search},stage:'approximate',hasApproximate:true,requiresApproximateConsent:false,
  items:[{property:{...property,owner:{email:'private@example.test'}},searchRequest:search,compatibilityScore:0,isExact:false,searchSpecificity:67,valueForMoney:1.25,reasons:['Az ár meghaladja a keretet']}]
 }:{active:{kind:'search',id:ids.search},items:[],stage:'empty',hasApproximate:true,requiresApproximateConsent:true});};
 const api=adapter();api.active={kind:'search',id:ids.search};
 const exact=await api.recommendations();assert.deepEqual(exact.items,[]);assert.equal(exact.requiresApproximateConsent,true);assert.equal(calls[0].target.search,'');
 const approximate=await api.recommendations({includeApproximate:true});assert.equal(approximate.stage,'approximate');assert.equal(calls[1].target.searchParams.get('includeApproximate'),'true');
 assert.equal(approximate.items[0].score,0);assert.equal(approximate.items[0].isExact,false);assert.equal(approximate.items[0].searchSpecificity,67);assert.equal(approximate.items[0].valueForMoney,1.25);assert.equal('owner' in approximate.items[0],false);
 assert.deepEqual(approximate.active,{kind:'search',id:ids.search});
});

test('approximate decision authorization is sent only with an explicit boolean opt-in',async()=>{
 const calls=routes({'/api/decisions':{charged:0}}),api=adapter(),candidate={pair:{propertyId:ids.property,searchId:ids.search}};
 await api.decide(candidate,false);assert.equal('allowApproximate' in JSON.parse(calls[0].body),false);
 await api.decide(candidate,true,{allowApproximate:true});assert.equal(JSON.parse(calls[1].body).allowApproximate,true);
 await api.decide(candidate,true,{allowApproximate:'false'});assert.equal('allowApproximate' in JSON.parse(calls[2].body),false);
});

test('recommendations keep the requested active kind while a later activation changes the adapter',async()=>{
 let finish;
 globalThis.fetch=async()=>new Promise(resolve=>{finish=()=>resolve(response({active:{kind:'search',id:ids.search},stage:'exact',items:[{property,searchRequest:search,compatibilityScore:100,isExact:true}]}));});
 const api=adapter();api.active={kind:'search',id:ids.search};const pending=api.recommendations();
 api.active={kind:'property',id:ids.property};finish();const result=await pending;
 assert.deepEqual(result.active,{kind:'search',id:ids.search});assert.equal(result.items[0].kind,'property');
});

test('search specialization is preserved from authoritative own-search DTOs',async()=>{
 routes(accountRoutes({'/api/me/entities':{searchRequests:[{...search,searchSpecificity:81}],active:{kind:'search',id:ids.search}}}));
 const state=await adapter().getState();assert.equal(state.searches[0].searchSpecificity,81);
});

test('invalid nonempty API location selections stay invalid rather than reviving through legacy city fields',async()=>{
 const {evaluateMatch}=await import('../dist/matching.js');
 for(const invalidId of ['city:Nemlétező','area:Budapest']){
  routes(accountRoutes({'/api/me/entities':{properties:[{...property,locationId:invalidId,city:'Budapest'}],searchRequests:[{...search,locationIds:['city:Budapest']}],active:{kind:'search',id:ids.search}}}));
  const state=await adapter().getState();assert.equal(state.properties[0].locationId,invalidId);assert.equal(evaluateMatch(state.properties[0],state.searches[0]).eligible,false);
 }
 for(const locationIds of [['city:Nemlétező'],['city:Budapest','city:Nemlétező']]){
  routes(accountRoutes({'/api/me/entities':{properties:[{...property,locationId:'city:Budapest'}],searchRequests:[{...search,city:'Budapest',locationIds}],active:{kind:'search',id:ids.search}}}));
  const state=await adapter().getState();assert.deepEqual(state.searches[0].locationIds,locationIds);assert.equal(evaluateMatch(state.properties[0],state.searches[0]).eligible,false);
 }
});

test('blank legacy API selections retain their canonical city and district fallback without changing save validation',async()=>{
 const {evaluateMatch}=await import('../dist/matching.js');
 routes(accountRoutes({'/api/me/entities':{properties:[{...property,locationId:'',city:'Budapest',district:'XIII.'}],searchRequests:[{...search,city:'Budapest',districts:['XIII.'],locationIds:[]}],active:{kind:'search',id:ids.search}}}));
 const state=await adapter().getState();assert.equal(state.properties[0].locationId,'district:Budapest:13');assert.deepEqual(state.searches[0].locationIds,['district:Budapest:13']);assert.equal(evaluateMatch(state.properties[0],state.searches[0]).eligible,true);
});

test('match criteria expose only concrete public comparison fields on discovery and incoming cards',async()=>{
 const details=[{key:'rooms',label:'Szobaszám',expected:'legalább 3 szoba',actual:'2 szoba',matches:false,privateOwner:{email:'hidden@example.test'}},
  {key:'area',label:'Alapterület',expected:'legalább 50 m²',actual:'64 m²',matches:true},
  {key:'privatePhone',label:'private',expected:'private',actual:'private',matches:false},{key:'floor',label:[],expected:'Földszint',actual:'1. emelet',matches:false}];
 const item={property:{...property,ownerFirstName:'Péter',owner:{name:'Kovács Péter',phone:'PRIVATE-PHONE'}},searchRequest:search,compatibilityScore:75,isExact:false,matchDetails:details};
 routes({'/api/feed':{items:[item]},'/api/incoming-likes':{active:{kind:'search',id:ids.search},items:[{...item,compatible:true}],total:1,offset:0,limit:50,hasMore:false}});
 const api=adapter();api.active={kind:'search',id:ids.search};
 for(const card of [(await api.feed())[0],(await api.incomingLikes()).items[0]]){
  assert.equal(card.ownerFirstName,'Péter');assert.equal(card.matchDetails.length,2);
  assert.deepEqual(card.matchDetails[0],{key:'rooms',label:'Szobaszám',expected:'legalább 3 szoba',actual:'2 szoba',matches:false});
  assert.equal(card.matchDetails[1].matches,true);assert.doesNotMatch(JSON.stringify(card),/hidden@example|PRIVATE-PHONE|privateOwner|Kovács/);
 }
});

test('public landing preserves real titles and first names while omitting contacts and all private fields',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'api',environment:'test'};globalThis.location={origin:'https://dev.otthonra.hu'};
 globalThis.fetch=async()=>response({searches:[{title:'Kertes családi otthont keresünk',ownerFirstName:'Anna',type:'Ház',locations:['Debrecen'],maxPrice:95000000,ownerName:'Nagy Anna',email:'PRIVATE-EMAIL'}],
  properties:[{title:'Világos otthon a belvárosban',ownerFirstName:'Péter',type:'Lakás',location:'Debrecen',price:65000000,area:60,rooms:3,ownerId:'PRIVATE-ID',phone:'PRIVATE-PHONE'}]});
 const result=await fetchLanding();
 assert.equal(result.searches[0].title,'Kertes családi otthont keresünk');assert.equal(result.searches[0].ownerFirstName,'Anna');
 assert.equal(result.properties[0].title,'Világos otthon a belvárosban');assert.equal(result.properties[0].ownerFirstName,'Péter');
 assert.doesNotMatch(JSON.stringify(result),/PRIVATE-|Nagy Anna/);
 globalThis.fetch=async()=>response({searches:[{title:'Hívj: +36 30 123 4567',ownerFirstName:'anna@example.test'}],properties:[{title:'Írj: peter@example.test',ownerFirstName:'+36 30 123 4567'}]});
 const unsafe=await fetchLanding();assert.equal(unsafe.searches[0].title,'Ingatlant keresnek');assert.equal(unsafe.properties[0].title,'Eladó ingatlan');assert.equal(unsafe.searches[0].ownerFirstName,'');assert.equal(unsafe.properties[0].ownerFirstName,'');
});


test('anonymous teaser source identities accept only opaque keys of the matching kind and never infer identity from a slot',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'api',environment:'test'};globalThis.location={origin:'https://dev.otthonra.hu'};
 const searchKey='search-'+'a'.repeat(64),propertyKey='property-'+'b'.repeat(64);
 globalThis.fetch=async()=>response({searches:[{key:'search-3',sourceKey:searchKey},{key:'search-1',sourceKey:propertyKey},{key:'search-2',sourceKey:'11111111-1111-1111-1111-111111111111'}],properties:[{key:'property-4',sourceKey:propertyKey},{key:'property-2',sourceKey:'private@example.hu'},{key:'property-1'}]});
 const value=await fetchLanding();
 assert.deepEqual(value.searches.map(item=>item.sourceKey),[searchKey,null,null]);
 assert.deepEqual(value.properties.map(item=>item.sourceKey),[propertyKey,null,null]);
 assert.equal(value.searches[0].key,'search-3');assert.equal(value.properties[0].key,'property-4');
 assert.doesNotMatch(JSON.stringify(value),/11111111-1111|private@example/);
});

test('superseded view state reads settle immediately and cannot overwrite a newer active account snapshot',async()=>{
 const model=adapter(),controller=new AbortController(),pending=[];
 globalThis.fetch=(url,options)=>new Promise(resolve=>pending.push({path:new URL(url).pathname,options,resolve}));
 const previous=model.getState({signal:controller.signal});
 assert.equal(pending.length,3);
 controller.abort();
 await assert.rejects(previous,error=>error.code==='API_READ_CANCELLED'&&error.status===undefined);
 assert.ok(pending.every(item=>item.options.signal.aborted),'Every read in the old view is cancelled');
 routes(accountRoutes());const current=await model.getState();
 for(const item of pending)item.resolve(response(item.path==='/api/me'?{...profile,id:'previous-user'}:item.path==='/api/me/entities'?{properties:[],searchRequests:[],active:{kind:'property',id:'previous-active'}}:[]));
 for(let index=0;index<8;index++)await Promise.resolve();
 assert.equal(model.userId,current.user.id);assert.deepEqual(model.active,current.active);
 assert.notEqual(model.userId,'previous-user');assert.notEqual(model.active.id,'previous-active');
});

test('all scoped view reads reject an already cancelled signal without sending a request',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'api',environment:'test'};globalThis.location={origin:'https://dev.otthonra.hu'};
 const model=adapter(),controller=new AbortController();controller.abort();let calls=0;
 globalThis.fetch=async()=>{calls++;throw new Error('A cancelled view must not start network work');};
 for(const read of [
  ()=>model.getState({signal:controller.signal}),()=>model.recommendations({signal:controller.signal}),
  ()=>model.feed({signal:controller.signal}),()=>model.matches({signal:controller.signal}),
  ()=>model.pendingFeedback({signal:controller.signal}),()=>model.getFeedbackScenario({signal:controller.signal}),
  ()=>model.incomingLikes({signal:controller.signal}),()=>model.notifications({signal:controller.signal}),
  ()=>model.getNotificationContext('notice',{signal:controller.signal}),
  ()=>model.getPropertyInsights(ids.property,{signal:controller.signal}),()=>fetchLanding({signal:controller.signal})
 ])await assert.rejects(read(),error=>error.code==='API_READ_CANCELLED');
 assert.equal(calls,0);
});

test('cancelling a view aborts its GET but neither aborts nor replays submitted writes',async()=>{
 const model=adapter(),controller=new AbortController(),pending=[];
 globalThis.fetch=(url,options)=>new Promise(resolve=>pending.push({url,options,resolve}));
 const read=model.matches({signal:controller.signal});
 const writes=['POST','PUT','DELETE'].map(method=>model.call('/write-test',method,{example:true},{signal:controller.signal}));
 controller.abort();
 await assert.rejects(read,error=>error.code==='API_READ_CANCELLED');
 const submitted=pending.filter(item=>item.options.method!=='GET');
 assert.equal(submitted.length,3);assert.ok(submitted.every(item=>!item.options.signal.aborted));
 submitted.forEach((item,index)=>item.resolve(response({accepted:index})));
 assert.deepEqual(await Promise.all(writes),[{accepted:0},{accepted:1},{accepted:2}]);
 assert.equal(pending.length,4,'Cancellation never retries a mutation');
});

test('a cancelled response body cannot hold a view open and completed reads detach their cancellation listener',async()=>{
 const model=adapter(),controller=new AbortController();let bodyStarted=false,resolveBody;
 globalThis.fetch=async()=>({ok:true,status:200,text:()=>{bodyStarted=true;return new Promise(resolve=>{resolveBody=resolve;});}});
 const pending=model.matches({signal:controller.signal});
 for(let index=0;index<4&&!bodyStarted;index++)await Promise.resolve();assert.equal(bodyStarted,true);
 controller.abort();await assert.rejects(pending,error=>error.code==='API_READ_CANCELLED');
 resolveBody('[]');await Promise.resolve();
 const fresh=new AbortController();let transportSignal;
 globalThis.fetch=async(_url,options)=>{transportSignal=options.signal;return response([]);};
 assert.deepEqual(await model.matches({signal:fresh.signal}),[]);fresh.abort();
 assert.equal(transportSignal.aborted,false,'A finished request releases its view listener');
});

test('the original twenty-second request deadline remains bounded for reads and writes without automatic retry',async()=>{
 const originalSetTimeout=globalThis.setTimeout,originalClearTimeout=globalThis.clearTimeout;
 const timers=new Map(),cleared=[];let nextTimer=0,calls=0;
 try{
  globalThis.setTimeout=(callback,delay)=>{assert.equal(delay,20000);const id=++nextTimer;timers.set(id,callback);return id;};
  globalThis.clearTimeout=id=>{cleared.push(id);timers.delete(id);};
  globalThis.fetch=async()=>{calls++;return await new Promise(()=>{});};
  const model=adapter();
  for(const method of ['GET','POST']){
   const pending=model.call('/deadline-test',method,method==='POST'?{example:true}:undefined);
   const [timer,callback]=[...timers.entries()][0];callback();
   await assert.rejects(pending,error=>error.code!=='API_READ_CANCELLED'&&/20 másodperc/.test(error.message));
   assert.ok(cleared.includes(timer));assert.equal(timers.size,0);
  }
  assert.equal(calls,2,'An expired write is not replayed');
 }finally{globalThis.setTimeout=originalSetTimeout;globalThis.clearTimeout=originalClearTimeout;}
});

test('an acknowledged mutual like can return before optional match hydration without retrying the accepted decision',async()=>{
 const candidate={pair:{propertyId:ids.property,searchId:ids.search}},api=adapter();
 for(const lookup of ['held','failed']){
  const calls=[];
  globalThis.fetch=async(url,options)=>{
   const path=new URL(url).pathname;calls.push({path,...options});
   if(path==='/api/decisions')return response({matchId:ids.match,charged:2});
   if(lookup==='held')return await new Promise(()=>{});
   return response({message:'Temporary match lookup failure'},503);
  };
  const result=await api.decide(candidate,true,{allowApproximate:true,resolveMatch:false});
  assert.equal(result.match,null);assert.equal(result.matchId,ids.match);assert.equal(result.charged,2);
  assert.equal(calls.length,1,'The already accepted write never waits for or retries optional hydration');
  assert.equal(calls[0].path,'/api/decisions');assert.equal(calls[0].method,'POST');
  assert.deepEqual(JSON.parse(calls[0].body),{propertyId:ids.property,searchRequestId:ids.search,liked:true,allowApproximate:true});
 }
 const calls=routes({'/api/decisions':{match,charged:0}});
 const inline=await api.decide(candidate,true,{resolveMatch:false});
 assert.equal(inline.matchId,ids.match);assert.equal(inline.match.id,ids.match);assert.equal(calls.length,1);
 const emptyCalls=routes({'/api/decisions':{matchId:null,charged:0}});
 assert.equal((await api.decide(candidate,false,{resolveMatch:false})).matchId,null);assert.equal(emptyCalls.length,1);
});

test('apartment height and private garden round-trip while the retired shared garden and derived floor state stay inactive',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201)});
 const input={...exactAddress,title:'Kerti lakás',city:'Debrecen',type:'Lakás',price:60,area:60,rooms:3,floor:'0',buildingFloors:'0',privateGarden:'false',sharedGarden:'true',airConditioning:false,isTopFloor:true};
 const saved=await adapter().saveEntity('property',input),body=JSON.parse(calls[0].body);
 assert.deepEqual([body.floor,body.buildingFloors,body.privateGarden,body.sharedGarden,body.airConditioning],[0,0,false,null,false]);
 assert.deepEqual([saved.floor,saved.buildingFloors,saved.privateGarden,saved.sharedGarden],[0,0,false,null]);
 assert.equal('isTopFloor' in body,false);
 await assert.rejects(adapter().saveEntity('property',{...input,floor:2,buildingFloors:1}),/magasabb/);
 await assert.rejects(adapter().saveEntity('property',{...input,buildingFloors:true}),/épület/);
 assert.equal(calls.length,1);
});

test('new search requirements serialize as opt-in booleans and old responses keep absent amenities unrestricted',async()=>{
 const calls=routes({'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 const saved=await adapter().saveEntity('search',{title:'Emeleti kerti lakás',city:'Debrecen',type:'Lakás',excludeTopFloor:true,excludeGroundFloorAndBelow:'false',airConditioning:'true',privateGarden:true,sharedGarden:false});
 const body=JSON.parse(calls[0].body);
 assert.deepEqual([body.excludeTopFloor,body.excludeGroundFloorAndBelow,body.airConditioning,body.privateGarden,body.sharedGarden],[true,false,true,true,false]);
 assert.deepEqual([saved.excludeTopFloor,saved.excludeGroundFloorAndBelow,saved.airConditioning,saved.privateGarden,saved.sharedGarden],[true,false,true,true,false]);
 const calls2=routes(accountRoutes());const old=(await adapter().getState()).searches[0];
 assert.ok(calls2.length);for(const key of ['excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden','sharedGarden'])assert.equal(old[key],false,key);
});

test('house saves clear building height and apartment gardens while retaining an all-type aircon requirement',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201),'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 await adapter().saveEntity('property',{...exactAddress,title:'Kertes ház',city:'Debrecen',type:'Ház',price:60,area:80,rooms:3,lotArea:400,floor:5,buildingFloors:2,privateGarden:true,sharedGarden:true,airConditioning:true});
 const p=JSON.parse(calls[0].body);assert.deepEqual([p.floor,p.buildingFloors,p.privateGarden,p.sharedGarden,p.airConditioning],[null,null,null,null,true]);
 await adapter().saveEntity('search',{title:'Ház',city:'Debrecen',type:'Ház',excludeTopFloor:true,excludeGroundFloorAndBelow:true,airConditioning:true,privateGarden:true,sharedGarden:true});
 const q=JSON.parse(calls[1].body);assert.deepEqual([q.excludeTopFloor,q.excludeGroundFloorAndBelow,q.airConditioning,q.privateGarden,q.sharedGarden],[false,false,true,false,false]);
});

test('new public match detail keys preserve server facts and discard unrelated or private metadata',async()=>{
 const keys=['excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden','sharedGarden'];
 routes({'/api/feed':{items:[{property:{...property,buildingFloors:3,privateGarden:false,sharedGarden:true},searchRequest:search,matchDetails:[...keys.map(key=>({key,label:key,expected:'Van',actual:'Nincs',matches:false})),{key:'addressDetails',label:'private',expected:'private',actual:'private',matches:false}]}]}});
 const api=adapter();api.active={kind:'search',id:ids.search};const feed=await api.feed();
 assert.deepEqual(feed[0].matchDetails.map(x=>x.key),keys.filter(key=>key!=='sharedGarden'));assert.equal(feed[0].privateGarden,false);assert.equal(feed[0].sharedGarden,null);assert.equal(feed[0].buildingFloors,3);
});


test('old keyed creation payloads preserve retired garden bytes while returned facts remain inactive',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201),'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 const creationRequestId='1252f520-aefe-4a9c-b1b6-932ef64fe38a';
 const p={...exactAddress,title:'Korábbi lezárt kerti lakás',city:'Debrecen',type:'Lakás',price:60,area:60,rooms:3,sharedGarden:'true'};
 const saved=await adapter().saveEntity('property',p,undefined,{creationRequestId});
 assert.equal(JSON.parse(calls[0].body).sharedGarden,true,'The original keyed request must retain its hashed boolean');assert.equal(saved.sharedGarden,null);
 const q={title:'Korábbi lezárt keresés',city:'Debrecen',type:'Lakás',sharedGarden:true};
 const search=await adapter().saveEntity('search',q,undefined,{creationRequestId});
 assert.equal(JSON.parse(calls[1].body).sharedGarden,true);assert.equal(search.sharedGarden,false);
 await adapter().saveEntity('search',{...q,type:'Ház'},undefined,{creationRequestId});assert.equal(JSON.parse(calls[2].body).sharedGarden,false,'The old house serialization also ignored shared garden');
 await adapter().saveEntity('property',p);assert.equal(JSON.parse(calls[3].body).sharedGarden,null,'Ordinary creates have no retired preference');
 await adapter().saveEntity('search',q);assert.equal(JSON.parse(calls[4].body).sharedGarden,false);
});


test('raised floor and an upper-range choice round-trip without losing old exact heights',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201),'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 const base={...exactAddress,title:'Magasföldszinti otthon',locationId:'city:Debrecen',type:'Lakás',price:60,area:60,rooms:3};
 const raised=await adapter().saveEntity('property',{...base,floor:0.5,buildingFloors:0});assert.equal(raised.floor,0.5);assert.equal(raised.floorIsUpperRange,false);
 const grouped=await adapter().saveEntity('property',{...base,floor:9,floorIsUpperRange:true,buildingFloors:12});assert.equal(grouped.floorIsUpperRange,true);
 const exact=await adapter().saveEntity('property',{...base,floor:12,floorIsUpperRange:false,buildingFloors:12});assert.equal(exact.floor,12);assert.equal(exact.floorIsUpperRange,false);
 await assert.rejects(adapter().saveEntity('property',{...base,floor:8,floorIsUpperRange:true}),/9 vagy/);
 const q={title:'Régebbi emeleti keresés',locationIds:['city:Debrecen'],type:'Lakás',floors:[11]};
 const key='1252f520-aefe-4a9c-b1b6-932ef64fe38a';
 const replay=await adapter().saveEntity('search',q,undefined,{creationRequestId:key});assert.deepEqual(JSON.parse(calls[3].body).floors,[11],'A frozen old input keeps its original wire hash');assert.deepEqual(replay.floors,[9]);
 await adapter().saveEntity('search',q);assert.deepEqual(JSON.parse(calls[4].body).floors,[9],'Ordinary writes use the current ninth-plus key');
});

test('ordinary entity writes reject obfuscated description contacts before sending requests while old keyed receipts remain replayable',async()=>{
 const calls=routes({'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 const base={title:'Elérhetőség nélküli keresés',locationIds:['city:Debrecen'],type:'Lakás'};
 await assert.rejects(adapter().saveEntity('search',{...base,description:'Anna kukac pelda pont hu'}),/Elérhetőséget/);assert.equal(calls.length,0);
 await adapter().saveEntity('search',{...base,description:'Világos, 60 négyzetméteres lakást keresek.',moveIn:''});assert.equal(JSON.parse(calls[0].body).moveIn,'');
 await adapter().saveEntity('search',{...base,description:'Anna kukac pelda pont hu'},undefined,{creationRequestId:'1252f520-aefe-4a9c-b1b6-932ef64fe38a'});assert.equal(calls.length,2,'The server must be able to acknowledge an old successful creation before applying the new policy');
});

test('new seller controls retain true, false and unknown values and send privacy/certificate facts explicitly',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201)});
 for(const balcony of [null,false,true]){
  const result=await adapter().saveEntity('property',{...exactAddress,title:'Részletes otthon',locationId:'city:Debrecen',type:'Lakás',price:80,area:60,rooms:3,balcony,hideStreet:false,hideHouseNumber:false,isAttic:false,energyRating:'A+',energyRatingScheme:'2023',heatingType:'Gázcirkó'});
  const body=JSON.parse(calls.at(-1).body);assert.equal(body.balcony,balcony);assert.equal(result.balcony,balcony);
  assert.equal(body.hideStreet,false);assert.equal(body.hideHouseNumber,false);assert.equal(body.isAttic,false);assert.equal(body.energyRatingScheme,'2023');assert.equal(body.heatingType,'Gázkazán / cirkó');
 }
 const result=await adapter().saveEntity('property',{...exactAddress,title:'Rejtett cím',locationId:'city:Debrecen',price:80,area:60,rooms:3,hideStreet:true,hideHouseNumber:false});
 assert.equal(JSON.parse(calls.at(-1).body).hideHouseNumber,true);assert.equal(result.hideHouseNumber,true);
});

test('frozen creations replay their historical heating labels and do not invent newly added request fields',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201),'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 const creationRequestId='aa853da8-ac30-4b3d-8d3c-a6d348ffda09';
 const saved=await adapter().saveEntity('property',{...exactAddress,title:'Régi piszkozat',locationId:'city:Debrecen',price:80,area:60,rooms:3,heatingType:'Gázcirkó',secondaryHeatingType:'Klíma'},undefined,{creationRequestId});
 const body=JSON.parse(calls[0].body);assert.equal(body.heatingType,'Gázcirkó');assert.equal(body.secondaryHeatingType,'Klíma');assert.equal(saved.heatingType,'Gázkazán / cirkó');
 for(const field of ['hideStreet','hideHouseNumber','isAttic','energyRatingScheme'])assert.equal(Object.hasOwn(body,field),false);
 await adapter().saveEntity('search',{title:'Régi keresési piszkozat',locationIds:['city:Debrecen'],heatingTypes:['Gázcirkó','Klíma']},undefined,{creationRequestId});
 assert.deepEqual(JSON.parse(calls[1].body).heatingTypes,['Gázcirkó','Klíma']);
});

test('anonymous detail reads whitelist every public field, convert prices once and honor address visibility',async()=>{
 const key='property-'+'a'.repeat(64);globalThis.OTTHONRA_CONFIG={mode:'api'};globalThis.location={origin:'https://dev.otthonra.hu'};globalThis.localStorage=storage();globalThis.localStorage.setItem(API_CONFIG_KEY,JSON.stringify({baseUrl:'https://private.example.hu',token:'NEVER-SEND'}));
 const base={kind:'property',key,sourceKey:key,title:'Világos otthon',ownerFirstName:'Anna',ownerAccountType:'agent',listing:{type:'Lakás',description:'Kellemes, világos otthon.',price:85000000,area:62,rooms:2.5,location:'Debrecen',city:'Debrecen',street:'Titkos utca',houseNumber:'18/A',address:'Titkos utca 18/A',hideStreet:true,hideHouseNumber:false,energyRating:'B',energyRatingScheme:'2023',balcony:null,isAttic:true,images:['https://images.example.hu/home.jpg','javascript:secret'],ownerId:'PRIVATE-ID',email:'PRIVATE-EMAIL',phone:'PRIVATE-PHONE',addressDetails:{latitude:47.5,longitude:19.1}},prefill:{type:'Lakás',locations:[locations.find(x=>x.id==='city:Debrecen')],price:85000000,area:62,rooms:2.5,energyRating:'B',energyRatingScheme:'2023'}};
 let captured;globalThis.fetch=async(url,options)=>{captured={url,options};return response(base);};
 const detail=await fetchPublicListing('property',key);assert.equal(captured.url,`https://dev.otthonra.hu/api/public/listings/property/${key}`);assert.equal(captured.options.headers.Authorization,undefined);
 assert.equal(detail.listing.price,85);assert.equal(detail.prefill.price,85);assert.equal(detail.listing.balcony,null);assert.equal(detail.listing.address,'');assert.equal(detail.listing.houseNumber,'');assert.equal(detail.listing.hideHouseNumber,true);
 assert.deepEqual(detail.listing.images,['https://images.example.hu/home.jpg']);assert.doesNotMatch(JSON.stringify(detail),/PRIVATE-|Titkos|18\/A|latitude|longitude|addressDetails/);
 base.listing.hideStreet=false;base.listing.hideHouseNumber=true;
 const streetOnly=await fetchPublicListing('property',key);assert.equal(streetOnly.listing.address,'Titkos utca');assert.equal(streetOnly.listing.houseNumber,'');
 base.listing.hideHouseNumber=false;assert.equal((await fetchPublicListing('property',key)).listing.address,'Titkos utca 18/A');
});

test('search detail cloning retains optional criteria and text without identities or repeated HUF conversion',async()=>{
 const key='search-'+'b'.repeat(64),city=locations.find(x=>x.id==='city:Debrecen');globalThis.OTTHONRA_CONFIG={mode:'api'};globalThis.location={origin:'https://dev.otthonra.hu'};
 const source={type:'Lakás',locations:[city],minPrice:50000000,maxPrice:90000000,minArea:55,maxArea:95,minRooms:1.5,maxRooms:4,heatingTypes:['Gázcirkó'],atticPreference:'exclude',minEnergyRating:'C',description:'Világos otthont keresek.',moveIn:'Azonnal',financing:'Önerő',balcony:true};
 globalThis.fetch=async()=>response({kind:'search',key,sourceKey:key,title:'Keresésem',ownerFirstName:'Péter',listing:{...source,ownerId:'PRIVATE'},prefill:source,clonePrefill:source});
 const detail=await fetchPublicListing('search',key);assert.equal(detail.listing.maxPrice,90);assert.equal(detail.clonePrefill.maxPrice,90);assert.equal(detail.clonePrefill.minPrice,50);assert.equal(detail.clonePrefill.minRooms,1.5);assert.equal(detail.clonePrefill.description,source.description);assert.equal(detail.clonePrefill.atticPreference,'exclude');assert.equal(detail.clonePrefill.minEnergyRating,'C');assert.deepEqual(detail.clonePrefill.heatingTypes,['Gázkazán / cirkó']);assert.doesNotMatch(JSON.stringify(detail),/PRIVATE|ownerId/);
});

test('missing or malformed anonymous listings fail without demo fallback or private authentication',async()=>{
 globalThis.OTTHONRA_CONFIG={mode:'api'};globalThis.location={origin:'https://dev.otthonra.hu'};let count=0;
 globalThis.fetch=async()=>{count++;return response({message:'A hirdetés nem található.'},404);};
 await assert.rejects(fetchPublicListing('property','property-'+'a'.repeat(64)),error=>error.status===404);assert.equal(count,1);
 for(const [kind,key]of [['private','search-'+'a'.repeat(64)],['property','../private'],['search','property-'+'a'.repeat(64)]])await assert.rejects(fetchPublicListing(kind,key),/hirdetés/);
 assert.equal(count,1);
});

test('own public budget round-trips in HUF while invalid public caps are rejected before network writes',async()=>{
 const calls=routes({'/api/searches':options=>response({...search,...JSON.parse(options.body)},201)});
 const api=adapter(),data={title:'Védett árkeret',locationIds:['city:Debrecen'],type:'Lakás',minPrice:20,maxPrice:80,publicMaxPrice:70,minArea:20};
 const saved=await api.saveEntity('search',data);assert.equal(saved.maxPrice,80);assert.equal(saved.publicMaxPrice,70);
 assert.equal(JSON.parse(calls[0].body).maxPrice,80000000);assert.equal(JSON.parse(calls[0].body).publicMaxPrice,70000000);
 for(const publicMaxPrice of [-1,0,19,81,'rossz'])await assert.rejects(api.saveEntity('search',{...data,publicMaxPrice}),/publikus maximumár/);
 await assert.rejects(api.saveEntity('search',{...data,maxPrice:2000000,publicMaxPrice:1000001}),/publikus maximumár/);
 assert.equal(calls.length,1);
 await api.saveEntity('search',{...data,publicMaxPrice:null});assert.equal(JSON.parse(calls[1].body).publicMaxPrice,null);
 const old={...data};delete old.publicMaxPrice;await api.saveEntity('search',old);assert.equal('publicMaxPrice' in JSON.parse(calls[2].body),false,'Old frozen creation payloads must keep their old shape');
});

test('API adapter retains private budget only for the owner, including history and matches',async()=>{
 const protectedSearch={...search,maxPrice:123456000,publicMaxPrice:70000000};
 routes(accountRoutes({'/api/me/entities':{searches:[protectedSearch],properties:[],decisions:[{id:'decision',actorId:ids.search,propertyId:ids.property,searchId:ids.search,searchRequest:protectedSearch}]},'/api/matches':[{...match,searchRequest:protectedSearch}]}));
 const api=adapter(),own=await api.getState();assert.equal(own.searches[0].maxPrice,123.456);assert.equal(own.searches[0].publicMaxPrice,70);
 assert.equal(own.decisions[0].search.maxPrice,123.456);assert.equal('searchRequest' in own.decisions[0],false);
 assert.equal((await api.matches())[0].search.maxPrice,123.456);
 const foreign={...protectedSearch,ownerId:'other'};
 routes(accountRoutes({'/api/me/entities':{searches:[],properties:[],decisions:[{id:'d',actorId:ids.property,propertyId:ids.property,searchId:ids.search,searchRequest:foreign}]},'/api/matches':[{...match,searchRequest:foreign}],'/api/feed':{active:{kind:'property',id:ids.property},items:[{search:foreign,propertyId:ids.property,searchId:ids.search,score:93}]}}));
 const foreignState=await api.getState();api.active={kind:'property',id:ids.property};
 for(const row of [foreignState.decisions[0].search,(await api.matches())[0].search,(await api.feed())[0]]){assert.equal(row.maxPrice,70);assert.equal('publicMaxPrice' in row,false);}
 assert.equal(JSON.stringify(await api.matches()).includes('123456000'),false);
});

test('anonymous details and public search-copy seeds never reuse a supplied private cap',()=>{
 const key='search-'+'a'.repeat(64),value={kind:'search',sourceKey:key,title:'Védett keresés',listing:{type:'Lakás',locations:['Debrecen'],maxPrice:123456000,publicMaxPrice:70000000},prefill:{type:'Lakás',locations:[locations.find(x=>x.id==='city:Debrecen')],maxPrice:123456000,publicMaxPrice:70000000},clonePrefill:{type:'Lakás',locations:[locations.find(x=>x.id==='city:Debrecen')],maxPrice:123456000,publicMaxPrice:70000000}};
 const data=publicListingFromApi('search',key,value);assert.equal(data.listing.maxPrice,70);assert.equal(data.prefill.maxPrice,70);assert.equal(data.clonePrefill.maxPrice,70);assert.equal(data.clonePrefill.publicMaxPrice,70);
 assert.equal(JSON.stringify(data).includes('123456000'),false);assert.equal(JSON.stringify(data).includes('123.456'),false);
});

test('registration and profile writes require a trimmed phone without sending empty contact data',async()=>{
 globalThis.localStorage=storage();const calls=routes(accountRoutes({'/api/auth/register':{accessToken:'registered-with-phone'},'/api/me':options=>response({...profile,...(options.body?JSON.parse(options.body):{})})}));
 for(const phone of [undefined,null,'',' \t ',false,12345,'1'.repeat(41)]){
  await assert.rejects(connectApi('https://api.example.hu','phone@example.hu','password1234',{name:'Telefonszámos Anna',phone}),/telefonszám/);
 }
 assert.equal(calls.length,0,'Invalid registration does not send credentials or replace a session');
 const api=await connectApi('https://api.example.hu','phone@example.hu','password1234',{name:'Telefonszámos Anna',phone:'  +36 30 555 0199  '});
 assert.equal(JSON.parse(calls[0].body).phone,'+36 30 555 0199');
 const before=calls.length;
 for(const phone of [undefined,null,'','  '])await assert.rejects(api.updateProfile({name:'Telefonszámos Anna',email:'phone@example.hu',phone}),/telefonszám/);
 assert.equal(calls.length,before);
 await api.updateProfile({name:'Telefonszámos Anna',email:'phone@example.hu',phone:' +36 30 555 0188 '});
 assert.equal(JSON.parse(calls.at(-1).body).phone,'+36 30 555 0188');
});
