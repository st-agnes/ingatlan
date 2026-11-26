/** Deterministic matching and ordering. Keep weights/formulas aligned with MatchingRanking.cs. */
import {getLocation,resolveLegacyLocations,isPropertyLocation} from './locations.js';
import {agglomerations} from './agglomerations-data.js';
import {CONDITION_OPTIONS,BUILDING_OPTIONS,CONSTRUCTION_AGE_OPTIONS,VIEW_OPTIONS,HEATING_OPTIONS,CEILING_HEIGHT_OPTIONS,
  FLOOR_OPTIONS,normalizeCondition,normalizeBuilding,normalizeHeating,normalizeSearchAttributes} from './attributes.js';

import {energyIndex,knownEnergyRating} from './energy-rating.js';

const FOCUS_WEIGHTS=Object.freeze({maxPrice:32,minRooms:22,minArea:16,condition:10,floor:7,elevator:5,balcony:4,
  building:3,heatingType:2.5,minEnergyRating:3,constructionAge:2,ceilingHeight:1.5,maxArea:1.25,maxRooms:1,minPrice:.75,view:.5,airConditioning:3,privateGarden:3});
export const MATCH_WEIGHTS=Object.freeze({maxPrice:1.2,minRooms:1.1,minArea:1,condition:.36,floor:.25,elevator:.09,balcony:.04,
  building:.0225,heatingType:.0169,minEnergyRating:.04,constructionAge:.0144,ceilingHeight:.01,maxArea:.16,maxRooms:.16,minPrice:.09,view:.01,airConditioning:.04,privateGarden:.04,location:1.5});
export const LOCATION_DISTANCE_SCALE_KM=20;
const norm=value=>String(value??'').normalize('NFD').replace(/\p{M}/gu,'').trim().toUpperCase();
const clamp=value=>Math.min(1,Math.max(0,value));
const members=new Map(agglomerations.map(area=>[area.id,area.settlements]));
const known=(value,options)=>options.includes(value);
const canon=(value,options)=>options.includes(value)?value:options.find(option=>norm(option)===norm(value))??String(value??'').trim();
const categoryLoss=(value,selected,options)=>selected.size?(!known(value,options)||!selected.has(value)?1:0):0;
const conditionIndex=value=>CONDITION_OPTIONS.indexOf(normalizeCondition(value));
const compiledMarker=Symbol('matching-search');
const valueBuildings=new Set(['Tégla','Kő és tégla','Fa','Rönkház','Könnyűszerkezet']);
const valueHeating=new Set(['Gázkazán / cirkó','Távfűtés','Házközponti fűtés']);
const garageTypes=new Set(['Garázs','Mélygarázs','Teremgarázs']);
const drivewayTypes=new Set(['Fedett beálló','Udvari beálló']);
const parkingOptions=['Utcai parkolás','Udvari beálló','Fedett beálló','Garázs','Mélygarázs','Teremgarázs','Egyéb'];

/** The public cap is the only budget used to rank a search for a seller. */
export const publicMaxPrice = search => search?.publicMaxPrice == null || search.publicMaxPrice === '' ? search?.maxPrice ?? null : search.publicMaxPrice;

