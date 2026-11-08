import { model as demoModel, demoLanding } from './model.js';
import { regions } from './regions-data.js';
import { getLocation, resolveLegacyLocations, isPropertyLocation } from './locations.js';
import {normalizePropertyAttributes, normalizeSearchAttributes} from './attributes.js';
import {normalizeAccountType,likeCost,normalizeReportReason,normalizeIncomingPagination,REPORT_REASON_OPTIONS} from './accounts.js';

export const API_CONFIG_KEY = 'otthonra.api';
export const hostedMode = () => globalThis.OTTHONRA_CONFIG?.mode === 'api';
export const deploymentEnvironment = () => globalThis.OTTHONRA_CONFIG?.environment || 'local';
const hostedApiBase = () => apiBase(globalThis.location?.origin);

const clone = value => value == null ? value : JSON.parse(JSON.stringify(value));
const MILLION = 1000000;

function apiBase(value) {
  let url;
  try { url = new URL(String(value || '').trim()); } catch { throw new Error('Adj meg egy érvényes API-címet, például https://api.pelda.hu.'); }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('Az API-cím HTTP vagy HTTPS URL lehet, felhasználónév és lekérdezési paraméterek nélkül.');
  return url.href.replace(/\/+$/, '').replace(/\/api$/, '');
}
function readConfig() {
  let raw;
  try { raw = globalThis.localStorage?.getItem(API_CONFIG_KEY); } catch { throw new Error('A böngésző helyi tárhelye nem érhető el.'); }
  if (!raw) return null;
  let config;
  try { config = JSON.parse(raw); } catch { throw new Error('Az API-kapcsolat beállítása sérült. A beállításoknál bontsd a kapcsolatot.'); }
  if (!config?.baseUrl || !config?.token) throw new Error('Az API-kapcsolat hiányos. Jelentkezz be újra a beállításoknál.');
  return { ...config, baseUrl: apiBase(config.baseUrl) };
}
function errorMessage(payload, status) {
  if (status === 401) return 'A munkameneted lejárt, vagy hibásak a bejelentkezési adatok. Jelentkezz be újra.';
  if (status === 403) return 'Ehhez a művelethez nincs jogosultságod.';
  if (payload?.errors && typeof payload.errors === 'object') {
    const messages = Object.values(payload.errors).flat().filter(v => typeof v === 'string');
    if (messages.length) return messages.join(' ');
  }
  return payload?.message || payload?.detail || payload?.error || payload?.title || `Az API-kérés sikertelen (${status}).`;
}
async function request(baseUrl, token, path, method = 'GET', body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(`${baseUrl}/api${path}`, { method, headers, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: controller.signal });
    const raw = await response.text();
    let payload = null;
    if (raw) { try { payload = JSON.parse(raw); } catch { if (response.ok) throw new Error('Az API érvénytelen JSON-választ küldött.'); } }
    if (!response.ok) { const error = new Error(errorMessage(payload, response.status)); error.status = response.status; throw error; }
    return payload;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Az API nem válaszolt 20 másodpercen belül. Próbáld újra.');
    if (error instanceof TypeError) throw new Error('Az API nem érhető el. Ellenőrizd a címet, a szerver futását és a CORS-beállításokat.');
    throw error;
  } finally { clearTimeout(timeout); }
}

const rows = value => Array.isArray(value) ? value : (value?.items || []);
const initials = name => String(name || '').trim().split(/\s+/).filter(Boolean).map(v => v[0]).slice(0, 2).join('').toUpperCase();
const millions = value => value == null ? value : Number(value) / MILLION;
const numeric = value => value == null ? value : Number(value);
function entityLocations(value, kind, strict = false) {
  let ids;
  if (kind === 'property') {
    if (Object.hasOwn(value, 'locationId') && (strict || value.locationId != null)) ids = [value.locationId];
    else if (value.location?.id) ids = [value.location.id];
  } else {
    if (Object.hasOwn(value, 'locationIds') && (strict || value.locationIds != null)) ids = Array.isArray(value.locationIds) ? value.locationIds : [];
    else if (Array.isArray(value.locations)) ids = value.locations.map(location=>location.id);
  }
  const uniqueIds = ids == null ? null : [...new Set(ids)];
  const selected = uniqueIds == null ? resolveLegacyLocations(kind === 'search' ? {...value, districts:inputStrings(value.districts)} : value) : uniqueIds.map(getLocation).filter(Boolean);
  const locations = kind === 'property' ? selected.filter(isPropertyLocation) : selected;
  if (strict && (!locations.length || (kind === 'search' && locations.length > 50)
      || (uniqueIds != null && locations.length !== uniqueIds.length))) throw new Error('Válassz érvényes települést vagy budapesti kerületet a találati listából.');
  return locations;
}

