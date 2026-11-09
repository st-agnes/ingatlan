/** Public, fictional fixtures for the explicitly identified Google Cloud test site. */
export const DEMO_PASSWORD = 'OtthonraDemo2026!';

const LEGACY_USERS = [
  {key: 'anna', name: 'Kovács Anna', email: 'anna@otthonra.local', phone: '+36 30 555 0101', active: {kind: 'search', key: 'anna-budapest'}},
  {key: 'peter', name: 'Nagy Péter', email: 'peter@otthonra.local', phone: '+36 30 555 0102', active: {kind: 'property', key: 'peter-pozsonyi'}},
  {key: 'eszter', name: 'Szabó Eszter', email: 'eszter@otthonra.local', phone: '+36 30 555 0103', active: {kind: 'search', key: 'eszter-buda'}}
];

const photos = [
  'https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=1400&q=85',
  'https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?auto=format&fit=crop&w=1400&q=85'
];
const fictional = 'Kitalált tesztadat, nem valódi ingatlanhirdetés. ';
const propertyDefaults = {
  neighborhood: '', address: '', description: fictional, type: 'Lakás', floor: 1,
  condition: 'Jó állapotú', building: 'Tégla', balcony: false, elevator: false,
  images: photos, archived: false, lotArea: null
};
const searchDefaults = {
  districts: [], description: fictional, type: 'Lakás', minPrice: null, maxPrice: null,
  minArea: null, maxArea: null, minRooms: null, maxRooms: null, balcony: false,
  elevator: false, moveIn: '3 hónapon belül', financing: 'Tesztként megadott saját forrás', archived: false
};