export function prepareSearch(input={}, {perspective='buyer'}={}) {
  const search={...input,...normalizeSearchAttributes(input),maxPrice:perspective==='seller'?publicMaxPrice(input):input.maxPrice};
  // Saved older rows may have an empty selection plus a canonical legacy city.
  // Save-time validation still rejects empty choices; explicit unknown IDs never fall back.
  let chosen=input.locationIds==null||Array.isArray(input.locationIds)&&input.locationIds.length===0
    ?resolveLegacyLocations(input):Array.isArray(input.locationIds)?input.locationIds.map(getLocation):[];
  if(chosen.length>50||chosen.some(location=>!location))chosen=[];
  const cities=new Set(),districtIds=new Set(),neighborhoodIds=new Set(),streetIds=new Set();
  for(const location of chosen){
    if(location.kind==='street')streetIds.add(location.id);
    else if(location.kind==='neighborhood')neighborhoodIds.add(location.id);
    else if(location.kind==='area')for(const city of members.get(location.id)||[])cities.add(city);
    else if(location.district)districtIds.add(location.id);
    else cities.add(location.city);
  }
  for(const id of districtIds)if(cities.has(getLocation(id).city))districtIds.delete(id);
  const type=norm(search.type);
  const prepared={[compiledMarker]:true,search,cities,districtIds,neighborhoodIds,streetIds,locationLabels:chosen.map(location=>location.label),type,house:type==='HAZ',flat:type==='LAKAS',
    hasNonStreetLocations:cities.size>0||districtIds.size>0||neighborhoodIds.size>0,
    conditions:new Set(search.conditions.map(normalizeCondition)),buildings:new Set(search.buildings.map(normalizeBuilding)),
    heating:new Set(search.heatingTypes),ages:new Set(search.constructionAges),views:new Set(search.views),floors:search.floors};
  prepared.conditionMinimum=prepared.conditions.size?Math.min(...[...prepared.conditions].map(conditionIndex)):null;
  prepared.specificity=specificityOf(prepared);
  return prepared;
}

function propertyPlace(property){
  const id=property.locationId??property.location?.id;
  const legacy=id==null||typeof id==='string'&&!id.trim();
  const location=legacy?resolveLegacyLocations(property)[0]:getLocation(id);
  return isPropertyLocation(location)?location:null;
}
function roomTotal(property){
  if(property.wholeRooms!=null||property.halfRooms!=null){
    const whole=Number(property.wholeRooms??0),half=Number(property.halfRooms??0);
    if(Number.isInteger(whole)&&Number.isInteger(half)&&whole>=0&&half>=0)return whole+half/2;
  }
  return Number(property.rooms);
}

function matchesStreet(property,place,streetIds){
  const street=getLocation(property.streetId??property.addressDetails?.streetId);
  return property.hideStreet===false&&street?.kind==='street'&&streetIds.has(street.id)&&street.city===place.city
    &&(!street.district||!place.district||street.district===place.district);
}

const knownFloor = p => p.floor != null && typeof p.floor !== 'boolean' && (Number.isInteger(Number(p.floor)) || Number(p.floor) === 0.5) && Number(p.floor) >= -5 && Number(p.floor) <= 200;
const effectiveTopFloor = p => Number(p.floor) === 0.5 && Number(p.buildingFloors) === 0 ? 0.5 : Number(p.buildingFloors);
const knownTopFloor = p => knownFloor(p) && p.floorIsUpperRange !== true && p.buildingFloors != null && typeof p.buildingFloors !== 'boolean' && Number.isInteger(Number(p.buildingFloors)) && Number(p.buildingFloors) >= 0 && Number(p.buildingFloors) <= 200 && Number(p.floor) <= effectiveTopFloor(p);
const belowTopFloor = p => knownTopFloor(p) && Number(p.floor) < effectiveTopFloor(p);
const aboveGroundFloor = p => knownFloor(p) && Number(p.floor) > 0;

export function exactLocationMatch(property,input){
  const q=input?.[compiledMarker]?input:prepareSearch(input),place=property&&propertyPlace(property);
  return !!place&&(q.cities.has(place.city)||q.districtIds.has(place.id)
    ||Array.isArray(property.neighborhoodIds)&&property.neighborhoodIds.some(id=>q.neighborhoodIds.has(id))
    ||q.streetIds.size>0&&matchesStreet(property,place,q.streetIds));
}