function propertyFromApi(value) {
  if (!value) return null;
  const location = entityLocations(value, 'property')[0] || null;
  return normalizePropertyAttributes({
    id: String(value.id), ownerId: String(value.ownerId ?? value.userId ?? ''), ownerAccountType:normalizeAccountType(value.ownerAccountType),
    title: value.title || '', locationId:location?.id || '', location:clone(location), city: location?.city ?? value.city ?? '', district: location ? location.district || '' : value.district ?? '', neighborhood: value.neighborhood || '', address: value.address || '', description: value.description || '', createdAt: value.createdAt,
    type: value.type || value.propertyType || 'Lakás',
    price: millions(value.priceHuf ?? value.price), area: numeric(value.area ?? value.areaSqm ?? value.sizeSqm), rooms: numeric(value.rooms ?? value.roomCount), wholeRooms:value.wholeRooms, halfRooms:value.halfRooms,
    lotArea: numeric(value.lotArea ?? value.lotAreaSqm ?? null), floor: numeric(value.floor), condition: value.condition || '', building: value.building || value.buildingMaterial || '',
    balcony: !!(value.balcony ?? value.hasBalcony), elevator: !!(value.elevator ?? value.hasElevator),
    constructionAge:value.constructionAge, view:value.view, ceilingHeight:value.ceilingHeight,
    heatingType:value.heatingType, secondaryHeatingType:value.secondaryHeatingType, insulated:value.insulated, energyRating:value.energyRating,
    airConditioning:value.airConditioning, solarPanels:value.solarPanels, parkingType:value.parkingType, parkingTypes:value.parkingTypes,
    images: clone(value.images || value.imageUrls || []), archived: !!(value.archived ?? value.isArchived)
  });
}
function searchFromApi(value) {
  if (!value) return null;
  const locations = entityLocations(value, 'search');
  return normalizeSearchAttributes({
    id: String(value.id), ownerId: String(value.ownerId ?? value.userId ?? ''), ownerAccountType:normalizeAccountType(value.ownerAccountType),
    title: value.title || '', locationIds:locations.map(location=>location.id), locations:clone(locations), city: locations[0]?.city ?? value.city ?? '', districts: locations.filter(location=>location.city===locations[0]?.city&&location.district).map(location=>location.district), description: value.description || '', moveIn: value.moveIn || '', buyerName: value.buyerName || '', financing: value.financing || '', avatar: value.avatar || '', createdAt: value.createdAt,
    type: value.type || value.propertyType || 'Lakás',
    minPrice: millions(value.minPriceHuf ?? value.minPrice ?? null), maxPrice: millions(value.maxPriceHuf ?? value.maxPrice ?? null),
    minArea: numeric(value.minArea ?? value.minAreaSqm ?? null), maxArea: numeric(value.maxArea ?? value.maxAreaSqm ?? null),
    minRooms: numeric(value.minRooms ?? null), maxRooms: numeric(value.maxRooms ?? null),
    balcony: !!(value.balcony ?? value.requiresBalcony), elevator: !!(value.elevator ?? value.requiresElevator),
    conditions:value.conditions ?? (value.condition ? [value.condition] : []),
    buildings:value.buildings ?? (value.building ? [value.building] : []),
    constructionAges:value.constructionAges, views:value.views, ceilingHeight:value.ceilingHeight, floors:value.floors, heatingTypes:value.heatingTypes,
    archived: !!(value.archived ?? value.isArchived)
  });
}
function inputNumber(value, name, nullable = false) {
  if (value === '' || value == null) {
    if (nullable) return null;
    throw new Error(`A(z) ${name} megadása kötelező.`);
  }
  const result = typeof value === 'boolean' ? NaN : Number(value);
  if (!Number.isFinite(result)) throw new Error(`A(z) ${name} érvényes szám legyen.`);
  return result;
}
const inputBoolean = value => value === true || value === 1 || ['true', '1', 'on'].includes(String(value).toLowerCase());
const inputText = value => value == null ? '' : String(value).trim();
const inputStrings = value => Array.isArray(value) ? value.map(inputText).filter(Boolean) : inputText(value).split(/[,\n]/).map(inputText).filter(Boolean);
function propertyToApi(value, updating = false) {
  const attributes = normalizePropertyAttributes(value,{strict:true,allowLegacyUnknown:updating});
  const type = inputText(value.type) || 'Lakás';
  const countsSupplied = [value.wholeRooms,value.halfRooms].some(count=>count != null && String(count).trim() !== '');
  const floor = type === 'Ház' ? null : attributes.floor;
  if (floor != null && !Number.isInteger(floor)) throw new Error('Az emelet egész szám legyen.');
  const images = Array.isArray(value.images) ? value.images.map(inputText).filter(Boolean) : inputText(value.images).split('\n').map(inputText).filter(Boolean);
  if (images.length > 12 || images.some(image => { try { return new URL(image).protocol !== 'https:' || image.length > 2000; } catch { return true; } })) throw new Error('Az API-hoz legfeljebb 12 HTTPS-képhivatkozás adható meg.');
  const price = inputNumber(value.price, 'ár'), area = inputNumber(value.area, 'alapterület'), rooms = inputNumber(attributes.rooms, 'szobaszám');
  if (price <= 0 || area <= 0 || rooms <= 0 || rooms > 1000) throw new Error('Az ár, az alapterület és a szobaszám legyen pozitív szám.');
  const location = entityLocations(value, 'property', true)[0];
  const lotArea = type === 'Ház' ? inputNumber(value.lotArea, 'telekméret') : null;
  if (lotArea != null && (lotArea <= 0 || lotArea > 10000000)) throw new Error('A telekméret pozitív szám legyen.');
  return {
    title: inputText(value.title), locationId:location.id, city:location.city, district:location.district || '', neighborhood: inputText(value.neighborhood), address: inputText(value.address), description: inputText(value.description),
    type, price: Math.round(price * MILLION), area, rooms, wholeRooms:countsSupplied ? attributes.wholeRooms : null, halfRooms:countsSupplied ? attributes.halfRooms : null, lotArea, floor,
    condition:attributes.condition, building:attributes.building,
    constructionAge:attributes.constructionAge, view:attributes.view, ceilingHeight:attributes.ceilingHeight,
    heatingType:attributes.heatingType, secondaryHeatingType:attributes.secondaryHeatingType, insulated:attributes.insulated, energyRating:attributes.energyRating,
    airConditioning:attributes.airConditioning, solarPanels:attributes.solarPanels, parkingType:attributes.parkingType, parkingTypes:attributes.parkingTypes,
    balcony: type === 'Ház' ? false : inputBoolean(value.balcony), elevator: type === 'Ház' ? false : inputBoolean(value.elevator), images, archived: inputBoolean(value.archived)
  };
}
function searchToApi(value) {
  const attributes = normalizeSearchAttributes(value,{strict:true});
  const minPrice = inputNumber(value.minPrice, 'minimumár', true), maxPrice = inputNumber(value.maxPrice, 'maximumár', true);
  const locations = entityLocations(value, 'search', true);
  const minArea = inputNumber(value.minArea, 'minimum alapterület', true), maxArea = inputNumber(value.maxArea, 'maximum alapterület', true);
  const minRooms = inputNumber(value.minRooms, 'minimum szobaszám', true), maxRooms = inputNumber(value.maxRooms, 'maximum szobaszám', true);
  for (const [min,max] of [[minPrice,maxPrice],[minArea,maxArea],[minRooms,maxRooms]]) {
    if ((min != null && min < 0) || (max != null && max <= 0) || (min != null && max != null && min > max)) throw new Error('A minimum érték nem lehet nagyobb a maximumnál; a korlátok érvényes számok legyenek.');
  }
  return {
    title: inputText(value.title), locationIds:locations.map(location=>location.id), city:locations[0].city, districts:locations.filter(location=>location.city===locations[0].city&&location.district).map(location=>location.district), description: inputText(value.description), type: inputText(value.type) || 'Lakás',
    minPrice: minPrice == null ? null : Math.round(minPrice * MILLION), maxPrice: maxPrice == null ? null : Math.round(maxPrice * MILLION),
    minArea, maxArea, minRooms, maxRooms,
    conditions:attributes.conditions, buildings:attributes.buildings, constructionAges:attributes.constructionAges,
    views:attributes.views, ceilingHeight:attributes.ceilingHeight, floors:attributes.floors, heatingTypes:attributes.heatingTypes,
    balcony: value.type === 'Ház' ? false : inputBoolean(value.balcony), elevator: value.type === 'Ház' ? false : inputBoolean(value.elevator), moveIn: inputText(value.moveIn), financing: inputText(value.financing), archived: inputBoolean(value.archived)
  };
}
function reportSummaries(values) {
  const unique=new Map();
  for(const item of Array.isArray(values)?values:[]) {
    if(!['property','search'].includes(item?.entityKind)||typeof item.entityId!=='string'||!item.entityId||!REPORT_REASON_OPTIONS.some(option=>option.value===item.reason))continue;
    const value={entityKind:item.entityKind,entityId:item.entityId,reason:item.reason};
    unique.set(JSON.stringify(value),value);
  }
  return [...unique.values()];
}
function candidateFromApi(item,activeKind) {
  const rawProperty=item.property,rawSearch=item.search||item.searchRequest;
  const propertyId=String(item.propertyId??rawProperty?.id??''),searchId=String(item.searchId??item.searchRequestId??rawSearch?.id??'');
  const property=activeKind==='search';
  const entity=property?propertyFromApi(rawProperty||item):searchFromApi(rawSearch||item);
  return {...entity,kind:property?'property':'search',score:Math.round(Number(item.compatibilityScore??item.score??100)),reasons:clone(item.reasons||[]),pair:{propertyId,searchId},likedYou:!!(item.likedYou??item.hasLiked)};
}
function notificationFromApi(value) {
  return {id:String(value.id),kind:String(value.kind||''),amount:Number(value.amount||0),text:String(value.text||''),decisionId:String(value.decisionId||''),createdAt:value.createdAt,readAt:value.readAt??null};
}
function messageFromApi(value) {
  return { ...clone(value), id: String(value.id), senderId: String(value.senderId ?? value.userId ?? ''), text: value.text ?? value.body ?? '', createdAt: value.createdAt };
}
function matchFromApi(value) {
  if (!value) return null;
  const partner = value.partner || value.contact || value.otherUser || {};
  return {
    ...clone(value), id: String(value.id),
    property: propertyFromApi(value.property), search: searchFromApi(value.search ?? value.searchRequest),
    partner: { ...clone(partner), accountType:normalizeAccountType(partner.accountType), id: String(partner.id ?? partner.userId ?? ''), name: partner.name || partner.displayName || '', avatar: partner.avatar || initials(partner.name || partner.displayName), email: partner.email || '', phone: partner.phone || partner.phoneNumber || '' },
    messages: rows(value.messages).map(messageFromApi), unread: Number(value.unread ?? value.unreadCount ?? 0)
  };
}

