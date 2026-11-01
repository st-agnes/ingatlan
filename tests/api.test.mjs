import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { ApiModel, API_CONFIG_KEY, connectApi, getModel, disconnectApi } from '../dist/api.js';

const originalFetch = globalThis.fetch;
const originalStorage = globalThis.localStorage;
afterEach(() => { globalThis.fetch = originalFetch; globalThis.localStorage = originalStorage; });
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