export function evaluateMatch(property,input,{includeReasons=true,perspective='buyer',locationDistanceKm=null}={}){
  const p=property,q=input?.[compiledMarker]?input:prepareSearch(input,{perspective}),s=q.search,place=p&&propertyPlace(p);
  const exactLocation=exactLocationMatch(p,q);
  const knownDistance=typeof locationDistanceKm==='number'&&Number.isFinite(locationDistanceKm)&&locationDistanceKm>=0;
  if(!p||p.archived||s.archived||p.ownerId===s.ownerId||!place||(!exactLocation&&(!q.hasNonStreetLocations||!knownDistance))
      ||q.type&&norm(p.type)!==q.type||!Number.isFinite(Number(p.price))||!Number.isFinite(Number(p.area))||!Number.isFinite(roomTotal(p)))
    return {eligible:false,isExact:false,score:0,reasons:[],matchDetails:[]};
  let distanceSquared=0;const differences=[];
  function add(key,active,penalty,label){if(!active)return;const amount=Math.max(0,penalty);distanceSquared+=MATCH_WEIGHTS[key]*amount*amount;if(amount>0)differences.push(label);}
  if(!exactLocation){
    const distance=locationDistanceKm/LOCATION_DISTANCE_SCALE_KM;
    distanceSquared+=MATCH_WEIGHTS.location*distance*distance;
    differences.push('Helyszín');
  }
  for(const [field,minimum,maximum,minLabel,maxLabel] of [['price','minPrice','maxPrice','Minimumár','Maximumár'],['rooms','minRooms','maxRooms','Minimum szobaszám','Maximum szobaszám'],['area','minArea','maxArea','Minimum alapterület','Maximum alapterület']]){
    const value=field==='rooms'?roomTotal(p):Number(p[field]);
    add(minimum,s[minimum]!=null&&Number(s[minimum])>0,(Number(s[minimum])-value)/(Number(s[minimum])>0?Number(s[minimum]):1),minLabel);
    add(maximum,s[maximum]!=null,Number(s[maximum])>0?(value-Number(s[maximum]))/Number(s[maximum]):value>Number(s[maximum])?1:0,maxLabel);
  }
  const actualCondition=conditionIndex(p.condition);
  add('condition',q.conditions.size,actualCondition<0||q.conditionMinimum<0?1:(q.conditionMinimum-actualCondition)/3,'Állapot');
  const floor=!knownFloor(p)?null:Number(p.floor);
  let floorLoss=q.floors.length?(floor==null?1:Math.min(...q.floors.map(wanted=>wanted===9&&floor>=9?0:Math.abs(wanted-floor)))/5):0;
  if(s.excludeTopFloor&&!belowTopFloor(p))floorLoss=Math.max(floorLoss,1);
  if(s.excludeGroundFloorAndBelow&&!aboveGroundFloor(p))floorLoss=Math.max(floorLoss,1);
  if(s.atticPreference&&(p.isAttic==null||p.isAttic!==(s.atticPreference==='only')))floorLoss=Math.max(floorLoss,1);
  add('floor',!q.house&&(q.floors.length||s.excludeTopFloor||s.excludeGroundFloorAndBelow||s.atticPreference),floorLoss,'Emelet');
  add('elevator',!q.house&&s.elevator,p.elevator?0:1,'Lift');
  add('balcony',!q.house&&s.balcony,p.balcony?0:1,'Erkély');
  add('airConditioning',s.airConditioning,p.airConditioning===true?0:1,'Légkondi');
  add('privateGarden',q.flat&&s.privateGarden,p.privateGarden===true?0:1,'Saját kert');
  add('building',q.buildings.size,categoryLoss(normalizeBuilding(p.building),q.buildings,BUILDING_OPTIONS),'Falazat');
  add('heatingType',q.heating.size,categoryLoss(normalizeHeating(p.heatingType),q.heating,HEATING_OPTIONS),'Fűtés típusa');
  const energyMinimum=energyIndex(s.minEnergyRating),energyActual=knownEnergyRating(p);
  add('minEnergyRating',energyMinimum>=0,energyActual<0?1:(energyMinimum-energyActual)/11,'Energetikai tanúsítvány');
  const age=CONSTRUCTION_AGE_OPTIONS.indexOf(canon(p.constructionAge,CONSTRUCTION_AGE_OPTIONS));
  add('constructionAge',q.ages.size,age<0?1:Math.min(...[...q.ages].map(value=>Math.abs(CONSTRUCTION_AGE_OPTIONS.indexOf(value)-age)))/4,'Építési kor');
  add('ceilingHeight',!!s.ceilingHeight,known(canon(p.ceilingHeight,CEILING_HEIGHT_OPTIONS),CEILING_HEIGHT_OPTIONS)&&canon(p.ceilingHeight,CEILING_HEIGHT_OPTIONS)===s.ceilingHeight?0:1,'Belmagasság');
  add('view',q.views.size,categoryLoss(canon(p.view,VIEW_OPTIONS),q.views,VIEW_OPTIONS),'Kilátás');
  const isExact=differences.length===0;
  const score=isExact?100:Math.min(99,Math.max(0,Math.round(100*Math.exp(-Math.sqrt(distanceSquared)))));
  return {eligible:true,isExact,score,reasons:!includeReasons?[]:isExact?['Megfelelő elhelyezkedés','A megadott árkereten belül','Megfelelő alapterület és szobaszám']:differences.map(label=>`${label}: eltérés a kereséstől`),
    distanceSquared,locationDistanceKm:exactLocation?0:locationDistanceKm,
    matchDetails:includeReasons?explainMatch(p,q,place,exactLocation,locationDistanceKm):[]};
}

