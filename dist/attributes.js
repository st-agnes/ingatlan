import {energyCode,energyIndex,meetsEnergyMinimum} from './energy-rating.js';
/** Shared optional property data and search filters. Values are the API's Hungarian labels. */
export const CONDITION_OPTIONS = Object.freeze(['Felújítandó','Átlagos','Jó','Új/felújított']);
export const BUILDING_OPTIONS = Object.freeze(['Tégla','Panel','Csúsztatott zsalu','Vályog','Szilikát','Vegyes falazat','Fa','Könnyűszerkezet','Kő és tégla','Rönkház','Passzívház','Egyéb']);
export const CONSTRUCTION_AGE_OPTIONS = Object.freeze(['10 évnél fiatalabb','10–30 év közötti','31–40 év közötti','41–50 év közötti','Több mint 50 éves']);
export const VIEW_OPTIONS = Object.freeze(['Kertre néző','Utcai','Udvari','Panorámás']);
export const HEATING_OPTIONS = Object.freeze(['Gázkazán / cirkó','Gázkonvektor','Távfűtés','Házközponti fűtés','Hőszivattyú','Fűtő klíma','Elektromos fűtés','Fa- / vegyes tüzelésű kazán','Pelletkazán','Kályha / cserépkályha','Kandalló','Egyéb','Nincs fűtés']);
export const PARKING_OPTIONS = Object.freeze(['Utcai parkolás','Udvari beálló','Fedett beálló','Garázs','Mélygarázs','Teremgarázs','Egyéb']);
export const CEILING_HEIGHT_OPTIONS = Object.freeze(['3 m alatti','3 m feletti']);
export const FLOOR_OPTIONS = Object.freeze([
  {value:-1,label:'Szuterén'}, {value:0,label:'Földszint'}, {value:0.5,label:'Magasföldszint'},
  ...Array.from({length:7},(_,index)=>({value:index+1,label:String(index+1)})),
  {value:8,label:'8 vagy afölötti'}
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
const heatingAliases = new Map([['Gázkazán','Gázkazán / cirkó'],['Gázcirkó','Gázkazán / cirkó'],['Klíma','Fűtő klíma'],['Vegyes tüzelésű kazán','Fa- / vegyes tüzelésű kazán'],['Cserépkályha','Kályha / cserépkályha']].map(([key,value])=>[normalized(key),value]));
export const normalizeHeating = (value, options = {}) => choice(value,HEATING_OPTIONS,{...options,aliases:heatingAliases});
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
    if (strict) throw new Error('Válassz érvényes emeletet vagy magasföldszintet.');
    return null;
  }
  const number = Number(value);
  if ((Number.isInteger(number) || number === 0.5) && number >= (strict && !allowLegacy ? -1 : -5) && number <= 200) return number;
  if (strict) throw new Error('Válassz érvényes emeletet vagy magasföldszintet.');
  return null;
}
function buildingFloorNumber(value, strict) {
  if (value == null || (typeof value === 'string' && !value.trim())) return null;
  const number = typeof value === 'boolean' ? NaN : Number(value);
  if (Number.isInteger(number) && number >= 0 && number <= 200) return number;
  if (strict) throw new Error('Az épület legfelső emelete 0 és 200 közötti egész szám legyen.');
  return null;
}
/** Keep explicit whole/half counts; derive them only for exact legacy half-room totals. */
export function normalizePropertyRooms(value = {}, {strict = false, previous} = {}) {
  const supplied = (object, field) => object[field] != null && object[field] !== '' && !(typeof object[field] === 'string' && !object[field].trim());
  if (supplied(value,'wholeRooms') || supplied(value,'halfRooms')) {
    const count = field => supplied(value,field) && typeof value[field] !== 'boolean' ? Number(value[field]) : supplied(value,field) ? NaN : 0;
    const wholeRooms = count('wholeRooms'), halfRooms = count('halfRooms');
    const rooms = wholeRooms + halfRooms / 2;
    if (Number.isInteger(wholeRooms) && Number.isInteger(halfRooms) && wholeRooms >= 0 && halfRooms >= 0 && wholeRooms <= 1000 && halfRooms <= 1000 && rooms > 0 && rooms <= 1000) {
      if (strict && supplied(value,'rooms')) {
        const total = typeof value.rooms === 'boolean' ? NaN : Number(value.rooms);
        if (!Number.isFinite(total) || total < 0 || (total > 0 && total !== rooms)) throw new Error('A szobaszám nem egyezik az egész és fél szobák összegével.');
      }
      return {...value, wholeRooms, halfRooms, rooms};
    }
    if (strict) throw new Error('Az egész és fél szobák száma nemnegatív egész szám legyen, összesen legalább fél és legfeljebb 1000 szobával.');
    return {...value, wholeRooms:null, halfRooms:null};
  }
  const rooms = supplied(value,'rooms') && typeof value.rooms !== 'boolean' ? Number(value.rooms) : value.rooms;
  if (previous && Number(previous.rooms) === rooms && (supplied(previous,'wholeRooms') || supplied(previous,'halfRooms'))) {
    const retained = normalizePropertyRooms(previous);
    if (retained.wholeRooms != null && retained.halfRooms != null) return {...value,rooms,wholeRooms:retained.wholeRooms,halfRooms:retained.halfRooms};
  }
  const exactHalfTotal = Number.isFinite(rooms) && rooms > 0 && rooms <= 1000 && Number.isInteger(rooms * 2);
  return {...value, rooms, wholeRooms:exactHalfTotal ? Math.floor(rooms) : null, halfRooms:exactHalfTotal ? (rooms % 1 === 0 ? 0 : 1) : null};
}
export function roomLabel(value) {
  const rooms = normalizePropertyRooms(value);
  if (rooms.wholeRooms == null || rooms.halfRooms == null) return `${Number(rooms.rooms).toLocaleString('hu-HU')} szoba`;
  if (!rooms.halfRooms) return `${rooms.wholeRooms} szoba`;
  if (!rooms.wholeRooms) return `${rooms.halfRooms} fél szoba`;
  return `${rooms.wholeRooms} egész + ${rooms.halfRooms} fél szoba`;
}
function parkingSelections(value, {strict, previous, allowLegacyUnknown}) {
  let input = value.parkingTypes;
  if (input == null) {
    if (previous?.parkingTypes != null && text(value.parkingType) === text(previous.parkingType)) input = previous.parkingTypes;
    else input = text(value.parkingType) ? [value.parkingType] : [];
  }
  if (!Array.isArray(input)) {
    if (strict) throw new Error('A parkolóhelyeket listaként add meg.');
    input = [input];
  }
  if (strict && input.length > 20) throw new Error('Legfeljebb 20 parkolóhely-választás adható meg.');
  const previousSelections = previous ? previous.parkingTypes ?? (text(previous.parkingType) ? [previous.parkingType] : []) : [];
  const result = input.map(item => choice(optionalText(item,80,strict),PARKING_OPTIONS,{strict,allowUnknown:allowLegacyUnknown || (Array.isArray(previousSelections) && previousSelections.some(old=>text(old) === text(item)))}));
  if (strict && result.some(item=>!item)) throw new Error('Érvénytelen parkolóhely-választás.');
  return [...new Set(result.filter(Boolean))];
}
/** Retired supplementary heating stays readable without silently rewriting old metadata. */
function retiredHeating(value,strict,previous) {
  const raw=optionalText(value,80,strict);
  normalizeHeating(raw,{strict,allowUnknown:!!previous&&raw===text(previous.secondaryHeatingType)});
  return raw;
}
/** Normalize without mutating the entity; unknown old labels survive reads. */
export function normalizePropertyAttributes(value = {}, {strict = false, previous, allowLegacyUnknown = false} = {}) {
  const legacyOptions = field => ({strict,allowUnknown:allowLegacyUnknown || (!!previous && text(value[field]) === text(previous[field]))});
  const parkingTypes = parkingSelections(value,{strict,previous,allowLegacyUnknown});
  const house = normalized(value.type) === 'haz', apartment = normalized(value.type) === 'lakas';
  const floor = strict && house ? null : floorNumber(value.floor,strict,allowLegacyUnknown || (!!previous && value.floor != null && Number(value.floor) === Number(previous.floor)));
  const buildingFloors = house ? null : buildingFloorNumber(value.buildingFloors,strict);
  const upperRange = !house && nullableBoolean(value.floorIsUpperRange,strict) === true;
  const hideStreet = nullableBoolean(value.hideStreet,strict) !== false;
  const hideHouseNumber = hideStreet || nullableBoolean(value.hideHouseNumber,strict) !== false;
  const energyRating = optionalText(value.energyRating,20,strict);
  const energyRatingScheme = optionalText(value.energyRatingScheme,20,strict);
  if (strict && energyRatingScheme && energyRatingScheme !== '2023') throw new Error('Érvénytelen energetikai tanúsítványrendszer.');
  if (strict && energyRatingScheme === '2023' && energyRating && energyIndex(energyRating)<0) throw new Error('Válassz érvényes energetikai kategóriát.');
  if (strict && upperRange && floor !== 9) throw new Error('A 9 vagy afölötti jelöléshez a csoportosított emeletet válaszd.');
  if (strict && floor != null && buildingFloors != null && floor > buildingFloors && !(floor === 0.5 && buildingFloors === 0)) throw new Error('Az ingatlan emelete nem lehet magasabb az épület legfelső emeleténél.');
  return {
    ...normalizePropertyRooms(value,{strict,previous}),
    condition:normalizeCondition(value.condition,legacyOptions('condition')),
    building:normalizeBuilding(value.building,legacyOptions('building')),
    constructionAge:choice(value.constructionAge,CONSTRUCTION_AGE_OPTIONS,{strict}),
    view:choice(value.view,VIEW_OPTIONS,{strict}),
    ceilingHeight:choice(value.ceilingHeight,CEILING_HEIGHT_OPTIONS,{strict}),
    floor, buildingFloors, floorIsUpperRange:upperRange && floor === 9,
    hideStreet,hideHouseNumber,isAttic:house ? null : nullableBoolean(value.isAttic,strict),
    balcony:strict && house ? null : nullableBoolean(value.balcony==='on'?true:value.balcony,strict),
    privateGarden:apartment ? nullableBoolean(value.privateGarden,strict) : null,
    sharedGarden:null, // Retained wire field; the shared-garden option is retired.
    heatingType:normalizeHeating(optionalText(value.heatingType,80,strict),legacyOptions('heatingType')),
    secondaryHeatingType:retiredHeating(value.secondaryHeatingType,strict,previous),
    energyRating:energyRatingScheme==='2023'?energyCode(energyRating):energyRating,energyRatingScheme:energyRating?energyRatingScheme:'',
    parkingTypes, parkingType:parkingTypes.join(', '),
    insulated:nullableBoolean(value.insulated,strict),
    airConditioning:nullableBoolean(value.airConditioning,strict),
    solarPanels:nullableBoolean(value.solarPanels,strict)
  };
}
export function normalizeSearchAttributes(value = {}, {strict = false} = {}) {
  const legacy = (plural,singular) => Object.hasOwn(value,plural) ? value[plural] : value[singular] && !['barmilyen','mindegy','osszes'].includes(normalized(value[singular])) ? [value[singular]] : [];
  const floors = (strict && value.type === 'Ház') || value.floors == null || value.floors === '' ? [] : value.floors;
  if (strict && !Array.isArray(floors)) throw new Error('Az emeleteket listaként add meg.');
  const rawFloors = (Array.isArray(floors) ? floors : [floors]).map(floor=>floor == null || typeof floor === 'boolean' || (typeof floor === 'string' && !floor.trim()) ? NaN : Number(floor));
  if (strict && rawFloors.some(floor=>!FLOOR_OPTIONS.some(option=>option.value === floor) && ![9,10,11].includes(floor))) throw new Error('Érvénytelen emeletválasztás.');
  const atticPreference = text(value.atticPreference);
  if (strict && !['','only','exclude'].includes(atticPreference)) throw new Error('Válassz érvényes tetőtéri feltételt.');
  const minEnergyRating = text(value.minEnergyRating);
  if (strict && minEnergyRating && energyIndex(minEnergyRating)<0) throw new Error('Válassz érvényes minimum energetikai kategóriát.');
  // Canonicalize old search buckets on read/save, without changing raw creation receipts.
  const normalizedFloors = [...new Set(rawFloors.map(floor=>Number.isInteger(floor) && floor >= 8 && floor <= 11 ? 8 : floor))];
  return {
    ...value,
    conditions:choices(legacy('conditions','condition'),CONDITION_OPTIONS,normalizeCondition,strict),
    buildings:choices(legacy('buildings','building'),BUILDING_OPTIONS,normalizeBuilding,strict),
    constructionAges:choices(value.constructionAges,CONSTRUCTION_AGE_OPTIONS,(item,options)=>choice(item,CONSTRUCTION_AGE_OPTIONS,options),strict),
    views:choices(value.views,VIEW_OPTIONS,(item,options)=>choice(item,VIEW_OPTIONS,options),strict),
    ceilingHeight:choice(value.ceilingHeight,CEILING_HEIGHT_OPTIONS,{strict}),
    floors:normalizedFloors,
    heatingTypes:choices(value.heatingTypes,HEATING_OPTIONS,normalizeHeating,strict),
    atticPreference:normalized(value.type)==='haz'?'':['only','exclude'].includes(atticPreference)?atticPreference:'',
    minEnergyRating:energyCode(minEnergyRating),
    excludeTopFloor:normalized(value.type) === 'haz' ? false : nullableBoolean(value.excludeTopFloor,strict) === true,
    excludeGroundFloorAndBelow:normalized(value.type) === 'haz' ? false : nullableBoolean(value.excludeGroundFloorAndBelow,strict) === true,
    airConditioning:nullableBoolean(value.airConditioning,strict) === true,
    privateGarden:normalized(value.type) === 'lakas' && nullableBoolean(value.privateGarden,strict) === true,
    sharedGarden:false,
    ...(strict && value.type === 'Ház' ? {balcony:false,elevator:false} : {})
  };
}
/** OR within a list, AND between attributes; missing seller data never satisfies a filter. */
export function attributesCompatible(property, search) {
  const p = normalizePropertyAttributes(property), s = normalizeSearchAttributes(search);
  for (const [propertyField, searchField, options] of [
    ['condition','conditions',CONDITION_OPTIONS],['building','buildings',BUILDING_OPTIONS],
    ['constructionAge','constructionAges',CONSTRUCTION_AGE_OPTIONS],['view','views',VIEW_OPTIONS],
    ['heatingType','heatingTypes',HEATING_OPTIONS]
  ]) {
    if (s[searchField].length && (!options.includes(p[propertyField]) || !s[searchField].includes(p[propertyField]))) return false;
  }
  if (s.ceilingHeight && (!CEILING_HEIGHT_OPTIONS.includes(p.ceilingHeight) || s.ceilingHeight !== p.ceilingHeight)) return false;
  if (s.type !== 'Ház' && (s.floors.length || s.atticPreference === 'only')) {
    const bucket = p.floor == null ? null : p.floor >= 8 ? 8 : p.floor;
    const floorMatches = bucket != null && FLOOR_OPTIONS.some(option=>option.value === bucket) && s.floors.includes(bucket);
    if (!floorMatches && !(s.atticPreference === 'only' && p.isAttic === true)) return false;
  }
  if (s.type !== 'Ház' && s.excludeTopFloor && (p.floor == null || p.floorIsUpperRange || p.buildingFloors == null || p.floor >= (p.floor === 0.5 && p.buildingFloors === 0 ? 0.5 : p.buildingFloors))) return false;
  if (s.type !== 'Ház' && s.excludeGroundFloorAndBelow && (p.floor == null || p.floor <= 0)) return false;
  if (s.type!=='Ház' && s.atticPreference === 'exclude' && p.isAttic !== false) return false;
  if (!meetsEnergyMinimum(p,s.minEnergyRating)) return false;
  if (s.airConditioning && p.airConditioning !== true) return false;
  if (s.privateGarden && p.privateGarden !== true) return false;
  return true;
}
