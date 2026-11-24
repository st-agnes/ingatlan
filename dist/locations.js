import { settlements } from './locations-data.js';
import { agglomerations } from './agglomerations-data.js';
import { neighborhoods } from './neighborhoods-data.js';

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

const quarters = neighborhoods.map(neighborhood => {
  if (!neighborhood || typeof neighborhood.id !== 'string' || !neighborhood.id.startsWith('neighborhood:')
      || typeof neighborhood.name !== 'string' || !neighborhood.name.trim() || !settlementNames.has(neighborhood.city)) {
    throw new Error('A városrészek katalógusa érvénytelen.');
  }
  return Object.freeze({...neighborhood, label: `${neighborhood.name} (${neighborhood.city})`, district: null,
    kind: 'neighborhood', settlementCount: null, aliases: Object.freeze([...(neighborhood.aliases || [])])});
});

export const locations = Object.freeze([...cities, ...districts, ...areas, ...quarters]);
const byId = new Map(locations.map(location => [location.id, location]));
const streetLocations = new Map();
if (byId.size !== locations.length) throw new Error('A helyszínazonosítók nem egyediek.');
const byCity = new Map(cities.map(location => [normalize(location.city), location]));
const byLabel = new Map(locations.map(location => [normalize(location.label), location]));
const indexed = locations.map((location, index) => ({ location, index,
  label: normalize(location.kind === 'area' ? `${location.city} és környéke` : location.label),
  terms: location.kind === 'neighborhood'
    ? [location.name, ...(location.aliases || [])].map(alias => normalize(`${alias} ${location.city}`).replace(/[().]/g, '')) : null }));

export function getLocation(id) {
  return typeof id === 'string' ? byId.get(id) ?? null : null;
}

export const isStreetId = id => typeof id === 'string' && /^street:[a-f0-9]{24}$/.test(id);

/** Register bounded metadata returned by the public catalogue API, never arbitrary typed text. */
export function registerLocations(values) {
  if (!Array.isArray(values)) return [];
  const result = [];
  for (const value of values) {
    if (!value || typeof value !== 'object') continue;
    const known = byId.get(value.id);
    if (known && known.kind !== 'street') { result.push(known); continue; }
    if (!isStreetId(value.id) || value.kind !== 'street' || !settlementNames.has(value.city)
        || typeof value.streetName !== 'string' || !value.streetName.trim() || value.streetName.length > 180
        || typeof value.label !== 'string' || !value.label.trim() || value.label.length > 400
        || /\p{Cc}/u.test(value.streetName + value.label)
        || !Array.isArray(value.postalCodes) || !value.postalCodes.length
        || value.postalCodes.some(code => typeof code !== 'string' || !/^\d{4}$/.test(code))) continue;
    const district = value.district == null || value.district === '' ? null : value.district;
    if (district !== null && (value.city !== 'Budapest' || !roman.some(number => number + '.' === district))) continue;
    const location = Object.freeze({id:value.id, label:value.label.trim(), city:value.city, district,
      kind:'street', streetName:value.streetName.trim(), postalCodes:Object.freeze([...new Set(value.postalCodes)].sort()), settlementCount:null});
    // A stable catalogue ID must never change meaning within an open workspace.
    if (known && JSON.stringify(known) !== JSON.stringify(location)) continue;
    if (!known) { byId.set(location.id, location); streetLocations.set(location.id, location); }
    result.push(known || location);
  }
  return result;
}

export function streetBelongsToLocation(street, location) {
  return street?.kind === 'street' && isPropertyLocation(location) && street.city === location.city
    && (!street.district || !location.district || street.district === location.district);
}

/** Resolve only an unambiguous exact catalogue name, optionally narrowed by postcode. */
export function resolveStreetLocation(streetName, location, postalCode = '', values = [...streetLocations.values()]) {
  const name = normalize(streetName), code = String(postalCode || '').trim();
  const matches = values.filter(street => streetBelongsToLocation(street, location)
    && (!location.district || street.district === location.district)
    && normalize(street.streetName) === name && (!code || street.postalCodes.includes(code)));
  return matches.length === 1 ? matches[0] : null;
}