const explanationNumber=new Intl.NumberFormat('hu-HU',{useGrouping:false,maximumFractionDigits:6});
const detailNumber=value=>explanationNumber.format(value);
const detailFloor=(value,bucket=false)=>value===-1?'Szuterén':value===0?'Földszint':value===0.5?'Magasföldszint':value>=9&&bucket?'9. emelet vagy afölötti':`${value}. emelet`;
const knownDetail=(value,options)=>options.includes(value)?value:'Nincs megadva';

/** Concrete requested/actual values, only built for cards that need presentation. */
function explainMatch(p,q,place,exactLocation,locationDistanceKm){
  const s=q.search,details=[];
  const add=(key,label,expected,actual,matches)=>details.push({key,label,expected,actual,matches});
  function bounds(key,label,actual,minimum,maximum,unit){
    const min=minimum!=null&&Number(minimum)>0,max=maximum!=null;
    if(!min&&!max)return;
    const expected=min&&max?`${detailNumber(minimum)}–${detailNumber(maximum)} ${unit}`
      :min?`legalább ${detailNumber(minimum)} ${unit}`:`legfeljebb ${detailNumber(maximum)} ${unit}`;
    add(key,label,expected,`${detailNumber(actual)} ${unit}`,(!min||actual>=minimum)&&(!max||actual<=maximum));
  }
  function category(key,label,actual,selected,options){
    if(!selected.size)return;
    const expected=options.filter(value=>selected.has(value));
    add(key,label,expected.length?expected.join(' vagy '):'Ismeretlen feltétel',knownDetail(actual,options),options.includes(actual)&&selected.has(actual));
  }
  const actualLocation=exactLocation?place.label:`${place.label} (kb. ${detailNumber(Number(locationDistanceKm.toFixed(1)))} km-re a keresett területtől)`;
  add('location','Helyszín',q.locationLabels.join(' vagy '),actualLocation,exactLocation);
  if(q.type)add('type','Ingatlantípus',s.type,p.type,true);
  bounds('price','Ár',Number(p.price),s.minPrice,s.maxPrice,'M Ft');
  bounds('rooms','Szobaszám',roomTotal(p),s.minRooms,s.maxRooms,'szoba');
  bounds('area','Alapterület',Number(p.area),s.minArea,s.maxArea,'m²');
  if(q.conditions.size){
    const actual=conditionIndex(p.condition),minimum=q.conditionMinimum;
    add('condition','Állapot',minimum>=0?`${CONDITION_OPTIONS[minimum]} vagy jobb`:'Ismeretlen feltétel',
      actual>=0?CONDITION_OPTIONS[actual]:'Nincs megadva',actual>=0&&minimum>=0&&actual>=minimum);
  }
  if(!q.house&&q.floors.length){
    const floor=!knownFloor(p)?null:Number(p.floor);
    add('floor','Emelet',q.floors.map(value=>detailFloor(value,true)).join(' vagy '),floor==null?'Nincs megadva':detailFloor(floor,p.floorIsUpperRange===true),
      floor!=null&&q.floors.some(value=>value===floor||value===9&&floor>=9));
  }
  if(!q.house&&s.elevator)add('elevator','Lift','Van lift',p.elevator?'Van lift':'Nincs lift',!!p.elevator);
  if(!q.house&&s.balcony)add('balcony','Erkély','Van erkély',p.balcony==null?'Nincs megadva':p.balcony===true?'Van erkély':'Nincs erkély',p.balcony===true);
  if(!q.house&&s.excludeTopFloor)add('excludeTopFloor','Legfelső emelet','Nem legfelső emelet',!knownTopFloor(p)?'Nincs megadva':belowTopFloor(p)?'Nem legfelső emelet':'Legfelső emelet',belowTopFloor(p));
  if(!q.house&&s.excludeGroundFloorAndBelow)add('excludeGroundFloorAndBelow','Földszint és szuterén','Földszint felett',knownFloor(p)?detailFloor(Number(p.floor),p.floorIsUpperRange===true):'Nincs megadva',aboveGroundFloor(p));
  if(!q.house&&s.atticPreference)add('atticPreference','Tetőtér',s.atticPreference==='only'?'Tetőtéri ingatlan':'Nem tetőtéri ingatlan',p.isAttic==null?'Nincs megadva':p.isAttic?'Tetőtéri ingatlan':'Nem tetőtéri ingatlan',p.isAttic!=null&&p.isAttic===(s.atticPreference==='only'));
  if(s.airConditioning)add('airConditioning','Légkondi','Van légkondi',p.airConditioning==null?'Nincs megadva':p.airConditioning===true?'Van légkondi':'Nincs légkondi',p.airConditioning===true);
  if(q.flat&&s.privateGarden)add('privateGarden','Saját kert','Van saját kert',p.privateGarden==null?'Nincs megadva':p.privateGarden===true?'Van saját kert':'Nincs saját kert',p.privateGarden===true);
  category('building','Falazat',normalizeBuilding(p.building),q.buildings,BUILDING_OPTIONS);
  category('heatingType','Fűtés típusa',normalizeHeating(p.heatingType),q.heating,HEATING_OPTIONS);
  const energyMinimum=energyIndex(s.minEnergyRating),energyActual=knownEnergyRating(p);
  if(energyMinimum>=0)add('minEnergyRating','Energetikai tanúsítvány',`${s.minEnergyRating} vagy jobb`,energyActual<0?'Nincs megadva':p.energyRating,energyActual>=energyMinimum);
  category('constructionAge','Építési kor',canon(p.constructionAge,CONSTRUCTION_AGE_OPTIONS),q.ages,CONSTRUCTION_AGE_OPTIONS);
  if(s.ceilingHeight){
    const actual=canon(p.ceilingHeight,CEILING_HEIGHT_OPTIONS);
    add('ceilingHeight','Belmagasság',s.ceilingHeight,knownDetail(actual,CEILING_HEIGHT_OPTIONS),CEILING_HEIGHT_OPTIONS.includes(actual)&&actual===s.ceilingHeight);
  }
  category('view','Kilátás',canon(p.view,VIEW_OPTIONS),q.views,VIEW_OPTIONS);
  return details;
}

