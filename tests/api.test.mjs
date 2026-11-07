import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import {locations} from '../dist/locations.js';
import { ApiModel, API_CONFIG_KEY, connectApi, getModel, disconnectApi, hostedMode, deploymentEnvironment } from '../dist/api.js';

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
  const result = await adapter().saveEntity('property', { title: 'Otthon', city: 'Budapest', district: 'XI.', type: 'Lakás', price: '72.9', area: '64.5', rooms: '2.5', floor: '3', balcony: false, elevator: 'false', images: ['https://images.example.hu/home.jpg'], ownerId: 'not-authoritative' });
  const body = JSON.parse(calls[0].body);
  assert.deepEqual([body.price, body.area, body.rooms, body.floor], [72900000, 64.5, 2.5, 3]);
  assert.equal(body.balcony, false);
  assert.equal(body.elevator, false);
  assert.equal('ownerId' in body, false);
  assert.equal(result.price, 72.9);
  assert.equal(body.locationId, 'district:Budapest:11');
  assert.equal(result.location.label, 'Budapest XI. kerület');
  assert.equal(calls[0].headers.Authorization, 'Bearer sample-token');
  await assert.rejects(adapter().saveEntity('property', { price: 'invalid', area: 5, rooms: 1 }), /érvényes szám/);
  await assert.rejects(adapter().saveEntity('property', { price: 5, area: 5, rooms: 1, floor: 1.5 }), /egész szám/);
  await assert.rejects(adapter().saveEntity('property', { price: 5, area: 5, rooms: 1, images: ['/assets/home.jpg'] }), /HTTPS/);
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
  for (const locationId of ['', 'city:Nemlétező']) await assert.rejects(adapter().saveEntity('property', { ...data, locationId }), /találati listából/);
  for (const locationIds of [[], ['city:Nemlétező'], ['city:Debrecen', 'city:Nemlétező']]) await assert.rejects(adapter().saveEntity('search', { ...data, locationIds }), /találati listából/);
  await assert.rejects(adapter().saveEntity('search', { title: 'Nincs kiválasztva' }), /találati listából/);
  assert.equal(calls.length, 0);
});

test('house plot area is required on save and is cleared for apartments', async () => {
  const calls = routes({ '/api/properties': options => response({ id: ids.property, ...JSON.parse(options.body) }, 201) });
  const data = { title: 'Kertes ház', locationId: 'city:Solymár', type: 'Ház', price: '105.5', area: '115', rooms: '4', lotArea: '720.5' };
  const house = await adapter().saveEntity('property', data);
  assert.equal(JSON.parse(calls[0].body).lotArea, 720.5);
  assert.equal(house.lotArea, 720.5);
  assert.equal(house.locationId, 'city:Solymár');
  for (const lotArea of ['',null,undefined]) await assert.rejects(adapter().saveEntity('property', { ...data, lotArea }), /telekméret/);
  const apartment = await adapter().saveEntity('property', { ...data, type: 'Lakás' });
  assert.equal(apartment.lotArea, null);
  await assert.rejects(adapter().saveEntity('property', { ...data, lotArea: 0 }), /telekméret/);
  await assert.rejects(adapter().saveEntity('property', { ...data, lotArea: 'hibás' }), /érvényes szám/);
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
  const api=await connectApi(globalThis.location.origin,'anna@example.hu','password1234',{name:'Teszt Anna',phone:''});
  assert.equal(api.baseUrl,globalThis.location.origin);assert.equal(api.mode,'api');
  assert.deepEqual(JSON.parse(calls[0].body),{name:'Teszt Anna',phone:'',accountType:'private',email:'anna@example.hu',password:'password1234'});
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
 const result=await adapter().saveEntity('property',{title:'Részletes lakás',locationId:'district:Budapest:13',type:'Lakás',price:78,area:68,rooms:3,condition:'Jó állapotú',building:'Tégla',constructionAge:'10–30 év közötti',view:'Kertre néző',ceilingHeight:'3 m feletti',floor:'0',heatingType:'Hőszivattyú',secondaryHeatingType:'Klíma',insulated:'false',energyRating:'BB',airConditioning:'true',solarPanels:null,parkingType:'Udvari beálló'});
 const body=JSON.parse(calls[0].body);
 assert.deepEqual([body.condition,body.building,body.floor],['Jó','Tégla',0]);
 assert.deepEqual([body.insulated,body.airConditioning,body.solarPanels],[false,true,null]);
 for(const field of ['condition','building','constructionAge','view','ceilingHeight','floor','heatingType','insulated','energyRating','airConditioning','solarPanels','parkingType'])assert.deepEqual(result[field],body[field],field);
 const blank=await adapter().saveEntity('property',{title:'Ismeretlen részletek',locationId:'city:Debrecen',type:'Lakás',price:40,area:50,rooms:2,insulated:'',airConditioning:'',solarPanels:''});
 assert.deepEqual([blank.condition,blank.building,blank.floor,blank.insulated,blank.airConditioning,blank.solarPanels],['','',null,null,null,null]);
});