const LEGACY_FIXTURES = [
  {
    key: 'peter-pozsonyi', owner: 'peter', kind: 'property', input: {
      ...propertyDefaults,
      title: 'Teszt · Napfényes otthon a Pozsonyi útnál', city: 'Budapest', district: 'XIII.',
      locationId: 'district:Budapest:13', neighborhood: 'Újlipótváros',
      price: 79_900_000, area: 68, rooms: 3, floor: 3, condition: 'Felújított', balcony: true, elevator: true,
      description: fictional + 'Világos, háromszobás, erkélyes lakás egy liftes házban. A példa Anna budapesti keresésének megfelel.'
    }
  },
  {
    key: 'peter-rozsadomb', owner: 'peter', kind: 'property', input: {
      ...propertyDefaults,
      title: 'Teszt · Zöldre néző lakás a Rózsadombon', city: 'Budapest', district: 'II.',
      locationId: 'district:Budapest:2', neighborhood: 'Rózsadomb',
      price: 92_000_000, area: 74, rooms: 3, balcony: true,
      description: fictional + 'Csendes környezetet, tágas nappalit és saját erkélyt bemutató minta. Eszter budai kereséséhez is illeszkedik.'
    }
  },
  {
    key: 'peter-debrecen', owner: 'peter', kind: 'property', input: {
      ...propertyDefaults,
      title: 'Teszt · Háromszobás lakás Debrecenben', city: 'Debrecen', district: '',
      locationId: 'city:Debrecen', neighborhood: 'Nagyerdő környéke',
      price: 64_900_000, area: 62, rooms: 3, floor: 2, balcony: true,
      description: fictional + 'A több településre megadott keresési igény kipróbálására szolgáló lakás, amely Anna debreceni keresésének megfelel.'
    }
  },
  {
    key: 'anna-solymar-house', owner: 'anna', kind: 'property', input: {
      ...propertyDefaults,
      title: 'Teszt · Kertes családi ház Solymáron', city: 'Solymár', district: '',
      locationId: 'city:Solymár', type: 'Ház', floor: null,
      price: 139_900_000, area: 135, rooms: 5, lotArea: 720,
      description: fictional + 'Ötszobás ház kerttel és megadott telekmérettel. Péter agglomerációs keresésével kipróbálható az eladói és keresői szerep váltása.'
    }
  },
  {
    key: 'eszter-pilisvorosvar-house', owner: 'eszter', kind: 'property', input: {
      ...propertyDefaults,
      title: 'Teszt · Családi ház Pilisvörösváron', city: 'Pilisvörösvár', district: '',
      locationId: 'city:Pilisvörösvár', type: 'Ház', floor: null,
      price: 119_900_000, area: 120, rooms: 4, lotArea: 650,
      description: fictional + 'Négyszobás családi ház tágas telekkel. A minta a több települést elfogadó házkereséshez tartozik.'
    }
  },
  {
    key: 'eszter-ujlipotvaros', owner: 'eszter', kind: 'property', input: {
      ...propertyDefaults,
      title: 'Teszt · Kétszobás erkélyes lakás Újlipótvárosban', city: 'Budapest', district: 'XIII.',
      locationId: 'district:Budapest:13', neighborhood: 'Újlipótváros',
      price: 69_900_000, area: 52, rooms: 2, floor: 4, balcony: true, elevator: true,
      description: fictional + 'Kompakt, erkélyes lakás liftes házban. Anna budapesti keresésében újabb választható ajánlatként jelenhet meg.'
    }
  },
  {
    key: 'anna-budapest', owner: 'anna', kind: 'search', input: {
      ...searchDefaults,
      title: 'Teszt · Világos otthont keresek Budapesten', city: 'Budapest', districts: ['XIII.', 'II.'],
      locationIds: ['district:Budapest:13', 'district:Budapest:2'], maxPrice: 100_000_000,
      minArea: 45, maxArea: null, minRooms: 2, maxRooms: null,
      description: fictional + 'Két kerületben keresett lakás. A minimumár, a maximum alapterület és a maximum szobaszám szándékosan nincs korlátozva.'
    }
  },
  {
    key: 'anna-debrecen', owner: 'anna', kind: 'search', input: {
      ...searchDefaults,
      title: 'Teszt · Debrecen és környéke is érdekel', city: 'Debrecen',
      locationIds: ['city:Debrecen', 'city:Hajdúszoboszló', 'city:Hajdúsámson'],
      maxPrice: 80_000_000, minArea: 50, maxArea: 95, minRooms: 2,
      description: fictional + 'Debrecenben, Hajdúszoboszlón vagy Hajdúsámsonban keresett otthon. Bármelyik felsorolt település megfelelő.'
    }
  },
  {
    key: 'peter-house', owner: 'peter', kind: 'search', input: {
      ...searchDefaults,
      title: 'Teszt · Kertes házat keresek az agglomerációban', city: 'Solymár', type: 'Ház',
      locationIds: ['city:Solymár', 'city:Pilisvörösvár'],
      maxPrice: 150_000_000, minArea: 105, minRooms: 4,
      description: fictional + 'Családi ház keresése Solymáron vagy Pilisvörösváron. A megadott települések bármelyike megfelel, a felső méret- és szobakorlát nyitott.'
    }
  },
  {
    key: 'eszter-buda', owner: 'eszter', kind: 'search', input: {
      ...searchDefaults,
      title: 'Teszt · Erkélyes lakást keresek Budán', city: 'Budapest', districts: ['II.'],
      locationIds: ['district:Budapest:2'], maxPrice: 110_000_000,
      minArea: 60, maxArea: 100, minRooms: 2, maxRooms: 4, balcony: true,
      description: fictional + 'Erkélyes, legalább két szobás lakás a második kerületben. A rózsadombi tesztlakással összepárosítható.'
    }
  }
];


