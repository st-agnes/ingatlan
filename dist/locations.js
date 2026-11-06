import { settlements } from './locations-data.js';
import { agglomerations } from './agglomerations-data.js';

// IDs are stable and shared by the browser, demo model, and .NET API.
const normalize = value => String(value ?? '').normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase('hu').trim().replace(/\s+/g, ' ');
const roman = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX','XXI','XXII','XXIII'];
const cities = settlements.map(city => Object.freeze({ id: 'city:' + city, label: city, city, district: null, kind: 'city', settlementCount: null }));
const districts = roman.map((number, index) => Object.freeze({ id: 'district:Budapest:' + (index + 1), label: 'Budapest ' + number + '. kerület', city: 'Budapest', district: number + '.', kind: 'district', settlementCount: null }));

const settlementNames = new Set(settlements);
const areaMembers = new Map();
const areas = agglomerations.map(area => {
  const members = area?.settlements;
  if (!area || typeof area.city !== 'string' || area.id !== 'area:' + area.city
      || !settlementNames.has(area.city) || areaMembers.has(area.id)
      || !Array.isArray(members) || members.length < 2 || new Set(members).size !== members.length
      || !members.includes(area.city) || members.some(name => !settlementNames.has(name))) {
    throw new Error('A városkörnyéki településcsoportok katalógusa érvénytelen.');
  }
  areaMembers.set(area.id, new Set(members));
  return Object.freeze({id: area.id, label: `${area.city} és környéke (${members.length} település)`,
    city: area.city, district: null, kind: 'area', settlementCount: members.length});
});

export const locations = Object.freeze([...cities, ...districts, ...areas]);
const byId = new Map(locations.map(location => [location.id, location]));
const byCity = new Map(cities.map(location => [normalize(location.city), location]));
const byLabel = new Map(locations.map(location => [normalize(location.label), location]));
const indexed = locations.map((location, index) => ({ location, index, label: normalize(location.kind === 'area' ? `${location.city} és környéke` : location.label) }));

export function getLocation(id) {
  return typeof id === 'string' ? byId.get(id) ?? null : null;
}

/** Listings always identify one real town or Budapest district. */
export function isPropertyLocation(location) {
  return !!location && location.kind !== 'area';
}

function districtNumber(value) {
  const token = normalize(value).replace(/^budapest\s*/, '').replace(/\s*ker(?:ulet)?\.?$/, '').replace(/[.\s]/g, '');
  if (/^\d{1,2}$/.test(token)) {
    const number = Number(token);
    return number >= 1 && number <= 23 ? number : null;
  }
  const index = roman.findIndex(number => number.toLowerCase() === token);
  return index < 0 ? null : index + 1;
}

function districtQuery(query) {
  const match = /^(?:(?:budapest|bp)\s*[,.-]?\s*(\d{1,2}|[ivx]+)\.?(?:\s*ker(?:ulet)?\.?)?|(\d{1,2}|[ivx]+)\.?\s*ker(?:ulet)?\.?)$/.exec(query);
  return match ? districtNumber(match[1] ?? match[2]) : null;
}

function editDistanceAtMostOne(left, right) {
  if (Math.abs(left.length - right.length) > 1) return false;
  let a = 0, b = 0, edits = 0;
  while (a < left.length && b < right.length) {
    if (left[a] === right[b]) { a++; b++; continue; }
    if (++edits > 1) return false;
    if (left.length <= right.length) b++;
    if (left.length >= right.length) a++;
  }
  return edits + (a < left.length || b < right.length ? 1 : 0) <= 1;
}

/** Suggest canonical choices; typed text alone never creates a location. */
export function searchLocations(query, limit = 8, {kind = 'search'} = {}) {
  if (!['search', 'property'].includes(kind)) throw new Error('Érvénytelen helyszínválasztó-típus.');
  const text = normalize(query).slice(0, 120);
  const count = Number.isFinite(Number(limit)) ? Math.max(0, Math.min(50, Math.trunc(Number(limit)))) : 8;
  if (!text || !count) return [];
  const number = districtQuery(text);
  const compact = text.replace(/\./g, '');
  const words = compact.split(' ');
  const results = [];
  for (const item of indexed) {
    if (kind === 'property' && !isPropertyLocation(item.location)) continue;
    const label = item.label.replace(/\./g, '');
    let score = null;
    if (number && item.location.id === 'district:Budapest:' + number) score = -1;
    else if (item.location.kind === 'area' && normalize(item.location.label) === text) score = 0;
    else if (label === compact) score = 0;
    // Keep a city's broad search option visible before its many districts.
    else if (item.location.kind === 'area' && normalize(item.location.city).startsWith(compact)) score = .5;
    else if (label.startsWith(compact)) score = 1;
    else if (words.every(word => label.split(' ').some(part => part.startsWith(word)))) score = 2;
    else if (label.includes(compact)) score = 3;
    else if (item.location.kind === 'area'
        && words.every(word => normalize(`${item.location.city} agglomeráció térsége környéke`).split(' ').some(part => part.startsWith(word)))) score = 2;
    if (score !== null) results.push({ ...item, score });
  }
  // Correct a single mistyped letter only when there are no direct suggestions.
  if (!results.length && text.length >= 4 && !/budapest|kerulet|\d/.test(text)) {
    for (const item of indexed) {
      if (kind === 'property' && !isPropertyLocation(item.location)) continue;
      const term = item.location.kind === 'area' ? normalize(item.location.city) : item.label;
      if (!item.location.district && editDistanceAtMostOne(text, term)) results.push({ ...item, score: item.location.kind === 'area' ? 4.5 : 4 });
    }
  }
  return results.sort((a, b) => a.score - b.score || a.index - b.index).slice(0, count).map(item => item.location);
}

/** Interpret old city/district fields without inventing a municipality. */
export function resolveLegacyLocations(value = {}) {
  const cityText = normalize(value.city);
  const exact = byLabel.get(cityText);
  if (exact?.district) return [exact];
  const city = byCity.get(cityText);
  if (!city) return [];
  if (city.city !== 'Budapest') return [city];
  const raw = value.districts ?? value.district;
  const selected = (Array.isArray(raw) ? raw : String(raw ?? '').split(',')).map(value => String(value).trim()).filter(Boolean);
  if (!selected.length) return [city];
  const numbers = selected.map(districtNumber);
  if (numbers.some(number => number === null)) return [];
  return [...new Set(numbers)].map(number => byId.get('district:Budapest:' + number));
}

function propertyLocation(property) {
  const id = property.locationId ?? property.location?.id;
  const location = id != null ? getLocation(id) : resolveLegacyLocations(property)[0] ?? null;
  return isPropertyLocation(location) ? location : null;
}

function searchLocationList(search) {
  if (search.locationIds != null) {
    if (!Array.isArray(search.locationIds) || !search.locationIds.length) return [];
    const selected = search.locationIds.map(getLocation);
    return selected.some(location => !location) ? [] : selected;
  }
  return resolveLegacyLocations(search);
}

/** Selected towns and districts are alternatives; all other filters remain separate. */
export function matchesLocations(property = {}, search = {}) {
  const home = propertyLocation(property);
  if (!home) return false;
  return searchLocationList(search).some(location => location.kind === 'area'
    ? areaMembers.get(location.id)?.has(home.city) === true
    : location.city === home.city && (!location.district || location.district === home.district));
}