test('multiselect search attributes serialize as deduplicated arrays and can all be cleared',async()=>{
 const calls=routes({'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 const result=await adapter().saveEntity('search',{title:'Szűrt keresés',locationIds:['city:Budapest'],conditions:['Jó','Felújított','Jó'],buildings:['Panel','Tégla'],constructionAges:['10 évnél fiatalabb','10–30 év közötti'],views:['Kertre néző','Panorámás'],ceilingHeight:'3 m alatti',floors:['-1','0','11']});
 const body=JSON.parse(calls[0].body);
 assert.deepEqual(body.conditions,['Jó','Új/felújított']);assert.deepEqual(body.buildings,['Panel','Tégla']);assert.deepEqual(body.floors,[-1,0,11]);
 for(const field of ['conditions','buildings','constructionAges','views','ceilingHeight','floors'])assert.deepEqual(result[field],body[field],field);
 const cleared=await adapter().saveEntity('search',{...result,conditions:[],buildings:[],constructionAges:[],views:[],ceilingHeight:'',floors:[]});
 assert.deepEqual([cleared.conditions,cleared.buildings,cleared.constructionAges,cleared.views,cleared.floors],[[],[],[],[],[]]);assert.equal(cleared.ceilingHeight,'');
});

test('new invalid enums and malformed selections are rejected before sending while an update can preserve server-owned legacy labels',async()=>{
 const calls=routes({['/api/properties/'+ids.property]:options=>response({id:ids.property,...JSON.parse(options.body)})});
 const base={title:'Meglévő lakás',locationId:'city:Budapest',price:50,area:60,rooms:3};
 await assert.rejects(adapter().saveEntity('property',{...base,view:'Ismeretlen'}),/Érvénytelen/);
 await assert.rejects(adapter().saveEntity('property',{...base,condition:'Ismeretlen'}),/Érvénytelen/);
 await assert.rejects(adapter().saveEntity('property',{...base,insulated:'talán'}),/igen, nem/);
 await assert.rejects(adapter().saveEntity('search',{title:'Hibás keresés',locationIds:['city:Budapest'],conditions:'Jó'}),/listaként/);
 await assert.rejects(adapter().saveEntity('search',{title:'Hibás keresés',locationIds:['city:Budapest'],floors:[12]}),/Érvénytelen/);
 assert.equal(calls.length,0);
 const updated=await adapter().saveEntity('property',{...base,condition:'Régi egyedi állapot',building:'Régi egyedi szerkezet'},ids.property);
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
 await assert.rejects(api.saveEntity('property',data),/találati listából/);
 const towns=locations.filter(value=>value.kind==='city').slice(0,50).map(value=>value.id);
 await assert.rejects(api.saveEntity('search',{title:'Túl sok hely',locationIds:['area:Budapest',...towns]}),/találati listából/);
 assert.equal(calls.length,0);
});

test('a property response with an invalid area ID does not become an exact town location',async()=>{
 routes(accountRoutes({'/api/me/entities':{properties:[{...property,locationId:'area:Budapest',city:'Budapest'}],searchRequests:[{...search,locationIds:['area:Budapest']}],active:{kind:'search',id:ids.search}}}));
 const state=await adapter().getState();assert.equal(state.properties[0].location,null);assert.equal(state.properties[0].locationId,'');
 assert.equal(state.searches[0].locations[0].kind,'area');assert.equal(state.searches[0].locations[0].settlementCount,81);
});

test('new seller details use typed arrays and explicit room composition throughout API round trips',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201)});
 const saved=await adapter().saveEntity('property',{title:'Fél szobás lakás',locationId:'city:Debrecen',type:'Lakás',price:'65.5',area:'80',wholeRooms:'2',halfRooms:'3',heatingType:'Gázkazán',secondaryHeatingType:'Kandalló',parkingTypes:['Garázs','Udvari beálló','Garázs']});
 const body=JSON.parse(calls[0].body);
 assert.deepEqual([body.wholeRooms,body.halfRooms,body.rooms],[2,3,3.5]);
 assert.deepEqual([saved.wholeRooms,saved.halfRooms,saved.rooms],[2,3,3.5]);
 assert.deepEqual(body.parkingTypes,['Garázs','Udvari beálló']);assert.deepEqual(saved.parkingTypes,body.parkingTypes);
 assert.equal(saved.secondaryHeatingType,'Kandalló');
 const legacy=await adapter().saveEntity('property',{title:'Régi API adat',locationId:'city:Debrecen',price:55,area:50,rooms:3.2});
 const legacyBody=JSON.parse(calls[1].body);
 assert.deepEqual([legacyBody.rooms,legacyBody.wholeRooms,legacyBody.halfRooms],[3.2,null,null]);
 assert.deepEqual([legacy.rooms,legacy.wholeRooms,legacy.halfRooms],[3.2,null,null]);
});

