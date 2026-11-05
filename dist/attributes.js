/** Shared optional property data and search filters. Values are the API's Hungarian labels. */
export const CONDITION_OPTIONS = Object.freeze(['Felújítandó','Átlagos','Jó','Új/felújított']);
export const BUILDING_OPTIONS = Object.freeze(['Tégla','Panel','Csúsztatott zsalu','Vályog','Szilikát','Vegyes falazat','Fa','Könnyűszerkezet','Kő és tégla','Rönkház','Passzívház','Egyéb']);
export const CONSTRUCTION_AGE_OPTIONS = Object.freeze(['10 évnél fiatalabb','10–30 év közötti','31–40 év közötti','41–50 év közötti','Több mint 50 éves']);
export const VIEW_OPTIONS = Object.freeze(['Kertre néző','Utcai','Udvari','Panorámás']);
export const CEILING_HEIGHT_OPTIONS = Object.freeze(['3 m alatti','3 m feletti']);
export const FLOOR_OPTIONS = Object.freeze([
  {value:-1,label:'Szuterén'}, {value:0,label:'Földszint'},
  ...Array.from({length:10},(_,index)=>({value:index+1,label:String(index+1)})),
  {value:11,label:'11 vagy afölötti'}
].map(Object.freeze));

const normalized = value => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLocaleLowerCase('hu');
const conditionAliases = new Map([
  ['Felújított','Új/felújított'],['Újszerű','Új/felújított'],['Új építésű','Új/felújított'],['Jó állapotú','Jó']
].map(([key,value])=>[normalized(key),value]));
const text = value => value == null ? '' : String(value).trim();
function choice(value, options, {strict = false, aliases, allowUnknown = false} = {}) {
  const raw = text(value);
  if (!raw) return '';
  const key = normalized(raw);
  const result = options.find(option=>normalized(option) === key) || aliases?.get(key);
  if (result) return result;
  if (strict && !allowUnknown) throw new Error(`Érvénytelen választás: ${raw.slice(0,80)}.`);
  return raw;
}
export const normalizeCondition = (value, options = {}) => choice(value,CONDITION_OPTIONS,{...options,aliases:conditionAliases});
export const normalizeBuilding = (value, options = {}) => choice(value,BUILDING_OPTIONS,options);
function choices(value, options, normalize, strict) {
  if (value == null || value === '') return [];
  if (!Array.isArray(value)) {
    if (strict) throw new Error('A keresési feltételeket listaként add meg.');
    value = [value];
  }
  const result = value.map(item=>normalize(item,{strict}));
  if (strict && result.some(item=>!item)) throw new Error('Érvénytelen választás a keresési feltételek között.');
  return [...new Set(result.filter(Boolean))];
}
function nullableBoolean(value, strict) {
  if (value == null || value === '') return null;
  if (value === true || value === 1 || normalized(value) === 'true') return true;
  if (value === false || value === 0 || normalized(value) === 'false') return false;
  if (strict) throw new Error('Válassz az igen, nem vagy nincs megadva lehetőségek közül.');
  return null;
}
function optionalText(value, maximum, strict) {
  const result = text(value);
  if (strict && result.length > maximum) throw new Error(`A szöveg legfeljebb ${maximum} karakter lehet.`);
  if (strict && (/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/.test(result) || /(?:\+?36|06)[\s().-]*(?:\d[\s().-]*){8,9}/.test(result))) {
    throw new Error('Elérhetőséget csak kölcsönös párosítás után lehet megosztani.');
  }
  return result;
}
function floorNumber(value, strict, allowLegacy = false) {
  if (value == null || (typeof value === 'string' && !value.trim())) return null;
  if (typeof value === 'boolean') {
    if (strict) throw new Error('Az emelet -1 és 200 közötti egész szám legyen.');
    return null;
  }
  const number = Number(value);
  if (Number.isInteger(number) && number >= (strict && !allowLegacy ? -1 : -5) && number <= 200) return number;
  if (strict) throw new Error('Az emelet -1 és 200 közötti egész szám legyen.');
  return null;
}
/** Normalize without mutating the entity; unknown old labels survive reads. */
export function normalizePropertyAttributes(value = {}, {strict = false, previous, allowLegacyUnknown = false} = {}) {
  const legacyOptions = field => ({strict,allowUnknown:allowLegacyUnknown || (!!previous && text(value[field]) === text(previous[field]))});
  return {
    ...value,
    condition:normalizeCondition(value.condition,legacyOptions('condition')),
    building:normalizeBuilding(value.building,legacyOptions('building')),
    constructionAge:choice(value.constructionAge,CONSTRUCTION_AGE_OPTIONS,{strict}),
    view:choice(value.view,VIEW_OPTIONS,{strict}),
    ceilingHeight:choice(value.ceilingHeight,CEILING_HEIGHT_OPTIONS,{strict}),
    floor:floorNumber(value.floor,strict,allowLegacyUnknown || (!!previous && value.floor != null && Number(value.floor) === Number(previous.floor))),
    heatingType:optionalText(value.heatingType,80,strict),
    energyRating:optionalText(value.energyRating,20,strict),
    parkingType:optionalText(value.parkingType,80,strict),
    insulated:nullableBoolean(value.insulated,strict),
    airConditioning:nullableBoolean(value.airConditioning,strict),
    solarPanels:nullableBoolean(value.solarPanels,strict)
  };
}
export function normalizeSearchAttributes(value = {}, {strict = false} = {}) {
  const legacy = (plural,singular) => Object.hasOwn(value,plural) ? value[plural] : value[singular] && !['barmilyen','mindegy','osszes'].includes(normalized(value[singular])) ? [value[singular]] : [];
  const floors = value.floors == null || value.floors === '' ? [] : value.floors;
  if (strict && !Array.isArray(floors)) throw new Error('Az emeleteket listaként add meg.');
  const normalizedFloors = [...new Set((Array.isArray(floors) ? floors : [floors]).map(floor=>floor == null || typeof floor === 'boolean' || (typeof floor === 'string' && !floor.trim()) ? NaN : Number(floor)))];
  if (strict && normalizedFloors.some(floor=>!Number.isInteger(floor) || !FLOOR_OPTIONS.some(option=>option.value === floor))) throw new Error('Érvénytelen emeletválasztás.');
  return {
    ...value,
    conditions:choices(legacy('conditions','condition'),CONDITION_OPTIONS,normalizeCondition,strict),
    buildings:choices(legacy('buildings','building'),BUILDING_OPTIONS,normalizeBuilding,strict),
    constructionAges:choices(value.constructionAges,CONSTRUCTION_AGE_OPTIONS,(item,options)=>choice(item,CONSTRUCTION_AGE_OPTIONS,options),strict),
    views:choices(value.views,VIEW_OPTIONS,(item,options)=>choice(item,VIEW_OPTIONS,options),strict),
    ceilingHeight:choice(value.ceilingHeight,CEILING_HEIGHT_OPTIONS,{strict}),
    floors:normalizedFloors
  };
}
/** OR within a list, AND between attributes; missing seller data never satisfies a filter. */
export function attributesCompatible(property, search) {
  const p = normalizePropertyAttributes(property), s = normalizeSearchAttributes(search);
  for (const [propertyField, searchField, options] of [
    ['condition','conditions',CONDITION_OPTIONS],['building','buildings',BUILDING_OPTIONS],
    ['constructionAge','constructionAges',CONSTRUCTION_AGE_OPTIONS],['view','views',VIEW_OPTIONS]
  ]) {
    if (s[searchField].length && (!options.includes(p[propertyField]) || !s[searchField].includes(p[propertyField]))) return false;
  }
  if (s.ceilingHeight && (!CEILING_HEIGHT_OPTIONS.includes(p.ceilingHeight) || s.ceilingHeight !== p.ceilingHeight)) return false;
  if (s.floors.length) {
    const bucket = p.floor == null ? null : p.floor >= 11 ? 11 : p.floor;
    if (bucket == null || !FLOOR_OPTIONS.some(option=>option.value === bucket) || !s.floors.includes(bucket)) return false;
  }
  return true;
}