/** Stable batches add new counterparties without resetting any existing decision. */
export const DEFAULT_BATCH = 'alap';
const extraUsers = [
  {key:'daniel-kozvetito', name:'Varga Dániel', email:'daniel.kozvetito', accountType:'agent'},
  {key:'kata-kozvetito', name:'Kiss Kata', email:'kata.kozvetito', accountType:'agent'},
  {key:'gabor-kozvetito', name:'Farkas Gábor', email:'gabor.kozvetito', accountType:'agent'},
  {key:'reka', name:'Tóth Réka', email:'reka', accountType:'private'},
  {key:'bence', name:'Németh Bence', email:'bence', accountType:'private'},
  {key:'julia', name:'Molnár Júlia', email:'julia', accountType:'private'},
  {key:'marton', name:'Varga Márton', email:'marton', accountType:'private'},
  {key:'lilla', name:'Szabó Lilla', email:'lilla', accountType:'private'},
  {key:'balazs', name:'Kiss Balázs', email:'balazs', accountType:'private'}
];
const copy = value => JSON.parse(JSON.stringify(value));

const propertyExtras = (slot, ownerIndex) => ({
  condition:['Jó','Új/felújított','Átlagos','Felújítandó'][(slot + ownerIndex) % 4],
  building:(slot + ownerIndex) % 3 === 0 ? 'Panel' : 'Tégla',
  constructionAge:['10 évnél fiatalabb','10–30 év közötti','31–40 év közötti','41–50 év közötti','Több mint 50 éves'][(slot + ownerIndex) % 5],
  view:['Kertre néző','Utcai','Udvari','Panorámás'][(slot + ownerIndex) % 4],
  ceilingHeight:slot % 2 ? '3 m feletti' : '3 m alatti',
  heatingType:['Gázkazán','Távfűtés','Hőszivattyú','Elektromos fűtés','Nincs fűtés'][(slot + ownerIndex) % 5],
  secondaryHeatingType:slot % 3 === 0 ? 'Klíma' : '',
  insulated:slot % 3 === 0 ? null : slot % 2 === 0,
  energyRating:slot % 2 ? 'BB' : 'A+',
  airConditioning:slot % 2 === 0, solarPanels:slot % 3 === 0,
  parkingTypes:slot % 2 ? ['Garázs','Udvari beálló'] : ['Utcai parkolás']
});

// County-specific examples supplement, rather than replace, the original matching scenarios.
// Keep these exact town names aligned with the shared KSH region/location catalogues.
const regionalPlaces = [
  ['HU110', ['district:Budapest:13','district:Budapest:9','district:Budapest:11']],
  ['HU331', ['Kecskemét','Baja','Kiskunfélegyháza']],
  ['HU231', ['Pécs','Komló','Mohács']],
  ['HU332', ['Békéscsaba','Gyula','Orosháza']],
  ['HU311', ['Miskolc','Kazincbarcika','Tiszaújváros']],
  ['HU333', ['Szeged','Hódmezővásárhely','Makó']],
  ['HU211', ['Székesfehérvár','Dunaújváros','Mór']],
  ['HU221', ['Győr','Sopron','Mosonmagyaróvár']],
  ['HU321', ['Debrecen','Hajdúszoboszló','Hajdúsámson']],
  ['HU312', ['Eger','Gyöngyös','Hatvan']],
  ['HU322', ['Szolnok','Jászberény','Karcag']],
  ['HU212', ['Tatabánya','Esztergom','Tata']],
  ['HU313', ['Salgótarján','Balassagyarmat','Pásztó']],
  ['HU120', ['Érd','Solymár','Pilisvörösvár']],
  ['HU232', ['Kaposvár','Siófok','Marcali']],
  ['HU323', ['Nyíregyháza','Mátészalka','Kisvárda']],
  ['HU233', ['Szekszárd','Dombóvár','Paks']],
  ['HU222', ['Szombathely','Kőszeg','Sárvár']],
  ['HU213', ['Veszprém','Pápa','Ajka']],
  ['HU223', ['Zalaegerszeg','Nagykanizsa','Keszthely']]
];
const regionalProfiles = [
  {type:'Lakás', key:'lakas', prices:[20,34,52,78,125,205], budgets:[25,40,60,90,145,230],
    areas:[24,38,56,83,118,162], rooms:[1,1.5,2.5,3,4,5.5],
    labels:['Kompakt garzon','Első saját otthon','Másfél szobánál nagyobb lakás','Tágas családi lakás','Nagy alapterületű lakás','Többgenerációs lakás']},
  {type:'Ház', key:'haz', prices:[28,46,73,110,165,245], budgets:[35,55,85,130,190,280],
    areas:[48,72,104,145,205,280], rooms:[1.5,2.5,3,4.5,6,7.5],
    labels:['Kis kertes ház','Kompakt családi ház','Családi ház kerttel','Tágas kertes otthon','Nagycsaládos otthon','Többgenerációs családi ház']}
];

