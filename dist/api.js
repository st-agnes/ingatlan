import {assertDescriptionContactFree,containsContactDetails} from './contact-policy.js';
import { model as demoModel, demoLanding, demoPublicListing } from './model.js';
import {publicFirstName,publicTitle} from './public-profile.js';
import {FEEDBACK_OPTIONS,FEEDBACK_PACKAGE_SIZES,FEEDBACK_QUESTION,feedbackTitle} from './feedback.js';
import { regions } from './regions-data.js';
import {searchSpecificity} from './matching.js';
import { getLocation, MAX_SEARCH_LOCATIONS, resolveLegacyLocations, isPropertyLocation, registerLocations, isStreetId, streetBelongsToLocation } from './locations.js';
import {normalizePropertyAttributes, normalizeSearchAttributes} from './attributes.js';
import {normalizeAccountType,likeCost,normalizeReportReason,normalizeListingProfilePagination,normalizeIncomingPagination,REPORT_REASON_OPTIONS} from './accounts.js';
import {sanitizeTeaserPrefill,originFromListing,prefillFromSearchClone} from './onboarding.js';

export const API_CONFIG_KEY = 'otthonra.api';
export const AUTH_ATTEMPT_KEY = 'otthonra.auth.attempt';
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
// This public, credential-free nonce coordinates pending authentication across tabs.
// Logout also starts a new generation, invalidating every older in-flight login.
function beginAuthAttempt() {
  const attempt=globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
  const storage=globalThis.localStorage;
  let initialConfig;
  try { if (!storage?.setItem) throw new Error();initialConfig=storage.getItem(API_CONFIG_KEY);storage.setItem(AUTH_ATTEMPT_KEY,attempt); } catch { throw new Error('A munkamenet nem menthető a böngésző helyi tárhelyére.'); }
  return {storage,attempt,initialConfig};
}
function requireCurrentAuthAttempt({storage,attempt,initialConfig}) {
  let current,currentConfig;
  try { current=storage.getItem(AUTH_ATTEMPT_KEY);currentConfig=storage.getItem(API_CONFIG_KEY); } catch { throw new Error('A böngésző helyi tárhelye nem érhető el.'); }
  if (current !== attempt || currentConfig !== initialConfig) {
    const error=new Error('A munkamenet időközben megváltozott. A legutóbbi bejelentkezést vagy kijelentkezést használjuk.');
    error.code='AUTH_ATTEMPT_SUPERSEDED';throw error;
  }
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
function readCancelled() {
  const error = new Error('Az elavult adatlekérést megszakítottuk.');
  error.code = 'API_READ_CANCELLED';
  return error;
}
function requireCurrentRead(signal) { if (signal?.aborted) throw readCancelled(); }
async function request(baseUrl, token, path, method = 'GET', body, {signal} = {}) {
  // A view may cancel its reads. Never attach its lifetime to a write: the
  // server may already have accepted that operation when navigation changes.
  const readSignal = method === 'GET' ? signal : null;
  requireCurrentRead(readSignal);
  const controller = new AbortController();
  const cancelRead = () => controller.abort();
  let abortListener;
  const aborted = new Promise((_resolve, reject) => {
    abortListener = () => {
      if (readSignal?.aborted) reject(readCancelled());
      else { const error = new Error('Request aborted'); error.name = 'AbortError'; reject(error); }
    };
    controller.signal.addEventListener('abort', abortListener, {once:true});
  });
  readSignal?.addEventListener('abort', cancelRead, {once:true});
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    requireCurrentRead(readSignal);
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const transport = async () => {
      const response = await fetch(`${baseUrl}/api${path}`, { method, headers, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: controller.signal });
      requireCurrentRead(readSignal);
      const raw = await response.text();
      requireCurrentRead(readSignal);
      let payload = null;
      if (raw) { try { payload = JSON.parse(raw); } catch { if (response.ok) throw new Error('Az API érvénytelen JSON-választ küldött.'); } }
      if (!response.ok) { const error = new Error(errorMessage(payload, response.status)); error.status = response.status; throw error; }
      return payload;
    };
    return await Promise.race([transport(), aborted]);
  } catch (error) {
    if (readSignal?.aborted || error.code === 'API_READ_CANCELLED') throw readCancelled();
    if (error.name === 'AbortError') throw new Error('Az API nem válaszolt 20 másodpercen belül. Próbáld újra.');
    if (error instanceof TypeError) throw new Error('Az API nem érhető el. Ellenőrizd a címet, a szerver futását és a CORS-beállításokat.');
    throw error;
  } finally {
    clearTimeout(timeout);
    readSignal?.removeEventListener('abort', cancelRead);
    controller.signal.removeEventListener('abort', abortListener);
  }
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
  const legacyEmpty = !strict && uniqueIds != null && (uniqueIds.length === 0 || kind === 'property' && uniqueIds.length === 1 && (uniqueIds[0] == null || typeof uniqueIds[0] === 'string' && !uniqueIds[0].trim()));
  const malformedSearchIds = kind === 'search' && value.locationIds != null
    && (!Array.isArray(value.locationIds) || value.locationIds.length > MAX_SEARCH_LOCATIONS);
  let selected = malformedSearchIds ? [] : uniqueIds == null || legacyEmpty
    ? resolveLegacyLocations(kind === 'search' ? {...value, districts:inputStrings(value.districts)} : value)
    : uniqueIds.map(getLocation).filter(Boolean);
  if(kind === 'search' && uniqueIds?.length && selected.length !== uniqueIds.length) selected=[];
  const locations = kind === 'property' ? selected.filter(isPropertyLocation) : selected;
  if (strict && (!locations.length || (kind === 'search' && locations.length > MAX_SEARCH_LOCATIONS)
      || (uniqueIds != null && locations.length !== uniqueIds.length))) throw new Error('Válassz érvényes települést vagy budapesti kerületet a találati listából.');
  return locations;
}