/** Address suggestions are scoped to one town or Budapest district. */
export function searchStreets(query, locationId, limit = 8, values = [...streetLocations.values()]) {
  const location = getLocation(locationId), text = normalize(query).slice(0, 120);
  const count = Number.isFinite(Number(limit)) ? Math.max(0, Math.min(50, Math.trunc(Number(limit)))) : 8;
  if (!isPropertyLocation(location) || !text || !count) return [];
  const words = text.split(' ');
  return values.filter(street => streetBelongsToLocation(street, location) && (!location.district || street.district === location.district))
    .map(street => ({street, name:normalize(street.streetName)}))
    .filter(item => words.every(word => item.name.split(' ').some(part => part.startsWith(word))))
    .sort((left,right) => Number(right.name === text) - Number(left.name === text)
      || Number(right.name.startsWith(text)) - Number(left.name.startsWith(text))
      || left.street.label.localeCompare(right.street.label, 'hu') || left.street.id.localeCompare(right.street.id))
    .slice(0,count).map(item => item.street);
}

/** Listings always identify one real town or Budapest district. */
export function isPropertyLocation(location) {
  return !!location && ['city', 'district'].includes(location.kind);
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
export function searchLocations(query, limit = 8, {kind = 'search', streets = [...streetLocations.values()]} = {}) {
  if (!['search', 'property'].includes(kind)) throw new Error('Érvénytelen helyszínválasztó-típus.');
  const text = normalize(query).slice(0, 120);
  const count = Number.isFinite(Number(limit)) ? Math.max(0, Math.min(50, Math.trunc(Number(limit)))) : 8;
  if (!text || !count) return [];
  const number = districtQuery(text);
  const compact = text.replace(/[().]/g, '');
  const words = compact.split(' ');
  const results = [];
  const candidates = kind === 'property' ? indexed : [...indexed, ...streets.map((location,index) => ({location,index:indexed.length+index,
    label:normalize(location.label),terms:[normalize(`${location.streetName} ${location.city} ${location.district || ''}`)]}))];
  for (const item of candidates) {
    if (kind === 'property' && !isPropertyLocation(item.location)) continue;
    const label = item.label.replace(/[().]/g, '');
    const terms = item.terms || [label];
    let score = null;
    if (number && item.location.id === 'district:Budapest:' + number) score = -1;
    else if (item.location.kind === 'area' && normalize(item.location.label) === text) score = 0;
    else if (label === compact) score = 0;
    // Keep a city's broad search option visible before its many districts.
    else if (item.location.kind === 'area' && normalize(item.location.city).startsWith(compact)) score = .5;
    else if (label.startsWith(compact)) score = 1;
    else if (terms.some(term => words.every(word => term.split(' ').some(part => part.startsWith(word))))) score = 2;
    else if (terms.some(term => term.includes(compact))) score = 3;
    else if (item.location.kind === 'area'
        && words.every(word => normalize(`${item.location.city} agglomeráció térsége környéke`).split(' ').some(part => part.startsWith(word)))) score = 2;
    if (score !== null) results.push({ ...item, score });
  }
  // Correct a single mistyped letter only when there are no direct suggestions.
  if (!results.length && text.length >= 4 && !/budapest|kerulet|\d/.test(text)) {
    for (const item of indexed) {
      if (kind === 'property' && !isPropertyLocation(item.location)) continue;
      const term = item.location.kind === 'area' ? normalize(item.location.city)
        : item.location.kind === 'neighborhood' ? normalize(item.location.name) : item.label;
      if (!item.location.district && editDistanceAtMostOne(text, term)) results.push({ ...item, score: item.location.kind === 'area' ? 4.5 : 4 });
    }
  }
  return results.sort((a, b) => a.score - b.score || a.index - b.index).slice(0, count).map(item => item.location);
}

/** Interpret old city/district fields without inventing a municipality. */
export function resolveLegacyLocations(value = {}) {
  const cityText = normalize(value.city);
  const exact = byLabel.get(cityText);
  if (exact?.kind === 'district') return [exact];
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
    if (!Array.isArray(search.locationIds) || !search.locationIds.length || search.locationIds.length > 50) return [];
    const selected = search.locationIds.map(getLocation);
    return selected.some(location => !location) ? [] : selected;
  }
  return resolveLegacyLocations(search);
}

/** Canonical places and verified street/neighborhood membership are alternatives. */
export function matchesLocations(property = {}, search = {}) {
  const home = propertyLocation(property);
  if (!home) return false;
  return searchLocationList(search).some(location => location.kind === 'street'
    ? property.hideStreet === false && streetBelongsToLocation(location, home) && (property.streetId ?? property.addressDetails?.streetId) === location.id
    : location.kind === 'neighborhood'
    ? Array.isArray(property.neighborhoodIds) && property.neighborhoodIds.includes(location.id)
    : location.kind === 'area' ? areaMembers.get(location.id)?.has(home.city) === true
    : location.city === home.city && (!location.district || location.district === home.district));
}