export function createDemoCatalog(batch = DEFAULT_BATCH) {
  if (typeof batch !== 'string' || !/^[a-z0-9][a-z0-9-]{0,31}$/.test(batch)) {
    throw new Error('A tesztadatcsomag neve 1–32 kisbetűs angol betű, szám vagy kötőjel legyen; betűvel vagy számmal kezdődjön.');
  }
  const keySuffix = batch === DEFAULT_BATCH ? '' : `--${batch}`;
  const titleSuffix = batch === DEFAULT_BATCH ? '' : ` · ${batch}`;
  const users = LEGACY_USERS.map(user => ({...copy(user), accountType:'private'}));
  const fixtures = copy(LEGACY_FIXTURES);
  for (const [ownerIndex, definition] of extraUsers.entries()) {
    const owner = definition.key + keySuffix;
    const firstProperty = `${owner}-budapest-13-1`;
    const firstSearch = `${owner}-budapest-search-1`;
    const kind = definition.accountType === 'agent' || ownerIndex % 2 === 0 ? 'search' : 'property';
    users.push({
      key:owner, name:definition.name + titleSuffix,
      email:`${definition.email}${batch === DEFAULT_BATCH ? '' : `+${batch}`}@otthonra.local`,
      phone:`+36 30 555 ${String(111 + ownerIndex).padStart(4,'0')}`,
      accountType:definition.accountType,
      active:{kind, key:kind === 'search' ? firstSearch : firstProperty}
    });
    const add = (key, kind, input) => fixtures.push({key:`${owner}-${key}`, owner, kind, input});
    const extras = slot => propertyExtras(slot, ownerIndex);
    for (const district of [13,2]) {
      for (let index = 0; index < 4; index++) {
        const wholeRooms = 2 + index % 2, halfRooms = index % 2;
        add(`budapest-${district}-${index + 1}`, 'property', {
          ...copy(propertyDefaults), ...extras(index + (district === 2 ? 4 : 0)),
          title:`Teszt · ${district === 13 ? 'Újlipótvárosi' : 'Budai'} otthon ${ownerIndex + 1}/${index + 1}${titleSuffix}`,
          city:'Budapest', district:district === 13 ? 'XIII.' : 'II.', locationId:`district:Budapest:${district}`,
          neighborhood:district === 13 ? 'Újlipótváros' : 'Rózsadomb',
          price:(district === 13 ? 65_000_000 : 79_000_000) + index * 3_000_000 + ownerIndex * 500_000,
          area:(district === 13 ? 60 : 66) + index * 4 + ownerIndex,
          wholeRooms, halfRooms, rooms:wholeRooms + halfRooms / 2, floor:index + 1,
          balcony:true, elevator:true,
          description:fictional + 'Változatos fűtéssel, parkolási lehetőségekkel és külön megadott egész- és félszobákkal kipróbálható budapesti otthon.'
        });
      }
    }
    for (const [index,city] of ['Debrecen','Hajdúsámson'].entries()) {
      add(`debrecen-${index + 1}`, 'property', {
        ...copy(propertyDefaults), ...extras(index + 8),
        title:`Teszt · ${city} környéki lakás ${ownerIndex + 1}${titleSuffix}`,
        city, district:'', locationId:`city:${city}`, neighborhood:city === 'Debrecen' ? 'Nagyerdő környéke' : 'Kertváros',
        price:54_000_000 + ownerIndex * 1_000_000 + index * 2_000_000,
        area:58 + ownerIndex + index * 3, wholeRooms:3, halfRooms:0, rooms:3, floor:index + 1,
        balcony:true, elevator:index === 0,
        description:fictional + 'A város és környéke csoport, illetve a több településes keresés kipróbálásához készült lakás.'
      });
    }
    for (const [index,city] of ['Solymár','Pilisvörösvár'].entries()) {
      add(`house-${index + 1}`, 'property', {
        ...copy(propertyDefaults), ...extras(index + 10), building:'Tégla', type:'Ház', floor:null,
        title:`Teszt · Kertes ház ${city} településen ${ownerIndex + 1}${titleSuffix}`,
        city, district:'', locationId:`city:${city}`,
        price:112_000_000 + ownerIndex * 2_000_000 + index * 3_000_000,
        area:114 + ownerIndex * 2 + index * 5, lotArea:610 + ownerIndex * 20 + index * 35,
        wholeRooms:4 + index, halfRooms:0, rooms:4 + index, balcony:false, elevator:false,
        description:fictional + 'Telekmérettel megadott családi ház. Az agglomerációs keresésekben sok új, korábban nem értékelt párost biztosít.'
      });
    }
    for (let index = 0; index < 4; index++) {
      const locationIds = [
        ['district:Budapest:13','district:Budapest:2'], ['city:Budapest'],
        ['area:Budapest'], ['district:Budapest:13','district:Budapest:2','city:Solymár']
      ][index];
      add(`budapest-search-${index + 1}`, 'search', {
        ...copy(searchDefaults), title:`Teszt · Budapesti otthont keresek ${ownerIndex + 1}/${index + 1}${titleSuffix}`,
        city:'Budapest', districts:index === 0 ? ['XIII.','II.'] : [], locationIds,
        maxPrice:110_000_000, minArea:45, maxArea:110, minRooms:2, maxRooms:4,
        conditions:index % 2 ? [] : ['Jó','Új/felújított','Átlagos','Felújítandó'],
        buildings:index % 2 ? [] : ['Tégla','Panel'],
        description:fictional + 'A budapesti kerületeket, a teljes várost vagy a városkörnyéki csoportot elfogadó keresés. Péter és a többi felhasználó budapesti lakásai is megfelelhetnek.'
      });
    }
    for (let index = 0; index < 2; index++) {
      add(`buda-search-${index + 1}`, 'search', {
        ...copy(searchDefaults), title:`Teszt · Erkélyes budai lakást keresek ${ownerIndex + 1}/${index + 1}${titleSuffix}`,
        city:'Budapest', districts:['II.'], locationIds:index ? ['district:Budapest:2','district:Budapest:11'] : ['district:Budapest:2'],
        maxPrice:110_000_000, minArea:60, maxArea:100, minRooms:2, maxRooms:4, balcony:true,
        description:fictional + 'Erkélyes budai ingatlanra nyitott keresés, amely a korábbi rózsadombi mintával is összekapcsolható.'
      });
      add(`debrecen-search-${index + 1}`, 'search', {
        ...copy(searchDefaults), title:`Teszt · Debreceni térségben keresek ${ownerIndex + 1}/${index + 1}${titleSuffix}`,
        city:'Debrecen', locationIds:index ? ['city:Debrecen','city:Hajdúsámson','city:Hajdúszoboszló'] : ['area:Debrecen'],
        maxPrice:80_000_000, minArea:50, maxArea:95, minRooms:2, maxRooms:4,
        description:fictional + 'Debrecen és a környező települések lakásaihoz készült keresés, többféle helyszínválasztással.'
      });
    }
    for (let index = 0; index < 4; index++) {
      add(`house-search-${index + 1}`, 'search', {
        ...copy(searchDefaults), title:`Teszt · Agglomerációs családi házat keresek ${ownerIndex + 1}/${index + 1}${titleSuffix}`,
        type:'Ház', city:'Solymár', locationIds:index % 2 ? ['area:Budapest'] : ['city:Solymár','city:Pilisvörösvár'],
        maxPrice:150_000_000, minArea:105, maxArea:180, minRooms:4, maxRooms:7,
        description:fictional + 'Solymári vagy pilisvörösvári családi házra keresett új párosítás, az eredeti házmintákhoz is megfelelő feltételekkel.'
      });
    }
  }
  let pairIndex = 0;
  for (const [regionId, places] of regionalPlaces) {
    for (const profile of regionalProfiles) {
      for (let index = 0; index < profile.prices.length; index++, pairIndex++) {
        const propertyOwnerIndex = pairIndex % extraUsers.length;
        const owner = extraUsers[propertyOwnerIndex].key + keySuffix;
        const searchOwner = extraUsers[(propertyOwnerIndex + 4) % extraUsers.length].key + keySuffix;
        const pairKey = `regional-${regionId.toLowerCase()}-${profile.key}-${index + 1}${keySuffix}`;
        const place = places[index % places.length];
        const locationId = place.startsWith('district:') ? place : `city:${place}`;
        const district = place.startsWith('district:') ? ({13:'XIII.',9:'IX.',11:'XI.'})[place.split(':')[2]] : '';
        const city = district ? 'Budapest' : place;
        const price = profile.prices[index] * 1_000_000;
        const area = profile.areas[index], rooms = profile.rooms[index];
        const house = profile.type === 'Ház';
        const attributes = propertyExtras(index + pairIndex, propertyOwnerIndex);
        const wholeRooms = Math.floor(rooms), halfRooms = (rooms - wholeRooms) * 2;
        fixtures.push({key:`${pairKey}-property`, owner, kind:'property', input:{
          ...copy(propertyDefaults), ...attributes,
          title:`Teszt · ${profile.labels[index]} · ${city}${titleSuffix}`,
          city, district, locationId, type:profile.type, price, area, rooms, wholeRooms, halfRooms,
          building:house ? 'Tégla' : attributes.building,
          floor:house ? null : index % 6,
          lotArea:house ? 240 + index * 215 : null,
          balcony:!house && index % 2 === 1, elevator:!house && index >= 3,
          description:fictional + 'A régiós tesztkínálat különböző árú, méretű és szobaszámú otthonainak egyike. A hozzá illeszkedő keresés másik felhasználóhoz tartozik.'
        }});
        fixtures.push({key:`${pairKey}-search`, owner:searchOwner, kind:'search', input:{
          ...copy(searchDefaults),
          title:`Teszt · ${profile.labels[index]} keresése · ${city}${titleSuffix}`,
          city, districts:district ? [district] : [], type:profile.type,
          locationIds:index % 2 ? places.map(value=>value.startsWith('district:') ? value : `city:${value}`) : [locationId],
          minPrice:index % 3 === 0 ? null : Math.max(1,profile.prices[index] - (house ? 12 : 8)) * 1_000_000,
          maxPrice:profile.budgets[index] * 1_000_000,
          minArea:Math.max(15,area - (house ? 12 : 8)),
          maxArea:index % 3 === 2 ? null : area + (house ? 25 : 16),
          minRooms:Math.max(1,rooms - 0.5), maxRooms:index % 2 ? null : rooms + 1,
          conditions:index % 3 === 0 ? [attributes.condition] : [],
          heatingTypes:index % 3 === 1 ? [attributes.heatingType] : [],
          description:fictional + 'Önálló régiós keresési példa változatos költségkerettel, méret- és szobaigénnyel. A nyitott felső korlátok és a több településes keresés is kipróbálható.'
        }});
      }
    }
  }
  return {users, fixtures};
}

const defaultCatalog = createDemoCatalog();
export const DEMO_USERS = defaultCatalog.users;
export const DEMO_FIXTURES = defaultCatalog.fixtures;
