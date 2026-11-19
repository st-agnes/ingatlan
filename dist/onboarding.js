import {getLocation, isPropertyLocation, registerLocations} from './locations.js';
import {CONDITION_OPTIONS, BUILDING_OPTIONS, CONSTRUCTION_AGE_OPTIONS, VIEW_OPTIONS, HEATING_OPTIONS, CEILING_HEIGHT_OPTIONS, FLOOR_OPTIONS, normalizeCondition, normalizeBuilding} from './attributes.js';

export const DRAFT_STORAGE_KEY = 'otthonra.onboarding.v1';
export const DRAFT_TTL_MS = 7 * 86400000;
const VERSION = 1;
const MAX_BYTES = 100000;
const uuidPattern = /^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i;
const validUuid = value => typeof value === 'string' && uuidPattern.test(value) && !/^0{8}-(?:0{4}-){3}0{12}$/.test(value);
const kinds = ['property','search'];
const phases = ['editing','awaiting-auth','saving','saved'];
const publicSourceKeyPattern = /^(property|search)-[a-f0-9]{64}$/;
const clone = value => JSON.parse(JSON.stringify(value));
const text = (value, limit) => typeof value === 'string' ? value.slice(0,limit) : '';
const clock = value => { const result = typeof value === 'function' ? value() : value ?? Date.now(); const time = new Date(result).getTime(); if (!Number.isFinite(time)) throw new Error('Érvénytelen időpont.'); return time; };
const email = value => text(value,254).trim().toLowerCase();
function newUuid() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(bytes);
  else for (let index=0; index<bytes.length; index++) bytes[index]=Math.floor(Math.random()*256);
  bytes[6]=(bytes[6]&15)|64; bytes[8]=(bytes[8]&63)|128;
  const hex=[...bytes].map(byte=>byte.toString(16).padStart(2,'0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
function freeze(value) { if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); } return value; }
function safeLocations(values) {
  if (!Array.isArray(values)) return [];
  return [...new Map(registerLocations(values.slice(0,50)).map(location=>[location.id,location])).values()].map(location=>{
    const result={id:location.id,label:location.label,city:location.city,district:location.district??null,kind:location.kind,settlementCount:location.settlementCount??null};
    if (location.kind === 'street') Object.assign(result,{streetName:location.streetName,postalCodes:[...location.postalCodes]});
    return result;
  });
}
function canonicalLocationIds(values) {
  if (!Array.isArray(values) || !values.length || values.length>50) return null;
  registerLocations(values.filter(value=>value && typeof value==='object'));
  const ids=Array.from(values,value=>typeof value==='string'?value:value?.id);
  if (ids.some(id=>!getLocation(id))) return null;
  return [...new Set(ids)].sort();
}
/** Draft origins contain only a public opaque listing key or canonical catalogue choices. */
export function normalizeDraftOrigin(value,entityKind) {
  if (!value || typeof value!=='object' || Array.isArray(value) || entityKind!=null && !kinds.includes(entityKind)) return null;
  if (kinds.includes(value.kind)) {
    if (typeof value.key!=='string' || !publicSourceKeyPattern.test(value.key) || !value.key.startsWith(value.kind+'-') || value.kind===entityKind) return null;
    return {kind:value.kind,key:value.key};
  }
  if (value.kind==='locations') {
    if (entityKind!=null && entityKind!=='search') return null;
    const ids=canonicalLocationIds(value.locationIds);
    return ids?{kind:'locations',locationIds:ids}:null;
  }
  if (value.kind==='blank' && kinds.includes(value.entityKind) && (entityKind==null || value.entityKind===entityKind)) return {kind:'blank',entityKind:value.entityKind};
  return null;
}
export const originFromListing = (sourceKind,sourceKey) => normalizeDraftOrigin({kind:sourceKind,key:sourceKey});
export const originFromLocations = values => normalizeDraftOrigin({kind:'locations',locationIds:values});
export const originBlank = entityKind => normalizeDraftOrigin({kind:'blank',entityKind});
/** Location starts match the edited current choices; listing starts match their original identity. */
export function sameDraftOrigin(draft,entityKind,origin) {
  if (!draft || draft.kind!==entityKind || !kinds.includes(entityKind)) return false;
  const candidate=normalizeDraftOrigin(origin,entityKind);
  if (!candidate) return false;
  if (candidate.kind==='locations') {
    const current=canonicalLocationIds(draft.data?.locationIds);
    return current!=null && current.length===candidate.locationIds.length && current.every((id,index)=>id===candidate.locationIds[index]);
  }
  const previous=normalizeDraftOrigin(draft.origin,entityKind);
  return previous?.kind===candidate.kind && (candidate.kind==='blank'?previous.entityKind===candidate.entityKind:previous.key===candidate.key);
}
const textFields = {title:150, description:6000, type:40, city:120, district:20, locationId:200, address:500, neighborhood:180, street:180, houseNumber:32, postalCode:4, streetId:64, condition:80, building:80, constructionAge:80, view:80, ceilingHeight:80, heatingType:80, secondaryHeatingType:80, energyRating:20, parkingType:200, moveIn:200, financing:300};
const numericFields = ['price','area','rooms','wholeRooms','halfRooms','lotArea','floor','minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms'];
const booleanFields = ['balcony','elevator','insulated','airConditioning','solarPanels'];
const listFields = ['locationIds','districts','conditions','buildings','constructionAges','views','floors','heatingTypes','parkingTypes','images'];
/** Persist only editable form fields. Authentication and origin metadata never enter an entity payload. */
export function sanitizeDraftData(value = {}, kind = 'search') {
  const result={};
  if (!value || typeof value !== 'object' || Array.isArray(value)) return result;
  for (const [field,limit] of Object.entries(textFields)) if (Object.hasOwn(value,field) && (value[field] == null || typeof value[field] === 'string')) result[field]=value[field] == null ? null : text(value[field],limit);
  for (const field of numericFields) if (Object.hasOwn(value,field)) {
    const item=value[field]; if (item == null || typeof item === 'number' && Number.isFinite(item) || typeof item === 'string') result[field]=typeof item === 'string' ? item.slice(0,80) : item;
  }
  for (const field of booleanFields) if (Object.hasOwn(value,field)) {
    const item=value[field]; if (item == null || typeof item === 'boolean' || typeof item === 'string') result[field]=typeof item === 'string' ? item.slice(0,10) : item;
  }
  for (const field of listFields) if (Object.hasOwn(value,field)) {
    const items=value[field];
    if (Array.isArray(items)) result[field]=items.slice(0,field === 'images' ? 12 : 50).filter(item=>typeof item === 'string' || field === 'floors' && typeof item === 'number' && Number.isFinite(item)).map(item=>typeof item === 'string' ? item.slice(0,field === 'images' ? 2000 : 200) : item);
    else if (typeof items === 'string') result[field]=items.slice(0,field === 'images' ? 12 * 2001 : 1000);
  }
  if (Array.isArray(value.locations)) result.locations=safeLocations(value.locations);
  if (kind === 'property' && value.addressDetails && typeof value.addressDetails === 'object') {
    result.addressDetails={};
    for (const field of ['street','houseNumber','postalCode','streetId']) if (typeof value.addressDetails[field] === 'string') result.addressDetails[field]=text(value.addressDetails[field],textFields[field]);
  }
  if (kind === 'search') for (const field of ['address','neighborhood','street','houseNumber','postalCode','streetId']) delete result[field];
  return result;
}
function editorState(value = {}) {
  return {query:text(value?.query,120),streetQuery:text(value?.streetQuery,180),titleGenerated:value?.titleGenerated===true,completedSteps:[...new Set((Array.isArray(value?.completedSteps)?value.completedSteps:[]).filter(step=>Number.isInteger(step)&&step>=0&&step<5))].sort(),locations:safeLocations(value?.locations)};
}
function normalizedDraft(value) {
  if (!value || typeof value !== 'object' || value.version !== VERSION || !validUuid(value.id) || !kinds.includes(value.kind) || !phases.includes(value.phase)) return null;
  const createdAt=Date.parse(value.createdAt),updatedAt=Date.parse(value.updatedAt),expiresAt=Date.parse(value.expiresAt);
  if (![createdAt,updatedAt,expiresAt].every(Number.isFinite) || createdAt>updatedAt || expiresAt<=updatedAt || expiresAt>updatedAt+DRAFT_TTL_MS) return null;
  const result={version:VERSION,id:value.id.toLowerCase(),kind:value.kind,data:sanitizeDraftData(value.data,value.kind),step:Number.isInteger(value.step)?Math.min(4,Math.max(0,value.step)):0,phase:value.phase,editor:editorState(value.editor),createdAt:new Date(createdAt).toISOString(),updatedAt:new Date(updatedAt).toISOString(),expiresAt:new Date(expiresAt).toISOString()};
  const origin=normalizeDraftOrigin(value.origin,value.kind);if (origin) result.origin=origin;
  if (typeof value.expectedEmail === 'string' && email(value.expectedEmail)) result.expectedEmail=email(value.expectedEmail);
  if (typeof value.ownerId === 'string' && value.ownerId.trim()) result.ownerId=value.ownerId.slice(0,100);
  result.creationRequestId=validUuid(value.creationRequestId)?value.creationRequestId.toLowerCase():result.id;
  if (value.completedData && typeof value.completedData === 'object') result.completedData=freeze(sanitizeDraftData(value.completedData,value.kind));
  if (typeof value.savedEntityId === 'string' && value.savedEntityId) result.savedEntityId=value.savedEntityId.slice(0,100);
  if (['saving','saved'].includes(result.phase) && (!result.creationRequestId || !result.completedData || !result.ownerId)) return null;
  return result;
}
function requiredDraft(draft) { const result=normalizedDraft(draft); if (!result) throw new Error('A mentett vázlat sérült. Kezdd újra a kitöltést.'); return result; }
function touch(draft,now) { const at=Math.max(clock(now),Date.parse(draft.updatedAt));return {...draft,updatedAt:new Date(at).toISOString(),expiresAt:new Date(at+DRAFT_TTL_MS).toISOString()}; }
export function createDraft(kind,data={}, {now,id,editor,origin}={}) {
  if (!kinds.includes(kind)) throw new Error('Érvénytelen profiltípus.');
  if (id != null && !validUuid(id)) throw new Error('Érvénytelen vázlatazonosító.');
  const at=clock(now),date=new Date(at).toISOString(),draftId=(id??newUuid()).toLowerCase();
  const draft={version:VERSION,id:draftId,creationRequestId:draftId,kind,data:sanitizeDraftData(data,kind),step:0,phase:'editing',editor:editorState(editor),createdAt:date,updatedAt:date,expiresAt:new Date(at+DRAFT_TTL_MS).toISOString()};
  const safeOrigin=normalizeDraftOrigin(origin,kind);if (safeOrigin) draft.origin=safeOrigin;
  return draft;
}
export function updateDraft(draft,patch={}, {now}={}) {
  const current=requiredDraft(draft),result=touch(current,now);
  if (patch.phase != null && !phases.includes(patch.phase)) throw new Error('Érvénytelen vázlatállapot.');
  if (patch.data && current.completedData && patch.phase !== 'editing') throw new Error('A lezárt vázlat szerkesztéséhez nyisd meg újra a kitöltést.');
  if (patch.phase === 'editing') { delete result.completedData;delete result.savedEntityId; }
  if (patch.data) result.data=sanitizeDraftData({...current.data,...patch.data},current.kind);
  if (patch.editor) result.editor=editorState({...current.editor,...patch.editor});
  if (Number.isInteger(patch.step)) result.step=Math.min(4,Math.max(0,patch.step));
  if (patch.phase) result.phase=patch.phase;
  return requiredDraft(result);
}
export function saveDraft(draft,storage=globalThis.localStorage) {
  const result=requiredDraft(draft),raw=JSON.stringify(result);
  if (raw.length>MAX_BYTES) throw new Error('A vázlat túl nagy a helyi mentéshez.');
  try { if (!storage?.setItem) throw new Error();storage.setItem(DRAFT_STORAGE_KEY,raw); } catch { throw new Error('A vázlat nem menthető a böngészőben. Ellenőrizd a helyi tárhelyet.'); }
  return result;
}
export function clearDraft(id,storage=globalThis.localStorage) {
  try { const raw=storage?.getItem(DRAFT_STORAGE_KEY);if (!raw || JSON.parse(raw)?.id?.toLowerCase() !== String(id).toLowerCase()) return false; storage.removeItem(DRAFT_STORAGE_KEY);return true; } catch { return false; }
}
export function loadDraft(storage=globalThis.localStorage,{now}={}) {
  let raw,value;
  try { raw=storage?.getItem(DRAFT_STORAGE_KEY);if (!raw || raw.length>MAX_BYTES) return null;value=JSON.parse(raw); } catch {return null;}
  const draft=normalizedDraft(value);
  if (!draft || Date.parse(draft.expiresAt)<=clock(now)) {if (value?.id) clearDraft(value.id,storage);return null;}
  return draft;
}
function completed(draft) { const result={...draft};if (!result.completedData) result.completedData=freeze(clone(result.data));return result; }
export function prepareDraftForAuth(draft,expectedEmail,{now}={}) {
  const result=completed(touch(requiredDraft(draft),now));
  if (expectedEmail != null && expectedEmail !== '') {
    const normalized=email(expectedEmail);if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) throw new Error('Adj meg egy érvényes e-mail-címet.');
    if (result.expectedEmail && result.expectedEmail !== normalized) throw new Error('Ez a vázlat másik e-mail-címhez tartozik.');
    result.expectedEmail=normalized;
  }
  result.phase='awaiting-auth';return result;
}
export function bindDraft(draft,user,{now}={}) {
  const result=touch(requiredDraft(draft),now),ownerId=typeof user?.id === 'string'?user.id:'';
  if (!ownerId || !email(user?.email)) throw new Error('A vázlat mentéséhez jelentkezz be.');
  if (result.ownerId && result.ownerId !== ownerId || result.expectedEmail && result.expectedEmail !== email(user.email)) throw new Error('A vázlat másik fiókhoz tartozik. Jelentkezz be a kitöltéshez használt e-mail-címmel.');
  result.ownerId=ownerId;result.expectedEmail=email(user.email);return result;
}
export function prepareDraftSave(draft,user,{now}={}) { const result=completed(bindDraft(draft,user,{now}));result.phase='saving';return result; }
export function markDraftSaved(draft,entityId,{now}={}) {
  const result=touch(requiredDraft(draft),now);if (!result.ownerId || !result.completedData || typeof entityId !== 'string' || !entityId) throw new Error('A mentés eredménye hiányos.');
  return {...result,phase:'saved',savedEntityId:entityId.slice(0,100)};
}