export class ApiModel {
  constructor(config) { this.mode = 'api'; this.baseUrl = apiBase(config.baseUrl); this.token = config.token; this.active = null; }
  call(path, method, body) { return request(this.baseUrl, this.token, path, method, body); }
  async getState() {
    const [profile, entities, ledgerResponse] = await Promise.all([this.call('/me'), this.call('/me/entities'), this.call('/credits/ledger')]);
    const user = profile.user || profile;
    const rawActive = entities.active || entities.activeEntity || profile.active || profile.activeEntity;
    const active = rawActive ? { kind: String(rawActive.kind).toLowerCase() === 'property' ? 'property' : 'search', id: String(rawActive.id ?? rawActive.entityId ?? '') || null } : { kind: String(profile.activeKind).toLowerCase() === 'property' ? 'property' : 'search', id: profile.activeEntityId == null ? null : String(profile.activeEntityId) };
    this.active = active;
    return {
      user: { accountType:normalizeAccountType(user.accountType), id: String(user.id), name: user.name || user.displayName || '', email: user.email || '', phone: user.phone || user.phoneNumber || '', avatar: user.avatar || initials(user.name || user.displayName) },
      credits: Number(profile.credits ?? profile.creditBalance ?? profile.balance ?? user.credits ?? 0), active,
      properties: rows(entities.properties).map(propertyFromApi), searches: rows(entities.searches || entities.searchRequests).map(searchFromApi),
      decisions: rows(entities.decisions || profile.decisions).map(d=>({...clone(d),id:String(d.id),actorId:String(d.actorId),propertyId:String(d.propertyId),searchId:String(d.searchId??d.searchRequestId),property:propertyFromApi(d.property),search:searchFromApi(d.search??d.searchRequest)})),
      ledger: rows(ledgerResponse.ledger || ledgerResponse).map(entry => ({ ...clone(entry), amount: Number(entry.amount ?? entry.delta ?? 0), description: entry.description || entry.reason || '', createdAt: entry.createdAt })),
      createdAt: user.createdAt,
      unreadNotificationCount:Number(profile.unreadNotificationCount??user.unreadNotificationCount??0),
      likeCost:active?.id?likeCost(user.accountType,active.kind):0,
      reportedOwnerIds:[...new Set((Array.isArray(entities.reportedOwnerIds)?entities.reportedOwnerIds:[]).map(String))],
      reportedEntities:reportSummaries(entities.reportedEntities)
    };
  }
  async feed() {
    if (!this.active) await this.getState();
    if (!this.active?.id) return [];
    const response = await this.call('/feed');
    return rows(response).map(item => {
      const rawProperty = item.property, rawSearch = item.search || item.searchRequest;
      const propertyId = String(item.propertyId ?? rawProperty?.id ?? (this.active.kind === 'property' ? this.active.id : item.id));
      const searchId = String(item.searchId ?? item.searchRequestId ?? rawSearch?.id ?? (this.active.kind === 'search' ? this.active.id : item.id));
      const isProperty = this.active.kind === 'search';
      const entity = isProperty ? propertyFromApi(rawProperty || item) : searchFromApi(rawSearch || item);
      return { ...entity, kind: isProperty ? 'property' : 'search', score: Math.round(Number(item.compatibilityScore ?? item.score ?? 100)), reasons: clone(item.reasons || []), pair: { propertyId, searchId }, likedYou: !!(item.likedYou ?? item.hasLiked), ...(isProperty ? {} : { buyerName: item.buyerName || entity.buyerName || 'Érdeklődő', avatar: item.avatar || entity.avatar || 'É', financing: item.financing || entity.financing }) };
    });
  }
  async incomingLikes(options={}) {
    const {offset,limit}=normalizeIncomingPagination(options);
    const query=new URLSearchParams({offset:String(offset),limit:String(limit)});
    const response=await this.call('/incoming-likes?'+query);
    const rawActive=response?.active;
    const active=rawActive&&['property','search'].includes(rawActive.kind)&&rawActive.id!=null?{kind:rawActive.kind,id:String(rawActive.id)}:null;
    const items=active?rows(response).map(item=>{
      const candidate=candidateFromApi(item,active.kind);
      if(candidate.kind==='property')candidate.address='';
      return {...candidate,likedYou:true,likedAt:item.likedAt,myDecision:['liked','passed'].includes(item.myDecision)?item.myDecision:null,matchId:item.matchId==null?null:String(item.matchId),compatible:item.compatible!==false};
    }):[];
    return {active,items,total:Number(response?.total??items.length),offset:Number(response?.offset??offset),limit:Number(response?.limit??limit),hasMore:!!response?.hasMore,likeCost:Number(response?.likeCost??0)};
  }
  async notifications(options={}) {
    const {offset,limit}=normalizeIncomingPagination(options);
    const query=new URLSearchParams({offset:String(offset),limit:String(limit)});
    const response=await this.call('/notifications?'+query);
    const items=rows(response).map(notificationFromApi);
    return {items,total:Number(response?.total??items.length),unreadCount:Number(response?.unreadCount??0),offset:Number(response?.offset??offset),limit:Number(response?.limit??limit),hasMore:!!response?.hasMore};
  }
  async markNotificationRead(id) {
    if(typeof id!=='string'||!id.trim())throw new Error('Érvénytelen értesítés.');
    return notificationFromApi(await this.call(`/notifications/${encodeURIComponent(id)}/read`,'PUT'));
  }
  async decide(item, liked) {
    const result = await this.call('/decisions', 'POST', { propertyId: item.pair.propertyId, searchRequestId: item.pair.searchId, liked: inputBoolean(liked) });
    let match = result.match ? matchFromApi(result.match) : null;
    if (!match && result.matchId) match = (await this.matches()).find(m => m.id === String(result.matchId)) || null;
    return { match, charged: Number(result.charged ?? result.creditsSpent ?? result.creditCost ?? 0) };
  }
  async activate(kind, id) { const result = await this.call('/me/active', 'PUT', { kind, id }); this.active = { kind, id }; return result; }
  async saveEntity(kind, data, id) {
    const route = kind === 'property' ? '/properties' : '/searches';
    const result = await this.call(`${route}${id ? `/${encodeURIComponent(id)}` : ''}`, id ? 'PUT' : 'POST', kind === 'property' ? propertyToApi(data,!!id) : searchToApi(data));
    return kind === 'property' ? propertyFromApi(result) : searchFromApi(result);
  }
  async deleteEntity(kind, id) { const result = await this.call(`/${kind === 'property' ? 'properties' : 'searches'}/${encodeURIComponent(id)}`, 'DELETE'); this.active = null; return result; }
  async reportAccount(entityKind,entityId,reason) {
    if(!['property','search'].includes(entityKind)||typeof entityId!=='string'||!entityId.trim())throw new Error('Érvénytelen jelentési profil.');
    return this.call('/reports','POST',{entityKind,entityId,reason:normalizeReportReason(reason)});
  }
  async updateProfile(data) { return this.call('/me', 'PUT', { name: data.name, email: data.email, phone: data.phone }); }
  async buyDemoCredits(amount) { return this.call('/credits/demo-topup', 'POST', { amount: Number(amount) }); }
  async createCheckout(amount) {
    const creditAmount = inputNumber(amount, 'kreditmennyiség');
    if (!Number.isInteger(creditAmount) || creditAmount <= 0) throw new Error('A kreditmennyiség pozitív egész szám legyen.');
    const result = await this.call('/credits/checkout', 'POST', { amount: creditAmount });
    let checkoutUrl;
    try { checkoutUrl = new URL(result?.checkoutUrl); } catch { throw new Error('A fizetési szolgáltató nem adott érvényes fizetési címet.'); }
    if (checkoutUrl.protocol !== 'https:' || checkoutUrl.username || checkoutUrl.password) throw new Error('A fizetési cím kizárólag biztonságos HTTPS-cím lehet.');
    return { checkoutUrl: checkoutUrl.href };
  }
  async matches() { return rows(await this.call('/matches')).map(matchFromApi); }
  async sendMessage(matchId, text) { return messageFromApi(await this.call(`/matches/${encodeURIComponent(matchId)}/messages`, 'POST', { text: String(text).trim() })); }
  async markRead() { return true; }
  async reset() { throw new Error('A valódi API-adatok a demó visszaállításával nem törölhetők. A demóhoz bontsd az API-kapcsolatot.'); }
}

