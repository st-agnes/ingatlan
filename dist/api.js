import { model as demoModel } from './model.js';
import { getLocation, resolveLegacyLocations } from './locations.js';

export const API_CONFIG_KEY = 'otthonra.api';
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
    if (!response.ok) throw new Error(errorMessage(payload, response.status));
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
  const locations = uniqueIds == null ? resolveLegacyLocations(kind === 'search' ? {...value, districts:inputStrings(value.districts)} : value) : uniqueIds.map(getLocation).filter(Boolean);
  if (strict && (!locations.length || (uniqueIds != null && locations.length !== uniqueIds.length))) throw new Error('Válassz érvényes települést vagy budapesti kerületet a találati listából.');
  return locations;
}

function propertyFromApi(value) {
  if (!value) return null;
  const location = entityLocations(value, 'property')[0] || null;
  return {
    id: String(value.id), ownerId: String(value.ownerId ?? value.userId ?? ''),
    title: value.title || '', locationId:location?.id || '', location:clone(location), city: location?.city ?? value.city ?? '', district: location ? location.district || '' : value.district ?? '', neighborhood: value.neighborhood || '', address: value.address || '', description: value.description || '', createdAt: value.createdAt,
    type: value.type || value.propertyType || 'Lakás',
    price: millions(value.priceHuf ?? value.price), area: numeric(value.area ?? value.areaSqm ?? value.sizeSqm), rooms: numeric(value.rooms ?? value.roomCount),
    lotArea: numeric(value.lotArea ?? value.lotAreaSqm ?? null), floor: numeric(value.floor), condition: value.condition || '', building: value.building || value.buildingMaterial || '',
    balcony: !!(value.balcony ?? value.hasBalcony), elevator: !!(value.elevator ?? value.hasElevator),
    images: clone(value.images || value.imageUrls || []), archived: !!(value.archived ?? value.isArchived)
  };
}
function searchFromApi(value) {
  if (!value) return null;
  const locations = entityLocations(value, 'search');
  return {
    id: String(value.id), ownerId: String(value.ownerId ?? value.userId ?? ''),
    title: value.title || '', locationIds:locations.map(location=>location.id), locations:clone(locations), city: locations[0]?.city ?? value.city ?? '', districts: locations.filter(location=>location.city===locations[0]?.city&&location.district).map(location=>location.district), description: value.description || '', moveIn: value.moveIn || '', buyerName: value.buyerName || '', financing: value.financing || '', avatar: value.avatar || '', createdAt: value.createdAt,
    type: value.type || value.propertyType || 'Lakás',
    minPrice: millions(value.minPriceHuf ?? value.minPrice ?? null), maxPrice: millions(value.maxPriceHuf ?? value.maxPrice ?? null),
    minArea: numeric(value.minArea ?? value.minAreaSqm ?? null), maxArea: numeric(value.maxArea ?? value.maxAreaSqm ?? null),
    minRooms: numeric(value.minRooms ?? null), maxRooms: numeric(value.maxRooms ?? null),
    balcony: !!(value.balcony ?? value.requiresBalcony), elevator: !!(value.elevator ?? value.requiresElevator),
    archived: !!(value.archived ?? value.isArchived)
  };
}
function inputNumber(value, name, nullable = false) {
  if (value === '' || value == null) {
    if (nullable) return null;
    throw new Error(`A(z) ${name} megadása kötelező.`);
  }
  const result = Number(value);
  if (!Number.isFinite(result)) throw new Error(`A(z) ${name} érvényes szám legyen.`);
  return result;
}
const inputBoolean = value => value === true || value === 1 || ['true', '1', 'on'].includes(String(value).toLowerCase());
const inputText = value => value == null ? '' : String(value).trim();
const inputStrings = value => Array.isArray(value) ? value.map(inputText).filter(Boolean) : inputText(value).split(/[,\n]/).map(inputText).filter(Boolean);
function propertyToApi(value) {
  const floor = inputNumber(value.floor, 'emelet', true);
  if (floor != null && !Number.isInteger(floor)) throw new Error('Az emelet egész szám legyen.');
  const images = Array.isArray(value.images) ? value.images.map(inputText).filter(Boolean) : inputText(value.images).split('\n').map(inputText).filter(Boolean);
  if (images.length > 12 || images.some(image => { try { return new URL(image).protocol !== 'https:' || image.length > 2000; } catch { return true; } })) throw new Error('Az API-hoz legfeljebb 12 HTTPS-képhivatkozás adható meg.');
  const price = inputNumber(value.price, 'ár'), area = inputNumber(value.area, 'alapterület'), rooms = inputNumber(value.rooms, 'szobaszám');
  const location = entityLocations(value, 'property', true)[0];
  const type = inputText(value.type) || 'Lakás';
  const lotArea = type === 'Ház' ? inputNumber(value.lotArea, 'telekméret', true) : null;
  if (lotArea != null && lotArea <= 0) throw new Error('A telekméret pozitív szám legyen.');
  return {
    title: inputText(value.title), locationId:location.id, city:location.city, district:location.district || '', neighborhood: inputText(value.neighborhood), address: inputText(value.address), description: inputText(value.description),
    type, price: Math.round(price * MILLION), area, rooms, lotArea, floor,
    condition: inputText(value.condition), building: inputText(value.building), balcony: inputBoolean(value.balcony), elevator: inputBoolean(value.elevator), images, archived: inputBoolean(value.archived)
  };
}
function searchToApi(value) {
  const minPrice = inputNumber(value.minPrice, 'minimumár', true), maxPrice = inputNumber(value.maxPrice, 'maximumár', true);
  const locations = entityLocations(value, 'search', true);
  return {
    title: inputText(value.title), locationIds:locations.map(location=>location.id), city:locations[0].city, districts:locations.filter(location=>location.city===locations[0].city&&location.district).map(location=>location.district), description: inputText(value.description), type: inputText(value.type) || 'Lakás',
    minPrice: minPrice == null ? null : Math.round(minPrice * MILLION), maxPrice: maxPrice == null ? null : Math.round(maxPrice * MILLION),
    minArea: inputNumber(value.minArea, 'minimum alapterület', true), maxArea: inputNumber(value.maxArea, 'maximum alapterület', true), minRooms: inputNumber(value.minRooms, 'minimum szobaszám', true), maxRooms: inputNumber(value.maxRooms, 'maximum szobaszám', true),
    balcony: inputBoolean(value.balcony), elevator: inputBoolean(value.elevator), moveIn: inputText(value.moveIn), financing: inputText(value.financing), archived: inputBoolean(value.archived)
  };
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
    partner: { ...clone(partner), id: String(partner.id ?? partner.userId ?? ''), name: partner.name || partner.displayName || '', avatar: partner.avatar || initials(partner.name || partner.displayName), email: partner.email || '', phone: partner.phone || partner.phoneNumber || '' },
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
      user: { id: String(user.id), name: user.name || user.displayName || '', email: user.email || '', phone: user.phone || user.phoneNumber || '', avatar: user.avatar || initials(user.name || user.displayName) },
      credits: Number(profile.credits ?? profile.creditBalance ?? profile.balance ?? user.credits ?? 0), active,
      properties: rows(entities.properties).map(propertyFromApi), searches: rows(entities.searches || entities.searchRequests).map(searchFromApi),
      decisions: rows(entities.decisions || profile.decisions).map(d=>({...clone(d),id:String(d.id),actorId:String(d.actorId),propertyId:String(d.propertyId),searchId:String(d.searchId??d.searchRequestId),property:propertyFromApi(d.property),search:searchFromApi(d.search??d.searchRequest)})),
      ledger: rows(ledgerResponse.ledger || ledgerResponse).map(entry => ({ ...clone(entry), amount: Number(entry.amount ?? entry.delta ?? 0), description: entry.description || entry.reason || '', createdAt: entry.createdAt })),
      createdAt: user.createdAt
    };
  }
  async feed() {
    if (!this.active) await this.getState();
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
  async decide(item, liked) {
    const result = await this.call('/decisions', 'POST', { propertyId: item.pair.propertyId, searchRequestId: item.pair.searchId, liked: inputBoolean(liked) });
    let match = result.match ? matchFromApi(result.match) : null;
    if (!match && result.matchId) match = (await this.matches()).find(m => m.id === String(result.matchId)) || null;
    return { match, charged: Number(result.charged ?? result.creditsSpent ?? result.creditCost ?? 0) };
  }
  async activate(kind, id) { const result = await this.call('/me/active', 'PUT', { kind, id }); this.active = { kind, id }; return result; }
  async saveEntity(kind, data, id) {
    const route = kind === 'property' ? '/properties' : '/searches';
    const result = await this.call(`${route}${id ? `/${encodeURIComponent(id)}` : ''}`, id ? 'PUT' : 'POST', kind === 'property' ? propertyToApi(data) : searchToApi(data));
    return kind === 'property' ? propertyFromApi(result) : searchFromApi(result);
  }
  async deleteEntity(kind, id) { const result = await this.call(`/${kind === 'property' ? 'properties' : 'searches'}/${encodeURIComponent(id)}`, 'DELETE'); this.active = null; return result; }
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

export function getModel() { const config = readConfig(); return config ? new ApiModel(config) : demoModel; }
export async function connectApi(baseUrl, email, password, registerData) {
  const base = apiBase(baseUrl);
  const result = await request(base, null, registerData ? '/auth/register' : '/auth/login', 'POST', { ...(registerData || {}), email: String(email).trim(), password: String(password) });
  const token = result?.token || result?.accessToken;
  if (!token) throw new Error('Az API nem küldött hitelesítési tokent.');
  const config = { baseUrl: base, token };
  const adapter = new ApiModel(config);
  await adapter.getState();
  try { globalThis.localStorage.setItem(API_CONFIG_KEY, JSON.stringify(config)); } catch { throw new Error('A kapcsolat nem menthető a böngésző helyi tárhelyére.'); }
  return adapter;
}
export function disconnectApi() { try { globalThis.localStorage?.removeItem(API_CONFIG_KEY); } catch { throw new Error('A mentett API-kapcsolat nem törölhető.'); } return demoModel; }
export function getApiConnection() { const config = readConfig(); return config ? { baseUrl: config.baseUrl } : null; }