const finite = value => value == null || value === '' || typeof value === 'boolean' ? null : Number.isFinite(Number(value)) ? Number(value) : null;
const selectedLocations = (source,override) => safeLocations(override ?? source?.locations);
const propertyTypes = ['Lakás','Ház','Telek','Nyaraló','Garázs','Iroda','Üzlethelyiség','Egyéb'];
const knownChoice = (value,options,normalize=value=>value) => options.includes(normalize(value)) ? normalize(value) : '';
const single = (values,options,normalize) => Array.isArray(values) && values.length===1 ? knownChoice(values[0],options,normalize) : '';
/** Strict public seed contract shared by the API adapter and the fictional demo. */
export function sanitizeTeaserPrefill(kind,value={}, {pricesInHuf=false}={}) {
  const source=value && typeof value==='object'?value:{},data={locations:safeLocations(source.locations)};
  if (propertyTypes.includes(source.type)) data.type=source.type;
  const numbers=kind==='property'?['price','area','rooms','wholeRooms','halfRooms','lotArea','floor']:['minPrice','maxPrice','minArea','maxArea','minRooms','maxRooms'];
  for (const field of numbers) {const number=finite(source[field]);data[field]=number!=null && pricesInHuf && ['price','minPrice','maxPrice'].includes(field)?number/1000000:number;}
  if (kind==='property') for (const [field,options,normalize] of [['condition',CONDITION_OPTIONS,normalizeCondition],['building',BUILDING_OPTIONS,normalizeBuilding],['constructionAge',CONSTRUCTION_AGE_OPTIONS],['view',VIEW_OPTIONS],['heatingType',HEATING_OPTIONS]]) data[field]=knownChoice(source[field],options,normalize);
  else {
    for (const [field,options,normalize] of [['conditions',CONDITION_OPTIONS,normalizeCondition],['buildings',BUILDING_OPTIONS,normalizeBuilding],['constructionAges',CONSTRUCTION_AGE_OPTIONS],['views',VIEW_OPTIONS],['heatingTypes',HEATING_OPTIONS]]) data[field]=[...new Set((Array.isArray(source[field])?source[field]:[]).slice(0,50).map(value=>knownChoice(value,options,normalize)).filter(Boolean))];
    data.floors=[...new Set((Array.isArray(source.floors)?source.floors:[]).slice(0,50).map(finite).filter(value=>value!=null&&FLOOR_OPTIONS.some(option=>option.value===value)))];
  }
  data.ceilingHeight=knownChoice(source.ceilingHeight,CEILING_HEIGHT_OPTIONS);data.balcony=source.balcony===true;data.elevator=source.elevator===true;
  if (data.type==='Ház') {data.balcony=false;data.elevator=false;if (kind==='search') data.floors=[];else data.floor=null;}
  return data;
}
/** Names describe the user's new profile and remain ordinary editable form values. */
export function suggestEntityTitle(kind,data={}) {
  const locations=selectedLocations(data),ids=kind==='property'?[data.locationId]:data.locationIds;
  const places=locations.length?locations:(Array.isArray(ids)?ids:[]).map(getLocation).filter(Boolean);
  const type=propertyTypes.includes(data.type)?data.type:'Ingatlan';
  const place=places[0]?.label || '';
  const suffix=places.length>1?` +${places.length-1} helyszín`:'';
  const start=kind==='property'?`${type} eladó`:`${type} keresés`;
  const number=value=>new Intl.NumberFormat('hu-HU',{maximumFractionDigits:2}).format(value);
  const detail=(value,unit)=>{const parsed=finite(value);return parsed!=null && parsed>0?`${number(parsed)}${unit}`:'';};
  const price=kind==='property'?detail(data.price,' M Ft'):detail(data.maxPrice,' M Ft-ig');
  const area=kind==='property'?detail(data.area,' m²'):detail(data.minArea,'+ m²');
  const rooms=kind==='property'?detail(data.rooms,' szoba'):detail(data.minRooms,'+ szoba');
  // Keep only two compact identifying figures, with room count as a fallback.
  const figures=[price,area,rooms].filter(Boolean).filter(value=>value.length<=20).slice(0,2);
  while (figures.length && start.length+suffix.length+figures.join(', ').length+(place?16:3)>70) figures.pop();
  const tail=figures.length?` · ${figures.join(', ')}`:'';
  const prefix=`${start}${place?' – ':''}`,available=70-prefix.length-suffix.length-tail.length;
  const label=place.length<=available?place:`${place.slice(0,Math.max(0,available-1)).trimEnd()}…`;
  return `${prefix}${label}${suffix}${tail}`;
}
/** Public teasers are seeds, never identities or an exact address for another home. Prices use the UI's million-HUF unit. */
export function prefillFromTeaser(targetKind,teaser,{locations}={}) {
  if (!kinds.includes(targetKind)) throw new Error('Érvénytelen profiltípus.');
  const source=teaser?.prefill && typeof teaser.prefill === 'object'?teaser.prefill:teaser??{};
  const chosen=selectedLocations(source,locations),data={};
  if (propertyTypes.includes(source.type)) data.type=source.type;
  if (targetKind==='search') {
    data.locations=chosen;data.locationIds=chosen.map(location=>location.id);
    const price=finite(source.price),area=finite(source.area),rooms=finite(source.rooms);
    // Multiply by integer ratios before rounding: 50 * 1.1 is not exactly 55 in JS.
    const maxPrice=price!=null && price>0?Math.ceil(price*11/50)*5:null;
    const minArea=area!=null && area>0?Math.floor(area*9/50)*5:null;
    Object.assign(data,{minPrice:null,maxPrice,minArea:minArea>0?minArea:null,maxArea:null,minRooms:rooms,maxRooms:null});
    for (const [field,plural,options,normalize] of [['condition','conditions',CONDITION_OPTIONS,normalizeCondition],['building','buildings',BUILDING_OPTIONS,normalizeBuilding],['constructionAge','constructionAges',CONSTRUCTION_AGE_OPTIONS],['view','views',VIEW_OPTIONS],['heatingType','heatingTypes',HEATING_OPTIONS]]) {
      const choice=knownChoice(source[field],options,normalize);data[plural]=choice?[choice]:[];
    }
    data.ceilingHeight=knownChoice(source.ceilingHeight,CEILING_HEIGHT_OPTIONS);
    const floor=finite(source.floor);data.floors=floor==null?[]:FLOOR_OPTIONS.some(option=>option.value===Math.min(11,floor))?[Math.min(11,floor)]:[];
    data.balcony=source.balcony===true;data.elevator=source.elevator===true;
  } else {
    if (chosen.length===1 && isPropertyLocation(chosen[0])) {data.locationId=chosen[0].id;data.locations=chosen;}
    for (const [min,max,target] of [['minPrice','maxPrice','price'],['minArea','maxArea','area'],['minRooms','maxRooms','rooms']]) {
      const low=finite(source[min]),high=finite(source[max]);if (low!=null && low===high) data[target]=low;
    }
    for (const [plural,field,options,normalize] of [['conditions','condition',CONDITION_OPTIONS,normalizeCondition],['buildings','building',BUILDING_OPTIONS,normalizeBuilding],['constructionAges','constructionAge',CONSTRUCTION_AGE_OPTIONS],['views','view',VIEW_OPTIONS],['heatingTypes','heatingType',HEATING_OPTIONS]]) {const choice=single(source[plural],options,normalize);if (choice) data[field]=choice;}
    const ceilingHeight=knownChoice(source.ceilingHeight,CEILING_HEIGHT_OPTIONS);if (ceilingHeight) data.ceilingHeight=ceilingHeight;
    if (Array.isArray(source.floors) && source.floors.length===1 && finite(source.floors[0])!=null && finite(source.floors[0])!==11) data.floor=finite(source.floors[0]);
    if (source.balcony===true) data.balcony=true;if (source.elevator===true) data.elevator=true;
  }
  if (data.type==='Ház') {data.balcony=false;data.elevator=false;if (targetKind==='search') data.floors=[];else delete data.floor;}
  data.title=suggestEntityTitle(targetKind,data);
  return sanitizeDraftData(data,targetKind);
}