const regionById = id => regions.find(region=>region.id===id)||null;
const nullableNumber = value => value==null||value===''?null:(Number.isFinite(Number(value))?Number(value):null);
function landingFromApi(value) {
  const region=regionById(value?.region?.id);
  const publicType=value=>['Lakás','Ház','Telek','Nyaraló','Garázs','Iroda','Üzlethelyiség','Egyéb'].includes(value)?value:'Ingatlan';
  return {
    regions:regions.map(region=>({...region})),region:clone(region),scope:region?'region':'national',
    searches:rows(value?.searches).slice(0,8).map((item,index)=>({key:String(item.key??`search-${index+1}`),title:String(item.title||'Ingatlant keresnek'),type:publicType(item.type),locations:(Array.isArray(item.locations)?item.locations:[]).filter(location=>typeof location==='string').slice(0,50),minPrice:millions(nullableNumber(item.minPrice)),maxPrice:millions(nullableNumber(item.maxPrice)),minArea:nullableNumber(item.minArea),maxArea:nullableNumber(item.maxArea),minRooms:nullableNumber(item.minRooms),maxRooms:nullableNumber(item.maxRooms),ownerAccountType:normalizeAccountType(item.ownerAccountType)})),
    properties:rows(value?.properties).slice(0,4).map((item,index)=>({key:String(item.key??`property-${index+1}`),title:String(item.title||'Eladó ingatlan'),type:publicType(item.type),location:String(item.location||''),price:millions(nullableNumber(item.price)),area:nullableNumber(item.area),wholeRooms:nullableNumber(item.wholeRooms),halfRooms:nullableNumber(item.halfRooms),rooms:nullableNumber(item.rooms),lotArea:nullableNumber(item.lotArea),ownerAccountType:normalizeAccountType(item.ownerAccountType)}))
  };
}
export async function fetchLanding({region}={}) {
  const selected=region==null||region===''?null:regionById(region);
  if(region!=null&&region!==''&&!selected)throw new Error('Válassz egy érvényes régiót.');
  if(!hostedMode())return {regions:regions.map(region=>({...region})),...demoLanding(selected)};
  const query=selected?'?'+new URLSearchParams({region:selected.id}):'';
  return landingFromApi(await request(hostedApiBase(),null,'/public/landing'+query));
}
function normalizedRegionLabel(value) {
  return String(value||'').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().replace(/\b(county|megye|varmegye)\b/g,'').replace(/[^a-z0-9]/g,'').replace(/^csongrad$/,'csongradcsanad');
}
/** Coarse IP lookup only; never requests device location or retains the provider payload. */
export async function detectLandingRegion(regionOptions=regions) {
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),3000);
  try {
    const response=await fetch('https://get.geojs.io/v1/ip/geo.json',{credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',redirect:'error',headers:{Accept:'application/json'},signal:controller.signal});
    if(!response.ok)return null;
    const payload=await response.json();
    if(payload?.country_code!=='HU'||typeof payload.region!=='string')return null;
    const label=normalizedRegionLabel(payload.region);
    return (Array.isArray(regionOptions)?regionOptions:[]).find(region=>regionById(region?.id)&&normalizedRegionLabel(region.label)===label)?.id||null;
  } catch {return null;}
  finally {clearTimeout(timeout);}
}

export function getModel() {
  const config = readConfig();
  if (hostedMode()) return config && config.baseUrl === hostedApiBase() ? new ApiModel(config) : null;
  return config ? new ApiModel(config) : demoModel;
}
export async function connectApi(baseUrl, email, password, registerData) {
  const base = apiBase(baseUrl);
  if (hostedMode() && base !== hostedApiBase()) throw new Error('Ehhez a munkatérhez a saját webcímén jelentkezhetsz be.');
  const registration=registerData?{...registerData,accountType:normalizeAccountType(registerData.accountType,{strict:true})}:{};
  const result = await request(base, null, registerData ? '/auth/register' : '/auth/login', 'POST', { ...registration, email: String(email).trim(), password: String(password) });
  const token = result?.token || result?.accessToken;
  if (!token) throw new Error('Az API nem küldött hitelesítési tokent.');
  const config = { baseUrl: base, token };
  const adapter = new ApiModel(config);
  await adapter.getState();
  try { globalThis.localStorage.setItem(API_CONFIG_KEY, JSON.stringify(config)); } catch { throw new Error('A kapcsolat nem menthető a böngésző helyi tárhelyére.'); }
  return adapter;
}
export function disconnectApi() { try { globalThis.localStorage?.removeItem(API_CONFIG_KEY); } catch { throw new Error('A mentett API-kapcsolat nem törölhető.'); } return hostedMode() ? null : demoModel; }
export function getApiConnection() { const config = readConfig(); return config ? { baseUrl: config.baseUrl } : null; }