/** Positive quality adjustment is capped at 25%; living size and price dominate. */
export function valueForMoney(p={}){
  const area=Number(p.area),price=Number(p.price);if(!(area>0)||!(price>0))return 0;
  const house=norm(p.type)==='HAZ',plot=house?Math.max(0,Number(p.lotArea)||0):0;
  let quality=Math.max(0,conditionIndex(p.condition))/3*.05;
  const building=normalizeBuilding(p.building);
  quality+=building==='Passzívház'?.02:valueBuildings.has(building)?.015:building==='Panel'?.01:known(building,BUILDING_OPTIONS)?.005:0;
  const age=CONSTRUCTION_AGE_OPTIONS.indexOf(canon(p.constructionAge,CONSTRUCTION_AGE_OPTIONS));quality+=age<0?0:(4-age)/4*.025;
  const view=canon(p.view,VIEW_OPTIONS);quality+=view==='Panorámás'?.015:view==='Kertre néző'?.01:view==='Udvari'?.005:0;
  const heating=normalizeHeating(p.heatingType);quality+=heating==='Hőszivattyú'?.025:valueHeating.has(heating)?.015:known(heating,HEATING_OPTIONS)&&heating!=='Nincs fűtés'?.005:0;
  quality+=p.insulated===true?.015:0;
  const energy=norm(p.energyRating);quality+=/^(AA?|A[1-4])\+{0,3}$/.test(energy)?.02:/^BB?\+{0,3}$/.test(energy)?.015:/^CC?\+{0,3}$/.test(energy)?.005:0;
  quality+=p.airConditioning===true?.01:0;quality+=p.solarPanels===true?.015:0;
  quality+=norm(p.type)==='LAKAS'&&p.privateGarden===true?.015:0;
  const parking=(Array.isArray(p.parkingTypes)?p.parkingTypes:[p.parkingType]).map(value=>canon(value,parkingOptions));
  quality+=parking.some(value=>garageTypes.has(value))?.015:parking.some(value=>drivewayTypes.has(value))?.01:0;
  quality+=canon(p.ceilingHeight,CEILING_HEIGHT_OPTIONS)==='3 m feletti'?.005:0;
  quality+=!house&&knownFloor(p)&&Number(p.floor)>=0&&Number(p.floor)<=3?.005:0;
  quality+=!house&&p.balcony?.01:0;quality+=!house&&p.elevator?.01:0;
  quality+=Math.min(1,Math.max(0,roomTotal(p)||0)/(area/25))*.005;
  return (area+.04*Math.min(plot,5*area))/price*(1+Math.min(.25,quality));
}

