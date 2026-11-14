# Székesfehérvár és Nyíregyháza – következő gyűjtési kör

**62 forrásalakzat: Székesfehérvár 43, Nyíregyháza 19.** A korábbi `50988ce` mentéshez képest 57 új normalizált település–név pár, és 39 korábbi tartalékkör neve kap térképi alapú alternatívát. Ezek bemeneti adatok; az országos összevonás választja ki az azonos névhez tartozó legjobb változatot.

## Tartalom

- `features.geojson`: a négy alábbi csomag összefoglaló állománya, WGS84-koordinátákkal.
- `fehervar-native-features.geojson`: 28 alakzat 22 valódi, zárt, színezett PDF-útvonalból. Az önkormányzat 2021-es örökségvédelmi hatástanulmányának 27. oldala tíz fő városrészt, azok külterületeit és kisebb beépített alkotórészeit ábrázolja. A kisebb és tágabb egységek külön neveken, szándékosan átfedve megmaradnak.
- `street-block-features.geojson`: 24 kis lakóterület becslése tényleges utca-, vasút- és vízvonalakból. Részletes magyarázat: `STREET-BLOCKS.md`.
- `fehervar-subarea-features.geojson`: további 7 hely becslése a nyomtatott városrészhatáron belüli, tényleges főutak/vasutak/vízvonalak által bezárt területekkel.
- `nyir-character-features.geojson`: Nyírjes és Mohosbokor látható beépített/vidékies felszíne a 2017-es önkormányzati karaktertérképről, valamint a térképen külön kategóriaként szereplő `Bokortanyák` területcsoport.

## Pontosság és forrás

A fehérvári útvonalak tényleges gépi PDF-poligonok. Elhelyezésük a teljes önkormányzati térkép és az OSM településhatár EOV-kiterjedésének illesztése; nem független pontosságmérés. A fehérvári részterületek és a kis lakótelepi utcacellák belső határai következtetések, nem nyomtatott teljes városrészhatárok.

A nyíregyházi karaktertérképnél a tényleges színezett felszíneket raszteres színmaszk adja, két képpontos réstömítéssel és egy képpontos egyszerűsítéssel. A területet a névponthoz rendeljük, nem a névpontból készítjük el. A `Bokortanyák` a nyomtatott kategória széttagolt felszíneinek uniója, nem minden tanya összes szántóföldje.

**Kör, Voronoi-hálózat, pont körüli puffer és konvex burok nem készült.** A különböző nevű felosztások átfedése megengedett. Egy teljes szülőterület tagjait nem tesszük meg automatikusan a teljes szülő szinonimájává.

A két teljes forrás-PDF, a nyíregyházi eredeti kép, a fehérvári natív képpontútvonalak, az elhelyezési adatok, 14 817 OSM forrásvonal, 126 névpont és a két településhatár itt megmaradnak. A forrás URL-je, oldalszáma és SHA-256-a az egyes kimenetekben található. A nyilvánosan elérhető önkormányzati dokumentumokhoz külön újrafelhasználási licencet nem állapítottunk meg; az OSM-rétegek ODbL-1.0 adatok, © OpenStreetMap contributors.

## Újraépítés

Python-függőségek: `shapely`, `pyproj`, `osmium`, `numpy`, `scipy`, `Pillow`, `PyMuPDF`. A már megőrzött forrásokkal hálózati letöltés és az országos PBF nélkül:

```sh
python3 data/neighborhoods/expansion-20261114-next/fehervar-nyiregyhaza/extract-street-blocks.py --saved-sources
python3 data/neighborhoods/expansion-20261114-next/fehervar-nyiregyhaza/extract-fehervar-native.py
python3 data/neighborhoods/expansion-20261114-next/fehervar-nyiregyhaza/extract-fehervar-subareas.py
python3 data/neighborhoods/expansion-20261114-next/fehervar-nyiregyhaza/extract-nyir-character.py
python3 data/neighborhoods/expansion-20261114-next/fehervar-nyiregyhaza/combine.py
```

Az utcacellák kiválasztását a `street-block-selection.json` rögzíti, így az újabb országos katalógusba kerülésük nem tünteti el őket újraépítéskor. Az összesítés nem állít országos vagy teljes városi lefedettséget.
