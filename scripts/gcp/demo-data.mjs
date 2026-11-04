/** Public, fictional fixtures for the explicitly identified Google Cloud test site. */
export const DEMO_PASSWORD = 'OtthonraDemo2026!';

export const DEMO_USERS = [
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

export const DEMO_FIXTURES = [
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