function privateAddressFromApi(value) {
  if (!value || typeof value !== 'object') return null;
  return {
    street: inputText(value.street), houseNumber: inputText(value.houseNumber), postalCode: inputText(value.postalCode),
    ...(isStreetId(value.streetId) ? {streetId:value.streetId} : {}),
    latitude: value.latitude == null ? null : numeric(value.latitude), longitude: value.longitude == null ? null : numeric(value.longitude),
    geocodedAt: value.geocodedAt ?? null, provider: inputText(value.provider), quality: inputText(value.quality), geocodingStatus: inputText(value.geocodingStatus)
  };
}
function propertyFromApi(value, own = false) {
  if (!value) return null;
  const location = entityLocations(value, 'property')[0] || null;
  const declaredId = value.locationId ?? value.location?.id;
  const hideStreet=value.hideStreet!==false,hideHouseNumber=hideStreet||value.hideHouseNumber!==false;
  const visibleStreet=!hideStreet?inputText(value.street):'',visibleNumber=!hideHouseNumber?inputText(value.houseNumber):'';
  const publicAddress=visibleStreet?[visibleStreet,visibleNumber].filter(Boolean).join(' '):!hideStreet&&!hideHouseNumber?inputText(value.address):'';
  return normalizePropertyAttributes({
    id: String(value.id), publicListingKey:originFromListing('property',value.publicListingKey)?.key??null, ownerId: String(value.ownerId ?? value.userId ?? ''), ownerAccountType:normalizeAccountType(value.ownerAccountType), ownerFirstName:publicFirstName(value.ownerFirstName),
    title: value.title || '', locationId:location?.id ?? declaredId ?? '', location:clone(location), city: location?.city ?? value.city ?? '', district: location ? location.district || '' : value.district ?? '', neighborhood: value.neighborhood || '', address: own ? value.address || '' : publicAddress,hideStreet,hideHouseNumber,...(!own&&!hideStreet?{street:visibleStreet,...(!hideHouseNumber?{houseNumber:visibleNumber}:{})}:{}), description: value.description || '', createdAt: value.createdAt,
    neighborhoodIds: [...new Set((Array.isArray(value.neighborhoodIds) ? value.neighborhoodIds : []).filter(id => getLocation(id)?.kind === 'neighborhood'))],
    ...(own ? {addressDetails:privateAddressFromApi(value.addressDetails)} : {}),
    type: value.type || value.propertyType || 'Lakás',
    price: millions(value.priceHuf ?? value.price), area: numeric(value.area ?? value.areaSqm ?? value.sizeSqm), rooms: numeric(value.rooms ?? value.roomCount), wholeRooms:value.wholeRooms, halfRooms:value.halfRooms,
    lotArea: numeric(value.lotArea ?? value.lotAreaSqm ?? null), floor: numeric(value.floor), floorIsUpperRange:value.floorIsUpperRange, buildingFloors:numeric(value.buildingFloors), condition: value.condition || '', building: value.building || value.buildingMaterial || '',
    balcony: value.balcony??value.hasBalcony??null, elevator: !!(value.elevator ?? value.hasElevator),
    constructionAge:value.constructionAge, view:value.view, ceilingHeight:value.ceilingHeight,
    heatingType:value.heatingType, secondaryHeatingType:value.secondaryHeatingType, insulated:value.insulated, energyRating:value.energyRating,energyRatingScheme:value.energyRatingScheme,isAttic:value.isAttic,
    airConditioning:value.airConditioning, privateGarden:value.privateGarden, sharedGarden:value.sharedGarden, solarPanels:value.solarPanels, parkingType:value.parkingType, parkingTypes:value.parkingTypes,
    images: clone(value.images || value.imageUrls || []), archived: !!(value.archived ?? value.isArchived)
  });
}
function searchFromApi(value,own=false) {
  if (!value) return null;
  // Street metadata travels with selected public search locations, not a browser-wide catalogue.
  registerLocations(value.locations);
  const locations = entityLocations(value, 'search');
  // Retain explicit invalid selections so the matcher cannot revive them through a legacy city.
  const declaredIds = value.locationIds != null ? clone(value.locationIds) : Array.isArray(value.locations) ? value.locations.map(location=>location?.id) : null;
  const locationIds = declaredIds == null || Array.isArray(declaredIds) && !declaredIds.length ? locations.map(location=>location.id) : declaredIds;
  const search = normalizeSearchAttributes({
    id: String(value.id), publicListingKey:originFromListing('search',value.publicListingKey)?.key??null, ownerId: String(value.ownerId ?? value.userId ?? ''), ownerAccountType:normalizeAccountType(value.ownerAccountType), ownerFirstName:publicFirstName(value.ownerFirstName),
    title: value.title || '', locationIds, locations:clone(locations), city: locations[0]?.city ?? value.city ?? '', districts: locations.filter(location=>location.city===locations[0]?.city&&location.district).map(location=>location.district), description: value.description || '', moveIn: value.moveIn || '', buyerName: value.buyerName || '', financing: value.financing || '', avatar: value.avatar || '', createdAt: value.createdAt,
    type: value.type || value.propertyType || 'Lakás',
    minPrice: millions(value.minPriceHuf ?? value.minPrice ?? null), maxPrice: millions(!own&&value.publicMaxPrice!=null?value.publicMaxPrice:value.maxPriceHuf ?? value.maxPrice ?? null),
    ...(own&&Object.hasOwn(value,'publicMaxPrice')?{publicMaxPrice:millions(value.publicMaxPrice)}:{}),
    minArea: numeric(value.minArea ?? value.minAreaSqm ?? null), maxArea: numeric(value.maxArea ?? value.maxAreaSqm ?? null),
    minRooms: numeric(value.minRooms ?? null), maxRooms: numeric(value.maxRooms ?? null),
    balcony: !!(value.balcony ?? value.requiresBalcony), elevator: !!(value.elevator ?? value.requiresElevator),
    conditions:value.conditions ?? (value.condition ? [value.condition] : []),
    buildings:value.buildings ?? (value.building ? [value.building] : []),
    constructionAges:value.constructionAges, views:value.views, ceilingHeight:value.ceilingHeight, floors:value.floors, heatingTypes:value.heatingTypes,
    excludeTopFloor:value.excludeTopFloor, excludeGroundFloorAndBelow:value.excludeGroundFloorAndBelow,atticPreference:value.atticPreference,minEnergyRating:value.minEnergyRating,
    airConditioning:value.airConditioning, privateGarden:value.privateGarden, sharedGarden:value.sharedGarden,
    archived: !!(value.archived ?? value.isArchived)
  });
  search.searchSpecificity = Number(value.searchSpecificity ?? searchSpecificity(search));
  return search;
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
function requiredPhone(value) {
  if(typeof value!=='string')throw new Error('A telefonszám megadása kötelező.');
  const phone=inputText(value);
  if(!phone)throw new Error('A telefonszám megadása kötelező.');
  if(phone.length>40)throw new Error('A telefonszám legfeljebb 40 karakter lehet.');
  return phone;
}
const inputStrings = value => Array.isArray(value) ? value.map(inputText).filter(Boolean) : inputText(value).split(/[,\n]/).map(inputText).filter(Boolean);
function propertyToApi(value, updating = false) {
  const type = inputText(value.type) || 'Lakás';
  const attributes = normalizePropertyAttributes({...value,type},{strict:true,allowLegacyUnknown:updating});
  const countsSupplied = [value.wholeRooms,value.halfRooms].some(count=>count != null && String(count).trim() !== '');
  const floor = type === 'Ház' ? null : attributes.floor;
  const images = Array.isArray(value.images) ? value.images.map(inputText).filter(Boolean) : inputText(value.images).split('\n').map(inputText).filter(Boolean);
  if (images.length > 12 || images.some(image => { try { return new URL(image).protocol !== 'https:' || image.length > 2000; } catch { return true; } })) throw new Error('Az API-hoz legfeljebb 12 HTTPS-képhivatkozás adható meg.');
  const price = inputNumber(value.price, 'ár'), area = inputNumber(value.area, 'alapterület'), rooms = inputNumber(attributes.rooms, 'szobaszám');
  if (price <= 0 || area <= 0 || rooms <= 0 || rooms > 1000) throw new Error('Az ár, az alapterület és a szobaszám legyen pozitív szám.');
  const location = entityLocations(value, 'property', true)[0];
  const lotArea = type === 'Ház' ? inputNumber(value.lotArea, 'telekméret') : null;
  if (lotArea != null && (lotArea <= 0 || lotArea > 10000000)) throw new Error('A telekméret pozitív szám legyen.');
  const street = inputText(value.street ?? value.addressDetails?.street), houseNumber = inputText(value.houseNumber ?? value.addressDetails?.houseNumber);
  const postalCode = inputText(value.postalCode ?? value.addressDetails?.postalCode);
  if (!street || !houseNumber) throw new Error('Add meg az ingatlan utcáját és házszámát.');
  if (street.length > 180 || /\p{Cc}/u.test(street) || !/^\d[\p{L}\d./ -]{0,31}$/u.test(houseNumber)
      || postalCode && !/^\d{4}$/.test(postalCode)) throw new Error('Adj meg érvényes utcát, házszámot és négyjegyű irányítószámot.');
  const streetId = value.streetId ?? value.addressDetails?.streetId ?? null;
  if (streetId != null && streetId !== '' && (!isStreetId(streetId)
      || getLocation(streetId) && !streetBelongsToLocation(getLocation(streetId), location))) throw new Error('Válassz az ingatlan településéhez tartozó utcát.');
  return {
    title: inputText(value.title), locationId:location.id, city:location.city, district:location.district || '', street, houseNumber, postalCode,
    ...(streetId ? {streetId} : {}), address: inputText(value.address), description: inputText(value.description),
    type, price: Math.round(price * MILLION), area, rooms, wholeRooms:countsSupplied ? attributes.wholeRooms : null, halfRooms:countsSupplied ? attributes.halfRooms : null, lotArea, floor, floorIsUpperRange:attributes.floorIsUpperRange, buildingFloors:attributes.buildingFloors,
    condition:attributes.condition, building:attributes.building,
    constructionAge:attributes.constructionAge, view:attributes.view, ceilingHeight:attributes.ceilingHeight,
    heatingType:attributes.heatingType, secondaryHeatingType:attributes.secondaryHeatingType, insulated:attributes.insulated, energyRating:attributes.energyRating,
    airConditioning:attributes.airConditioning, privateGarden:attributes.privateGarden, sharedGarden:attributes.sharedGarden,
    solarPanels:attributes.solarPanels, parkingType:attributes.parkingType, parkingTypes:attributes.parkingTypes,
    ...(Object.hasOwn(value,'hideStreet')?{hideStreet:attributes.hideStreet}:{}),...(Object.hasOwn(value,'hideHouseNumber')?{hideHouseNumber:attributes.hideHouseNumber}:{}),
    ...(Object.hasOwn(value,'isAttic')?{isAttic:attributes.isAttic}:{}),...(Object.hasOwn(value,'energyRatingScheme')?{energyRatingScheme:attributes.energyRatingScheme}:{}),
    balcony: attributes.balcony, elevator: type === 'Ház' ? false : inputBoolean(value.elevator), images, archived: inputBoolean(value.archived)
  };
}
function searchToApi(value) {
  const type = inputText(value.type) || 'Lakás';
  const attributes = normalizeSearchAttributes({...value,type},{strict:true});
  const minPrice = inputNumber(value.minPrice, 'minimumár', true), maxPrice = inputNumber(value.maxPrice, 'maximumár', true);
  const publicPrice=inputNumber(value.publicMaxPrice,'publikus maximumár',true);
  if(publicPrice!=null&&(publicPrice<=0||publicPrice>1000000||maxPrice!=null&&publicPrice>maxPrice||minPrice!=null&&publicPrice<minPrice))throw new Error('A publikus maximumár a minimumár és a saját maximumár közé essen.');
  const locations = entityLocations(value, 'search', true);
  const minArea = inputNumber(value.minArea, 'minimum alapterület', true), maxArea = inputNumber(value.maxArea, 'maximum alapterület', true);
  const minRooms = inputNumber(value.minRooms, 'minimum szobaszám', true), maxRooms = inputNumber(value.maxRooms, 'maximum szobaszám', true);
  for (const [min,max] of [[minPrice,maxPrice],[minArea,maxArea],[minRooms,maxRooms]]) {
    if ((min != null && min < 0) || (max != null && max <= 0) || (min != null && max != null && min > max)) throw new Error('A minimum érték nem lehet nagyobb a maximumnál; a korlátok érvényes számok legyenek.');
  }
  return {
    title: inputText(value.title), locationIds:locations.map(location=>location.id), city:locations[0].city, districts:locations.filter(location=>location.city===locations[0].city&&location.district).map(location=>location.district), description: inputText(value.description), type: inputText(value.type) || 'Lakás',
    minPrice: minPrice == null ? null : Math.round(minPrice * MILLION), maxPrice: maxPrice == null ? null : Math.round(maxPrice * MILLION),
    ...(Object.hasOwn(value,'publicMaxPrice')?{publicMaxPrice:publicPrice==null?null:Math.round(publicPrice*MILLION)}:{}),
    minArea, maxArea, minRooms, maxRooms,
    conditions:attributes.conditions, buildings:attributes.buildings, constructionAges:attributes.constructionAges,
    views:attributes.views, ceilingHeight:attributes.ceilingHeight, floors:attributes.floors, heatingTypes:attributes.heatingTypes,
    excludeTopFloor:attributes.excludeTopFloor, excludeGroundFloorAndBelow:attributes.excludeGroundFloorAndBelow,
    airConditioning:attributes.airConditioning, privateGarden:attributes.privateGarden, sharedGarden:attributes.sharedGarden,
    ...(Object.hasOwn(value,'atticPreference')?{atticPreference:attributes.atticPreference}:{}),...(Object.hasOwn(value,'minEnergyRating')?{minEnergyRating:attributes.minEnergyRating}:{}),
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
const matchDetailKeys=new Set(['location','type','price','rooms','area','condition','floor','excludeTopFloor','excludeGroundFloorAndBelow','airConditioning','privateGarden','elevator','balcony','building','heatingType','atticPreference','minEnergyRating','constructionAge','ceilingHeight','view']);
function matchDetailsFromApi(value) {
  if(!Array.isArray(value))return [];
  return value.filter(item=>item&&matchDetailKeys.has(item.key)&&typeof item.matches==='boolean'
    &&['label','expected','actual'].every(field=>typeof item[field]==='string')).slice(0,30)
    .map(({key,label,expected,actual,matches})=>({key,label:label.slice(0,80),expected:expected.slice(0,3000),actual:actual.slice(0,3000),matches}));
}
function candidateFromApi(item,activeKind) {
  const rawProperty=item.property,rawSearch=item.search||item.searchRequest;
  const propertyId=String(item.propertyId??rawProperty?.id??''),searchId=String(item.searchId??item.searchRequestId??rawSearch?.id??'');
  const property=activeKind==='search';
  const entity=property?propertyFromApi(rawProperty||item):searchFromApi(rawSearch||item);
  const score=Math.round(Number(item.compatibilityScore??item.score??100));
  return {...entity,kind:property?'property':'search',score,isExact:item.isExact??score===100,searchSpecificity:Number(item.searchSpecificity??entity.searchSpecificity??0),valueForMoney:Number(item.valueForMoney??0),reasons:clone(item.reasons||[]),matchDetails:matchDetailsFromApi(item.matchDetails),pair:{propertyId,searchId},likedYou:!!(item.likedYou??item.hasLiked)};
}
const notificationPages = new Set(['incoming','messages','insights','credits']);
const notificationReference = value => typeof value==='string'&&value.trim()&&value.length<=200?value:null;
function notificationTargetFromApi(value,kind='') {
  if(!value||typeof value!=='object'||Array.isArray(value))return ['like_refund','feedback_refund','credit_added'].includes(kind)?{page:'credits',entityKind:null,entityId:null,propertyId:null,searchRequestId:null,matchId:null}:null;
  if(!notificationPages.has(value.page))return null;
  return {page:value.page,entityKind:['property','search'].includes(value.entityKind)?value.entityKind:null,entityId:notificationReference(value.entityId),propertyId:notificationReference(value.propertyId),searchRequestId:notificationReference(value.searchRequestId),matchId:notificationReference(value.matchId)};
}
function notificationFromApi(value={}) {
  const kind=String(value.kind||'');
  const result={id:String(value.id),kind,amount:Number(value.amount||0),text:String(value.text||''),decisionId:value.decisionId==null?null:String(value.decisionId),feedbackPackageId:value.feedbackPackageId==null?null:String(value.feedbackPackageId),createdAt:value.createdAt,readAt:value.readAt??null,target:notificationTargetFromApi(value.target,kind)};
  if(Number.isSafeInteger(value.unreadCount)&&value.unreadCount>=0)result.unreadCount=value.unreadCount;
  return result;
}
function notificationContextFromApi(value={}) {
  const notification=notificationFromApi(value.notification),target=notificationTargetFromApi(value.target??notification.target,notification.kind);
  let item=null;
  if(value.available===true&&notification.kind==='incoming_like'&&target?.page==='incoming'&&target.entityKind&&target.entityId&&value.item){
    const raw=value.item,candidate=candidateFromApi(raw,target.entityKind);
    if(candidate.kind==='property')candidate.address='';
    item={...candidate,likedYou:true,likedAt:raw.likedAt,myDecision:['liked','passed'].includes(raw.myDecision)?raw.myDecision:null,matchId:raw.matchId==null?null:String(raw.matchId),compatible:raw.compatible!==false};
  }
  const available=value.available===true&&!!target&&(target.page!=='incoming'||!!item);
  return {notification,available,target,canActivate:available&&value.canActivate===true&&!!target.entityKind&&!!target.entityId,item};
}
const feedbackReason=reason=>FEEDBACK_OPTIONS.find(option=>option.value===reason);
const feedbackCount=value=>Number.isFinite(Number(value))?Math.max(0,Math.trunc(Number(value))):0;
function feedbackId(value,label='azonosító') {
  if(typeof value!=='string'||!value.trim())throw new Error(`Érvénytelen ${label}.`);
  return value.trim();
}
function feedbackPackageFromApi(value) {
  if(!value||typeof value!=='object')return null;
  const size=feedbackCount(value.size),receivedCount=feedbackCount(value.receivedCount);
  return {id:String(value.id??''),size,receivedCount,remaining:Math.max(0,size-receivedCount),enabled:value.enabled===true,
    createdAt:value.createdAt,expiresAt:value.expiresAt,refundedAt:value.refundedAt??null,refundedCredits:feedbackCount(value.refundedCredits),
    status:['active','completed','expired'].includes(value.status)?value.status:'expired'};
}
function feedbackPromptFromApi(value) {
  if(!value||typeof value!=='object'||typeof value.id!=='string'||!value.id||typeof value.propertyId!=='string'||!value.propertyId)return null;
  const sellerFirstName=publicFirstName(value.sellerFirstName);
  return {id:value.id,propertyId:value.propertyId,sellerFirstName,title:feedbackTitle(sellerFirstName),question:FEEDBACK_QUESTION,
    options:FEEDBACK_OPTIONS.map(option=>({...option})),expiresAt:value.expiresAt};
}
function propertyInsightsFromApi(value) {
  const stats=value?.stats||{},feedback=value?.feedback||{};
  const items=rows(feedback.items).filter(item=>feedbackReason(item.reason)&&item.reason!=='decline').map(item=>({
    id:String(item.id??''),reason:item.reason,label:feedbackReason(item.reason).label,createdAt:item.createdAt
  }));
  const counts=new Map(rows(feedback.reasonCounts).filter(item=>feedbackReason(item.reason)&&item.reason!=='decline').map(item=>[item.reason,feedbackCount(item.count)]));
  return {propertyId:String(value?.propertyId??''),stats:{uniqueViewers:feedbackCount(stats.uniqueViewers),buyerLikes:feedbackCount(stats.buyerLikes),sellerLikes:feedbackCount(stats.sellerLikes),matchedViewers:feedbackCount(stats.matchedViewers),matchRate:Math.max(0,Math.min(100,Number(stats.matchRate)||0))},
    feedback:{total:feedbackCount(feedback.total),items,reasonCounts:FEEDBACK_OPTIONS.filter(option=>option.value!=='decline').map(option=>({reason:option.value,label:option.label,count:counts.get(option.value)||0})),offset:feedbackCount(feedback.offset),limit:feedbackCount(feedback.limit||50),hasMore:feedback.hasMore===true},
    activePackage:feedbackPackageFromApi(value?.activePackage),packages:rows(value?.packages).slice(0,20).map(feedbackPackageFromApi).filter(Boolean),
    packageSizes:[...FEEDBACK_PACKAGE_SIZES],durationDays:14,creditCostPerFeedback:1};
}
function feedbackScenarioFromApi(value) {
  if(value?.available!==true||!['buyer','seller'].includes(value.role))return {available:false};
  return {available:true,role:value.role,propertyId:String(value.propertyId??''),searchId:String(value.searchId??''),
    buyerEmail:String(value.buyerEmail??''),sellerEmail:String(value.sellerEmail??''),feedbackReady:value.feedbackReady===true};
}
function messageFromApi(value) {
  return { ...clone(value), id: String(value.id), senderId: String(value.senderId ?? value.userId ?? ''), text: value.text ?? value.body ?? '', createdAt: value.createdAt };
}
function matchFromApi(value,viewerId) {
  if (!value) return null;
  const partner = value.partner || value.contact || value.otherUser || {};
  const {searchRequest:_legacySearch,...safe}=clone(value);
  return {
    ...safe, id: String(value.id),
    property: propertyFromApi(value.property), search: searchFromApi(value.search ?? value.searchRequest,String((value.search??value.searchRequest)?.ownerId)===viewerId),
    partner: { ...clone(partner), accountType:normalizeAccountType(partner.accountType), id: String(partner.id ?? partner.userId ?? ''), name: partner.name || partner.displayName || '', avatar: partner.avatar || initials(partner.name || partner.displayName), email: partner.email || '', phone: partner.phone || partner.phoneNumber || '' },
    messages: rows(value.messages).map(messageFromApi), unread: Number(value.unread ?? value.unreadCount ?? 0)
  };
}

export class ApiModel {
  constructor(config) { this.mode = 'api'; this.baseUrl = apiBase(config.baseUrl); this.token = config.token; this.active = null; this.userId = null; this.feedbackScenarioCapability = undefined; }
  call(path, method, body, options) { return request(this.baseUrl, this.token, path, method, body, options); }
  async findLocations(query, limit = 8, {kind = 'search'} = {}) {
    if (!['search','property'].includes(kind)) throw new Error('Érvénytelen helyszínválasztó-típus.');
    const count = Number.isFinite(Number(limit)) ? Math.max(0,Math.min(50,Math.trunc(Number(limit)))) : 8;
    if (!String(query ?? '').trim() || !count) return [];
    const parameters = new URLSearchParams({q:String(query).slice(0,120),limit:String(count),kind});
    const locations = registerLocations(rows(await this.call('/locations?' + parameters)));
    return locations.filter(location => kind === 'search' || isPropertyLocation(location)).slice(0,count);
  }
  async findStreets(query, locationId, limit = 8) {
    const location = getLocation(locationId);
    const count = Number.isFinite(Number(limit)) ? Math.max(0,Math.min(50,Math.trunc(Number(limit)))) : 8;
    if (!isPropertyLocation(location) || !String(query ?? '').trim() || !count) return [];
    const parameters = new URLSearchParams({q:String(query).slice(0,120),locationId,limit:String(count)});
    return registerLocations(rows(await this.call('/streets?' + parameters)))
      .filter(street => streetBelongsToLocation(street,location)).slice(0,count);
  }
  async getState({signal}={}) {
    const [profile, entities, ledgerResponse] = await Promise.all([this.call('/me','GET',undefined,{signal}), this.call('/me/entities','GET',undefined,{signal}), this.call('/credits/ledger','GET',undefined,{signal})]);
    requireCurrentRead(signal);
    const user = profile.user || profile;
    this.userId = String(user.id);
    const rawActive = entities.active || entities.activeEntity || profile.active || profile.activeEntity;
    const active = rawActive ? { kind: String(rawActive.kind).toLowerCase() === 'property' ? 'property' : 'search', id: String(rawActive.id ?? rawActive.entityId ?? '') || null } : { kind: String(profile.activeKind).toLowerCase() === 'property' ? 'property' : 'search', id: profile.activeEntityId == null ? null : String(profile.activeEntityId) };
    this.active = active;
    return {
      user: { accountType:normalizeAccountType(user.accountType), id: String(user.id), name: user.name || user.displayName || '', email: user.email || '', phone: user.phone || user.phoneNumber || '', avatar: user.avatar || initials(user.name || user.displayName) },
      credits: Number(profile.credits ?? profile.creditBalance ?? profile.balance ?? user.credits ?? 0), active,
      properties: rows(entities.properties).map(value=>propertyFromApi(value,String(value.ownerId ?? value.userId ?? '')===this.userId)), searches: rows(entities.searches || entities.searchRequests).map(value=>searchFromApi(value,String(value.ownerId??value.userId??'')===this.userId)),
      decisions: rows(entities.decisions || profile.decisions).map(d=>({...Object.fromEntries(Object.entries(clone(d)).filter(([key])=>key!=='searchRequest')),id:String(d.id),actorId:String(d.actorId),propertyId:String(d.propertyId),searchId:String(d.searchId??d.searchRequestId),property:propertyFromApi(d.property,String(d.property?.ownerId)===this.userId),search:searchFromApi(d.search??d.searchRequest,String((d.search??d.searchRequest)?.ownerId)===this.userId)})),
      ledger: rows(ledgerResponse.ledger || ledgerResponse).map(entry => ({ ...clone(entry), amount: Number(entry.amount ?? entry.delta ?? 0), description: entry.description || entry.reason || '', createdAt: entry.createdAt })),
      createdAt: user.createdAt,
      unreadNotificationCount:Number(profile.unreadNotificationCount??user.unreadNotificationCount??0),
      likeCost:active?.id?likeCost(user.accountType,active.kind):0,
      reportedOwnerIds:[...new Set((Array.isArray(entities.reportedOwnerIds)?entities.reportedOwnerIds:[]).map(String))],
      reportedEntities:reportSummaries(entities.reportedEntities)
    };
  }
  async recommendations({includeApproximate=false,signal}={}) {
    requireCurrentRead(signal);
    if (!this.active) await this.getState({signal});
    const requestedActive=this.active?{...this.active}:null;
    if (!requestedActive?.id) return {active:null,items:[],hasApproximate:false,requiresApproximateConsent:false,stage:'empty'};
    const response = await this.call('/feed'+(includeApproximate===true?'?includeApproximate=true':''),'GET',undefined,{signal});
    const rawActive=response?.active;
    const active=Object.hasOwn(response||{},'active')?(rawActive&&['property','search'].includes(rawActive.kind)&&rawActive.id!=null?{kind:rawActive.kind,id:String(rawActive.id)}:null):requestedActive;
    const items=rows(response).map(item=>{
      const candidate=candidateFromApi(item,requestedActive.kind);
      return candidate.kind==='search'?{...candidate,buyerName:item.buyerName||candidate.buyerName||'Érdeklődő',avatar:item.avatar||candidate.avatar||'É',financing:item.financing||candidate.financing}:candidate;
    });
    return {active,items,hasApproximate:!!response?.hasApproximate,requiresApproximateConsent:!!response?.requiresApproximateConsent,
      stage:['exact','approximate','empty'].includes(response?.stage)?response.stage:items.length?'exact':'empty'};
  }
  async feed(options={}) { return (await this.recommendations(options)).items; }
  async getListingContext(kind,key,{signal}={}) {
    if(!originFromListing(kind,key))throw new Error('A hirdetés nem érhető el.');
    const value=await this.call(`/listings/${kind}/${key}/context`,'GET',undefined,{signal});
    requireCurrentRead(signal);
    return listingContextFromApi(kind,value);
  }
  async getListingProfiles(kind,key,{offset=0,limit=50,signal}={}) {
    if(!originFromListing(kind,key))throw new Error('A hirdetés nem érhető el.');
    const page=normalizeListingProfilePagination({offset,limit}),query=new URLSearchParams({offset:String(page.offset),limit:String(page.limit)});
    const value=await this.call(`/listings/${kind}/${key}/profiles?${query}`,'GET',undefined,{signal});
    requireCurrentRead(signal);
    return listingProfilesFromApi(kind,value,page);
  }
  async getListingMap(kind,key,{signal}={}) {
    if(!originFromListing(kind,key))throw new Error('A hirdetés nem érhető el.');
    const value=await request(this.baseUrl,null,`/public/listings/${kind}/${key}/map`,'GET',undefined,{signal});
    requireCurrentRead(signal);
    return listingMapFromApi(kind,value);
  }
  async incomingLikes(options={}) {
    const {offset,limit}=normalizeIncomingPagination(options);
    const query=new URLSearchParams({offset:String(offset),limit:String(limit)});
    const response=await this.call('/incoming-likes?'+query,'GET',undefined,{signal:options.signal});
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
    const response=await this.call('/notifications?'+query,'GET',undefined,{signal:options.signal});
    const items=rows(response).map(notificationFromApi);
    return {items,total:Number(response?.total??items.length),unreadCount:Number(response?.unreadCount??0),offset:Number(response?.offset??offset),limit:Number(response?.limit??limit),hasMore:!!response?.hasMore};
  }
  async markNotificationRead(id) {
    if(typeof id!=='string'||!id.trim())throw new Error('Érvénytelen értesítés.');
    return notificationFromApi(await this.call(`/notifications/${encodeURIComponent(id)}/read`,'PUT'));
  }
  async getNotificationContext(id,{signal}={}) {
    if(typeof id!=='string'||!id.trim())throw new Error('Érvénytelen értesítés.');
    return notificationContextFromApi(await this.call(`/notifications/${encodeURIComponent(id)}/context`,'GET',undefined,{signal}));
  }

  async getPropertyInsights(id,options={}) {
    id=feedbackId(id,'ingatlanazonosító');
    const {offset,limit}=normalizeIncomingPagination(options);
    return propertyInsightsFromApi(await this.call(`/properties/${encodeURIComponent(id)}/insights?${new URLSearchParams({offset:String(offset),limit:String(limit)})}`,'GET',undefined,{signal:options.signal}));
  }
  async getFeedbackScenario({signal}={}) {
    requireCurrentRead(signal);
    if(!hostedMode()||deploymentEnvironment()!=='test')return {available:false};
    if(this.feedbackScenarioCapability===undefined){
      try{const result=await this.call('/test/feedback-scenario','GET',undefined,{signal});requireCurrentRead(signal);this.feedbackScenarioCapability=feedbackScenarioFromApi(result);}
      catch(error){if(error.status!==404)throw error;this.feedbackScenarioCapability={available:false};}
    }
    return clone(this.feedbackScenarioCapability);
  }
  async resetFeedbackScenario() {
    if(!hostedMode()||deploymentEnvironment()!=='test')throw new Error('A visszajelzés-próba csak a tesztkörnyezetben érhető el.');
    const result=feedbackScenarioFromApi(await this.call('/test/feedback-scenario/reset','POST',{}));
    this.feedbackScenarioCapability=result;
    if(result.available)this.active={kind:result.role==='buyer'?'search':'property',id:result.role==='buyer'?result.searchId:result.propertyId};
    return clone(result);
  }
  async buyFeedbackPackage(id,size,requestId) {
    id=feedbackId(id,'ingatlanazonosító');
    if(!FEEDBACK_PACKAGE_SIZES.includes(Number(size)))throw new Error('Válassz 10, 20 vagy 50 visszajelzéses csomagot.');
    if(typeof requestId!=='string'||!(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i).test(requestId)||/^0{8}-0{4}-0{4}-0{4}-0{12}$/.test(requestId))throw new Error('Érvénytelen vásárlási azonosító.');
    const result=await this.call(`/properties/${encodeURIComponent(id)}/feedback-packages`,'POST',{size:Number(size),requestId});
    return {package:feedbackPackageFromApi(result.package),charged:feedbackCount(result.charged),credits:feedbackCount(result.credits)};
  }
  async recordImpression(propertyId,searchId) {
    propertyId=feedbackId(propertyId,'ingatlanazonosító');searchId=feedbackId(searchId,'keresésazonosító');
    const result=await this.call('/impressions','POST',{propertyId,searchRequestId:searchId});
    return {recorded:result.recorded===true};
  }
  async pendingFeedback({signal}={}) { return feedbackPromptFromApi((await this.call('/feedback/pending','GET',undefined,{signal})).feedbackPrompt); }
  async answerFeedback(id,reason) {
    id=feedbackId(id,'visszajelzés-azonosító');
    if(!feedbackReason(reason))throw new Error('Válassz egy visszajelzési lehetőséget.');
    const result=await this.call(`/feedback/${encodeURIComponent(id)}`,'POST',{reason});
    return {accepted:result.accepted===true,alreadyAnswered:result.alreadyAnswered===true};
  }
  async decide(item, liked, {allowApproximate=false,resolveMatch=true}={}) {
    const result = await this.call('/decisions', 'POST', { propertyId: item.pair.propertyId, searchRequestId: item.pair.searchId, liked: inputBoolean(liked), ...(allowApproximate===true?{allowApproximate:true}:{}) });
    let match = result.match ? matchFromApi(result.match,this.userId) : null;
    const matchId = match?.id ?? (result.matchId == null ? null : String(result.matchId).trim() || null);
    if (!match && matchId && resolveMatch !== false) match = (await this.matches()).find(m => m.id === matchId) || null;
    return { match, matchId, charged: Number(result.charged ?? result.creditsSpent ?? result.creditCost ?? 0), feedbackPrompt:feedbackPromptFromApi(result.feedbackPrompt) };
  }
  async activate(kind, id) { const result = await this.call('/me/active', 'PUT', { kind, id }); this.active = { kind, id }; return result; }
  async saveEntity(kind, data, id, {creationRequestId}={}) {
    if (!['property','search'].includes(kind)) throw new Error('Érvénytelen profiltípus.');
    if (creationRequestId != null && (id || typeof creationRequestId !== 'string' || !/^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i.test(creationRequestId) || /^0{8}-(?:0{4}-){3}0{12}$/.test(creationRequestId))) throw new Error('Érvénytelen létrehozási azonosító.');
    const route = kind === 'property' ? '/properties' : '/searches';
    // Keyed requests may replay a successful older receipt; the backend checks
    // that receipt before applying the current description policy to new data.
    if (!creationRequestId) assertDescriptionContactFree(data.description);
    const payload=kind === 'property' ? propertyToApi(data,!!id) : searchToApi(data);
    if (creationRequestId) {
      payload.creationRequestId=creationRequestId.toLowerCase();
      // An accepted old receipt must replay its original pre-alias heating labels.
      if(kind==='property')for(const field of ['heatingType','secondaryHeatingType'])if(typeof data[field]==='string')payload[field]=data[field].trim();
      if(kind==='search'&&Array.isArray(data.heatingTypes))payload.heatingTypes=data.heatingTypes.map(inputText);
      // Preserve the historical wire selection in frozen drafts. Persistence
      // normalizes the old tenth/eleventh choices into today's ninth-plus band.
      if (kind === 'search' && Array.isArray(data.floors) && inputText(data.type) !== 'Ház')
        payload.floors=[...new Set(data.floors.map(Number))];
      // An old frozen draft must retry its original request hash. The server
      // ignores this retired field for persistence and matching.
      const legacyGarden=data.sharedGarden, legacyGardenText=String(legacyGarden).trim().toLowerCase();
      if (Object.hasOwn(data,'sharedGarden') && ([true,false,1,0].includes(legacyGarden) || ['true','false'].includes(legacyGardenText)))
        payload.sharedGarden=(inputText(data.type)||'Lakás')==='Lakás' ? legacyGarden===true || legacyGarden===1 || legacyGardenText==='true' : kind==='property' ? null : false;
    }
    const result = await this.call(`${route}${id ? `/${encodeURIComponent(id)}` : ''}`, id ? 'PUT' : 'POST', payload);
    return kind === 'property' ? propertyFromApi(result,true) : searchFromApi(result,true);
  }
  async deleteEntity(kind, id) { const result = await this.call(`/${kind === 'property' ? 'properties' : 'searches'}/${encodeURIComponent(id)}`, 'DELETE'); this.active = null; return result; }
  async reportAccount(entityKind,entityId,reason) {
    if(!['property','search'].includes(entityKind)||typeof entityId!=='string'||!entityId.trim())throw new Error('Érvénytelen jelentési profil.');
    return this.call('/reports','POST',{entityKind,entityId,reason:normalizeReportReason(reason)});
  }
  async updateProfile(data) { return this.call('/me', 'PUT', { name: data.name, email: data.email, phone: requiredPhone(data.phone) }); }
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
  async matches({signal}={}) { return rows(await this.call('/matches','GET',undefined,{signal})).map(value=>matchFromApi(value,this.userId)); }
  async sendMessage(matchId, text) { return messageFromApi(await this.call(`/matches/${encodeURIComponent(matchId)}/messages`, 'POST', { text: String(text).trim() })); }
  async markRead() { return true; }
  async reset() { throw new Error('A valódi API-adatok a demó visszaállításával nem törölhetők. A demóhoz bontsd az API-kapcsolatot.'); }
}

/** Anonymous editors use the same bounded catalogue endpoints as authenticated editors. */
export async function findPublicLocations(query,limit=12,{kind='search'}={}) {
  if (!hostedMode()) return demoModel.findLocations(query,limit,{kind});
  return new ApiModel({baseUrl:hostedApiBase(),token:null}).findLocations(query,limit,{kind});
}
export async function findPublicStreets(query,locationId,limit=12) {
  if (!hostedMode()) return demoModel.findStreets(query,locationId,limit);
  return new ApiModel({baseUrl:hostedApiBase(),token:null}).findStreets(query,locationId,limit);
}

const regionById = id => regions.find(region=>region.id===id)||null;
const nullableNumber = value => value==null||value===''?null:(Number.isFinite(Number(value))?Number(value):null);

const publicListingHref=(kind,key)=>originFromListing(kind,key)?`#listing/${kind}/${key}`:null;
const publicImage=value=>{if(typeof value!=='string'||value.length>2000)return null;try{const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password?url.href:null;}catch{return null;}};
/** Whitelist full anonymous detail fields; never spread transport data into public state. */
export function publicListingFromApi(kind,key,value,{pricesInHuf=true}={}) {
  if(!originFromListing(kind,key)||value?.kind!==kind||value?.sourceKey!==key)throw new Error('A hirdetés nem érhető el.');
  const source=value.listing&&typeof value.listing==='object'?value.listing:{};
  const prefill=sanitizeTeaserPrefill(kind,value.prefill,{pricesInHuf});
  const price=v=>pricesInHuf?millions(nullableNumber(v)):nullableNumber(v);
  const common={title:containsContactDetails(value.title||source.title)?(kind==='property'?'Eladó ingatlan':'Ingatlant keresnek'):publicTitle(value.title||source.title,kind==='property'?'Eladó ingatlan':'Ingatlant keresnek'),type:inputText(source.type),description:typeof source.description==='string'&&!containsContactDetails(source.description)?source.description.slice(0,6000):'',ownerFirstName:publicFirstName(value.ownerFirstName),ownerAccountType:normalizeAccountType(value.ownerAccountType)};
  let listing;
  if(kind==='property'){
    const p=normalizePropertyAttributes({...source});
    const hideStreet=p.hideStreet,hideHouseNumber=p.hideHouseNumber;
    const street=hideStreet?'':inputText(source.street),houseNumber=hideHouseNumber?'':inputText(source.houseNumber);
    listing={...common,location:inputText(source.location),city:inputText(source.city),district:inputText(source.district),neighborhood:inputText(source.neighborhood),
      price:price(source.price),area:nullableNumber(source.area),rooms:nullableNumber(source.rooms),wholeRooms:nullableNumber(source.wholeRooms),halfRooms:nullableNumber(source.halfRooms),lotArea:nullableNumber(source.lotArea),
      floor:p.floor,floorIsUpperRange:p.floorIsUpperRange,buildingFloors:p.buildingFloors,isAttic:p.isAttic,condition:p.condition,building:p.building,constructionAge:p.constructionAge,view:p.view,ceilingHeight:p.ceilingHeight,
      heatingType:p.heatingType,insulated:p.insulated,energyRating:p.energyRating,energyRatingScheme:p.energyRatingScheme,airConditioning:p.airConditioning,solarPanels:p.solarPanels,parkingTypes:[...p.parkingTypes],parkingType:p.parkingType,
      balcony:p.balcony,elevator:source.elevator===true,privateGarden:p.privateGarden,hideStreet,hideHouseNumber,street,houseNumber,address:street?[street,houseNumber].filter(Boolean).join(' '):'',
      images:(Array.isArray(source.images)?source.images:[]).slice(0,12).map(value=>!pricesInHuf&&typeof value==='string'&&/^\/assets\/[a-z0-9._/-]+$/i.test(value)?value:publicImage(value)).filter(Boolean)};
  }else{
    const s=normalizeSearchAttributes(source);
    const locations=Array.isArray(source.locations)?source.locations.slice(0,MAX_SEARCH_LOCATIONS):[];
    listing={...common,locations:locations.map(item=>typeof item==='string'?item:inputText(item?.label)).filter(Boolean),minPrice:price(source.minPrice),maxPrice:price(source.publicMaxPrice??source.maxPrice),minArea:nullableNumber(source.minArea),maxArea:nullableNumber(source.maxArea),minRooms:nullableNumber(source.minRooms),maxRooms:nullableNumber(source.maxRooms),
      conditions:s.conditions,buildings:s.buildings,constructionAges:s.constructionAges,views:s.views,ceilingHeight:s.ceilingHeight,floors:s.floors,heatingTypes:s.heatingTypes,atticPreference:s.atticPreference,minEnergyRating:s.minEnergyRating,
      excludeTopFloor:s.excludeTopFloor,excludeGroundFloorAndBelow:s.excludeGroundFloorAndBelow,airConditioning:s.airConditioning,privateGarden:s.privateGarden,balcony:source.balcony===true,elevator:source.elevator===true,moveIn:inputText(source.moveIn),financing:inputText(source.financing)};
  }
  const result={kind,key,sourceKey:key,title:common.title,ownerFirstName:common.ownerFirstName,ownerAccountType:common.ownerAccountType,listing,prefill,href:publicListingHref(kind,key)};
  if(kind==='search'){
    const cloneSource={...sanitizeTeaserPrefill('search',value.clonePrefill||value.prefill,{pricesInHuf}),...Object.fromEntries(['description','moveIn','financing'].map(field=>[field,typeof value.clonePrefill?.[field]==='string'&&!containsContactDetails(value.clonePrefill[field])?value.clonePrefill[field]:'']))};
    result.clonePrefill=prefillFromSearchClone(cloneSource);
  }
  return result;
}
export async function fetchPublicListing(kind,key,{signal}={}) {
  if(!originFromListing(kind,key))throw new Error('A hirdetés nem érhető el.');
  if(!hostedMode())return publicListingFromApi(kind,key,demoPublicListing(kind,key),{pricesInHuf:false});
  return publicListingFromApi(kind,key,await request(hostedApiBase(),null,`/public/listings/${kind}/${key}`,'GET',undefined,{signal}));
}

/** The authenticated endpoint computes eligibility and scores; public details cannot be rescored safely. */
export function listingContextFromApi(kind,value={}) {
  const raw=value.active,active=raw&&['property','search'].includes(raw.kind)&&typeof raw.id==='string'&&raw.id?{
    kind:raw.kind,id:raw.id,title:inputText(raw.title),type:inputText(raw.type),
    locations:(Array.isArray(raw.locations)?raw.locations:[]).map(location=>typeof location==='string'?location:inputText(location?.label)).filter(Boolean),
    locationIds:(Array.isArray(raw.locationIds)?raw.locationIds:[]).filter(id=>typeof id==='string'&&getLocation(id)),
    price:millions(nullableNumber(raw.price)),minPrice:millions(nullableNumber(raw.minPrice)),maxPrice:millions(nullableNumber(raw.maxPrice)),
    minArea:nullableNumber(raw.minArea),maxArea:nullableNumber(raw.maxArea),minRooms:nullableNumber(raw.minRooms),maxRooms:nullableNumber(raw.maxRooms)
  }:null;
  const item=active&&active.kind!==kind&&value.item?candidateFromApi(value.item,active.kind):null;
  const hasPair=!!(item?.pair.propertyId&&item?.pair.searchId),myDecision=['liked','passed'].includes(value.myDecision)?value.myDecision:null;
  const score=nullableNumber(value.compatibilityScore??item?.score),hasUnseenExact=value.hasUnseenExact===true;
  const reasons=new Set(['no_active_profile','opposite_profile_required','own_listing','agent_pair_forbidden','incompatible','exact_matches_remaining','already_liked','already_passed','already_matched']);
  return {active,item,available:value.available!==false,myDecision,matchId:typeof value.matchId==='string'?value.matchId:null,
    compatible:value.compatible===true,isExact:value.isExact===true,compatibilityScore:score==null?null:Math.max(0,Math.min(100,Math.round(score))),
    likeCost:Math.max(0,nullableNumber(value.likeCost)??0),credits:Math.max(0,nullableNumber(value.credits)??0),
    canDecide:value.available!==false&&value.canDecide===true&&value.compatible===true&&!!active&&active.kind!==kind&&hasPair&&!myDecision&&!hasUnseenExact,
    requiresApproximateConsent:value.requiresApproximateConsent===true,hasUnseenExact,unavailableReason:reasons.has(value.unavailableReason)?value.unavailableReason:null};
}
export async function getListingContext(kind,key,options={}) {
  if(!originFromListing(kind,key))throw new Error('A hirdetés nem érhető el.');
  const model=getModel();
  return typeof model?.getListingContext==='function'?model.getListingContext(kind,key,options):null;
}
export function listingProfilesFromApi(kind,value={},page={offset:0,limit:50}) {
  const expected=kind==='property'?'search':'property',items=[];
  for(const row of rows(value).slice(0,50)){
    const raw=row?.profile;
    if(!raw||raw.kind!==expected||typeof raw.id!=='string'||!raw.id)continue;
    const profile=listingContextFromApi(kind,{active:raw}).active;if(!profile)continue;
    const score=nullableNumber(row.score);
    items.push({profile,score:row.compatible===true&&score!=null?Math.max(0,Math.min(100,Math.round(score))):0,isExact:row.compatible===true&&row.isExact===true,compatible:row.compatible===true,isActive:row.isActive===true});
  }
  const offset=Number.isSafeInteger(value.offset)&&value.offset>=0?value.offset:page.offset,limit=Number.isSafeInteger(value.limit)&&value.limit>0&&value.limit<=50?value.limit:page.limit;
  const total=Number.isSafeInteger(value.total)&&value.total>=0?value.total:offset+items.length;
  return {kind:expected,items,total,offset,limit,hasMore:value.hasMore===true&&items.length>0&&offset+items.length<total,unavailableReason:['own_listing','agent_pair_forbidden'].includes(value.unavailableReason)?value.unavailableReason:null};
}
export async function getListingProfiles(kind,key,options={}) {
  if(!originFromListing(kind,key))throw new Error('A hirdetés nem érhető el.');
  const model=getModel();
  if(typeof model?.getListingProfiles!=='function')throw new Error('A profilválasztó most nem érhető el.');
  return model.getListingProfiles(kind,key,options);
}
function listingMapFromApi(kind,value) {
  const locationIds=[...new Set((Array.isArray(value?.locationIds)?value.locationIds:[]).filter(id=>typeof id==='string'&&getLocation(id)&&!isStreetId(id)))];
  let externalUrl=null;
  if(typeof value?.externalUrl==='string')try{
    const url=new URL(value.externalUrl);
    if(url.protocol==='https:'&&['google.com','www.google.com','maps.google.com'].includes(url.hostname)&&!url.username&&!url.password&&url.pathname.startsWith('/maps'))externalUrl=url.href;
  }catch{/* An invalid external URL never becomes a navigation target. */}
  return {kind,available:value?.available===true&&!!(externalUrl||locationIds.length),locationIds,externalUrl};
}
export async function getListingMap(kind,key,{signal}={}) {
  if(!originFromListing(kind,key))throw new Error('A hirdetés nem érhető el.');
  const value=hostedMode()?await request(hostedApiBase(),null,`/public/listings/${kind}/${key}/map`,'GET',undefined,{signal})
    :typeof demoModel.getListingMap==='function'?await demoModel.getListingMap(kind,key,{signal}):null;
  requireCurrentRead(signal);
  return listingMapFromApi(kind,value);
}

function landingFromApi(value) {
  const region=regionById(value?.region?.id);
  const publicType=value=>['Lakás','Ház','Telek','Nyaraló','Garázs','Iroda','Üzlethelyiség','Egyéb'].includes(value)?value:'Ingatlan';
  return {
    regions:regions.map(region=>({...region})),region:clone(region),scope:region?'region':'national',
    searches:rows(value?.searches).slice(0,16).map((item,index)=>({key:String(item.key??`search-${index+1}`),sourceKey:originFromListing('search',item.sourceKey)?.key??null,href:publicListingHref('search',item.sourceKey),title:publicTitle(item.title,'Ingatlant keresnek'),type:publicType(item.type),locations:(Array.isArray(item.locations)?item.locations:[]).filter(location=>typeof location==='string').slice(0,MAX_SEARCH_LOCATIONS),minPrice:millions(nullableNumber(item.minPrice)),maxPrice:millions(nullableNumber(item.publicMaxPrice??item.maxPrice)),minArea:nullableNumber(item.minArea),maxArea:nullableNumber(item.maxArea),minRooms:nullableNumber(item.minRooms),maxRooms:nullableNumber(item.maxRooms),ownerAccountType:normalizeAccountType(item.ownerAccountType),ownerFirstName:publicFirstName(item.ownerFirstName),prefill:sanitizeTeaserPrefill('search',item.prefill,{pricesInHuf:true})})),
    properties:rows(value?.properties).slice(0,8).map((item,index)=>({key:String(item.key??`property-${index+1}`),sourceKey:originFromListing('property',item.sourceKey)?.key??null,href:publicListingHref('property',item.sourceKey),image:publicImage(item.image),title:publicTitle(item.title,'Eladó ingatlan'),type:publicType(item.type),location:String(item.location||''),price:millions(nullableNumber(item.price)),area:nullableNumber(item.area),wholeRooms:nullableNumber(item.wholeRooms),halfRooms:nullableNumber(item.halfRooms),rooms:nullableNumber(item.rooms),lotArea:nullableNumber(item.lotArea),ownerAccountType:normalizeAccountType(item.ownerAccountType),ownerFirstName:publicFirstName(item.ownerFirstName),prefill:sanitizeTeaserPrefill('property',item.prefill,{pricesInHuf:true})}))
  };
}
export async function fetchLanding({region,signal}={}) {
  const selected=region==null||region===''?null:regionById(region);
  if(region!=null&&region!==''&&!selected)throw new Error('Válassz egy érvényes régiót.');
  if(!hostedMode())return {regions:regions.map(region=>({...region})),...demoLanding(selected)};
  const query=selected?'?'+new URLSearchParams({region:selected.id}):'';
  return landingFromApi(await request(hostedApiBase(),null,'/public/landing'+query,'GET',undefined,{signal}));
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
  const registration=registerData?{...registerData,accountType:normalizeAccountType(registerData.accountType,{strict:true}),phone:requiredPhone(registerData.phone)}:{};
  const attempt=beginAuthAttempt();
  const result = await request(base, null, registerData ? '/auth/register' : '/auth/login', 'POST', { ...registration, email: String(email).trim(), password: String(password) });
  requireCurrentAuthAttempt(attempt);
  const token = result?.token || result?.accessToken;
  if (!token) throw new Error('Az API nem küldött hitelesítési tokent.');
  const config = { baseUrl: base, token };
  const adapter = new ApiModel(config);
  await adapter.getState();
  requireCurrentAuthAttempt(attempt);
  try { attempt.storage.setItem(API_CONFIG_KEY, JSON.stringify(config)); } catch { throw new Error('A kapcsolat nem menthető a böngésző helyi tárhelyére.'); }
  return adapter;
}
export function disconnectApi() { const attempt=beginAuthAttempt();try { attempt.storage.removeItem(API_CONFIG_KEY); } catch { throw new Error('A mentett API-kapcsolat nem törölhető.'); } return hostedMode() ? null : demoModel; }
export function getApiConnection() { const config = readConfig(); return config ? { baseUrl: config.baseUrl } : null; }