test('legacy-only API updates leave explicit composition to the server and allow unchanged public legacy descriptions',async()=>{
 const calls=routes({['/api/properties/'+ids.property]:options=>response({id:ids.property,...JSON.parse(options.body)})});
 const updated=await adapter().saveEntity('property',{title:'Változatlan részletek',locationId:'city:Debrecen',price:55,area:50,rooms:3.5,heatingType:'Hőszivattyú és padlófűtés',parkingType:'Régi garázs, kapubeállóval'},ids.property);
 const body=JSON.parse(calls[0].body);
 assert.deepEqual([body.wholeRooms,body.halfRooms],[null,null],'do not invent a different breakdown for old-client updates');
 assert.equal(updated.heatingType,'Hőszivattyú és padlófűtés');assert.deepEqual(updated.parkingTypes,['Régi garázs, kapubeállóval']);
});

test('invalid counts, negative numeric values and newly introduced heating or parking choices do not reach the API',async()=>{
 const calls=routes({}),api=adapter(),base={title:'Érvényes lakás',locationId:'city:Debrecen',price:55,area:50,wholeRooms:2,halfRooms:1};
 for(const changes of [{price:-1},{area:-1},{wholeRooms:-1},{halfRooms:-1},{halfRooms:1.5},{wholeRooms:0,halfRooms:0},{rooms:4},{rooms:-1},{heatingType:'Új egyedi fűtés'},{secondaryHeatingType:'Új egyedi fűtés'},{parkingTypes:['Ismeretlen']},{parkingTypes:['Garázs',null]}])await assert.rejects(api.saveEntity('property',{...base,...changes}));
 for(const key of ['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms'])await assert.rejects(api.saveEntity('search',{title:'Hibás keresés',locationIds:['city:Debrecen'],[key]:-1}));
 await assert.rejects(api.saveEntity('search',{title:'Hibás fűtés',locationIds:['city:Debrecen'],heatingTypes:['Ismeretlen']}));
 assert.equal(calls.length,0);
});

test('house API saves remove hidden controls while search heating remains an optional multi-selection',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201),'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201)});
 const house=await adapter().saveEntity('property',{title:'Kertes ház',locationId:'city:Solymár',type:'Ház',price:95,area:110,wholeRooms:4,halfRooms:0,lotArea:700,floor:'invalid',balcony:true,elevator:true});
 assert.deepEqual([house.floor,house.balcony,house.elevator],[null,false,false]);
 const saved=await adapter().saveEntity('search',{title:'Házat keresünk',locationIds:['city:Solymár'],type:'Ház',floors:[3],balcony:true,elevator:true,heatingTypes:['Gázkazán','Klíma','Gázkazán'],minRooms:2.5,maxRooms:4.5});
 assert.deepEqual([saved.floors,saved.balcony,saved.elevator],[[],false,false]);
 assert.deepEqual(saved.heatingTypes,['Gázkazán','Klíma']);
 assert.deepEqual([saved.minRooms,saved.maxRooms],[2.5,4.5]);
 const body=JSON.parse(calls[1].body);assert.deepEqual(body.heatingTypes,saved.heatingTypes);
});

test('agent declarations register explicitly while invalid choices never send credentials',async()=>{
 globalThis.localStorage=storage();
 const calls=routes(accountRoutes({'/api/auth/register':{accessToken:'registered-agent-token'},'/api/me':{...profile,accountType:'agent'}}));
 const api=await connectApi('https://api.example.hu','agent@example.hu','password1234',{name:'Közvetítő Anna',accountType:'agent'});
 assert.equal(JSON.parse(calls[0].body).accountType,'agent');assert.equal((await api.getState()).user.accountType,'agent');assert.equal((await api.getState()).likeCost,1);
 const before=calls.length;for(const accountType of ['',false,'unknown'])await assert.rejects(connectApi('https://api.example.hu','agent@example.hu','password1234',{name:'Közvetítő Anna',accountType}),/fióktípust/);
 assert.equal(calls.length,before);
});