function specificityOf(q){
  const s=q.search;let selected=0,total=8;
  const coverage=q.cities.size+q.districtIds.size/23+q.neighborhoodIds.size/100+q.streetIds.size/10000;
  selected+=coverage>0?8/(1+Math.log2(1+coverage)):0;
  function add(weight,strength){total+=weight;selected+=weight*clamp(strength);}
  for(const [minimum,maximum] of [['minPrice','maxPrice'],['minArea','maxArea'],['minRooms','maxRooms']]){
    const min=s[minimum]!=null&&Number(s[minimum])>0,max=s[maximum]!=null;
    const strength=min&&max?.5+.5*clamp(Number(s[maximum])>0?Number(s[minimum])/Number(s[maximum]):1):.5;
    add(FOCUS_WEIGHTS[minimum],min?strength:0);add(FOCUS_WEIGHTS[maximum],max?strength:0);
  }
  const category=(count,choices)=>count?1/Math.sqrt(Math.min(count,choices)):0;
  add(FOCUS_WEIGHTS.condition,q.conditionMinimum==null?0:(q.conditionMinimum+1)/4);
  add(FOCUS_WEIGHTS.building,category(q.buildings.size,BUILDING_OPTIONS.length));
  add(FOCUS_WEIGHTS.heatingType,category(q.heating.size,HEATING_OPTIONS.length));
  const energyMinimum=energyIndex(s.minEnergyRating);add(FOCUS_WEIGHTS.minEnergyRating,energyMinimum<0?0:(energyMinimum+1)/12);
  add(FOCUS_WEIGHTS.constructionAge,category(q.ages.size,CONSTRUCTION_AGE_OPTIONS.length));
  add(FOCUS_WEIGHTS.view,category(q.views.size,VIEW_OPTIONS.length));
  add(FOCUS_WEIGHTS.ceilingHeight,s.ceilingHeight?1:0);
  add(FOCUS_WEIGHTS.airConditioning,s.airConditioning?1:0);
  if(q.flat)add(FOCUS_WEIGHTS.privateGarden,s.privateGarden?1:0);
  if(!q.house){add(FOCUS_WEIGHTS.floor,Math.max(category(q.floors.length,FLOOR_OPTIONS.length),s.excludeTopFloor||s.excludeGroundFloorAndBelow||s.atticPreference?1:0));add(FOCUS_WEIGHTS.elevator,s.elevator?1:0);add(FOCUS_WEIGHTS.balcony,s.balcony?1:0);}
  return Math.max(0,Math.min(100,Math.round(100*selected/total)));
}
export function searchSpecificity(search,options){return search?.[compiledMarker]?search.specificity:prepareSearch(search,options).specificity;}