test('API owner metadata persists through own lists, public feeds, history and matches without using the viewer account type',async()=>{
 const agentProperty={...property,ownerAccountType:'agent'},privateSearch={...search,ownerAccountType:'private'};
 routes(accountRoutes({'/api/me':{...profile,accountType:'agent'},'/api/me/entities':{properties:[agentProperty],searchRequests:[privateSearch],reportedOwnerIds:['other','other'],active:{kind:'search',id:ids.search},decisions:[{id:'choice',actorId:ids.search,actorKind:'search',propertyId:ids.property,searchRequestId:ids.search,property:agentProperty,searchRequest:privateSearch}]},'/api/feed':{likeCost:1,items:[{property:agentProperty,searchRequest:privateSearch}]},'/api/matches':[{...match,property:agentProperty,searchRequest:privateSearch,contact:{...match.contact,accountType:'agent'}}]}));
 const api=adapter(),state=await api.getState();assert.equal(state.user.accountType,'agent');assert.equal(state.likeCost,1);assert.deepEqual(state.reportedOwnerIds,['other']);
 assert.equal(state.properties[0].ownerAccountType,'agent');assert.equal(state.searches[0].ownerAccountType,'private');assert.equal(state.decisions[0].property.ownerAccountType,'agent');assert.equal(state.decisions[0].search.ownerAccountType,'private');
 const card=(await api.feed())[0];assert.equal(card.ownerAccountType,'agent');assert.equal('email' in card,false);assert.equal('phone' in card,false);
 const result=(await api.matches())[0];assert.equal(result.partner.accountType,'agent');assert.equal(result.property.ownerAccountType,'agent');assert.equal(result.search.ownerAccountType,'private');
});

test('legacy API responses retain private/free defaults and no-active accounts have no like cost',async()=>{
 routes(accountRoutes());let state=await adapter().getState();assert.equal(state.user.accountType,'private');assert.equal(state.likeCost,0);assert.deepEqual(state.reportedOwnerIds,[]);
 routes(accountRoutes({'/api/me':{...profile,accountType:'agent',activeKind:null,activeEntityId:null},'/api/me/entities':{properties:[],searchRequests:[],active:null}}));state=await adapter().getState();assert.equal(state.likeCost,0);
 routes(accountRoutes({'/api/me':{...profile,accountType:'agent'},'/api/me/entities':{properties:[property],searchRequests:[],active:{kind:'property',id:ids.property}}}));state=await adapter().getState();assert.equal(state.likeCost,2);assert.equal(state.properties[0].ownerAccountType,'private','a viewer declaration cannot label another owner');
});

test('report requests use source entities only and preserve idempotent acknowledgements and retryable API failures',async()=>{
 const receipt={id:'receipt',reported:true,reportedOwnerId:'other',alreadyReported:false};let sent=0;
 const calls=routes({'/api/reports':options=>{sent++;return response({...receipt,alreadyReported:sent>1},sent===1?201:200);}}),api=adapter();
 assert.deepEqual(await api.reportAccount('property',ids.property),receipt);assert.deepEqual(JSON.parse(calls[0].body),{entityKind:'property',entityId:ids.property});
 assert.equal((await api.reportAccount('search',ids.search)).alreadyReported,true);assert.equal('createdAt' in receipt,false);
 const before=calls.length;for(const [kind,id] of [['user','other'],['property',''],['search',null]])await assert.rejects(api.reportAccount(kind,id),/jelentési profil/);assert.equal(calls.length,before);
 routes({'/api/reports':()=>response({message:'Átmeneti hiba'},503)});await assert.rejects(api.reportAccount('property',ids.property),error=>error.status===503&&error.message==='Átmeneti hiba');
});

test('owner declarations cannot be set through property or search save payloads or profile updates',async()=>{
 const calls=routes({'/api/properties':options=>response({id:ids.property,...JSON.parse(options.body)},201),'/api/searches':options=>response({id:ids.search,...JSON.parse(options.body)},201),'/api/me':options=>response({...profile,...JSON.parse(options.body)})});
 const api=adapter();await api.saveEntity('property',{title:'Saját ingatlan',locationId:'city:Debrecen',price:50,area:50,rooms:2,ownerAccountType:'agent'});
 await api.saveEntity('search',{title:'Saját keresés',locationIds:['city:Debrecen'],ownerAccountType:'agent'});await api.updateProfile({name:'Nagy Anna',email:'anna@example.hu',phone:'',accountType:'agent'});
 for(const call of calls){const body=JSON.parse(call.body);assert.equal('ownerAccountType' in body,false);assert.equal('accountType' in body,false);}
});
