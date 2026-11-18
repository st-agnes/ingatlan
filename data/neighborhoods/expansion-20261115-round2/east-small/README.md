# Keleti kisebb települések – 2026. november 15., második kör

**26 új névhez 26 térképi alapú becsült keresési terület:** Hosszúpályi 8, Monostorpályi 5, Mátészalka 7, Orosháza 6. Mindegyik `estimated: true`, `lowConfidence: true`. A 26 elemű kiinduló név szerinti hiánylistát feldolgoztuk; ez nem teljes városi területi vagy hivatalos városrészhatár-lefedettség.

## A kiválasztás

- **14 fizikai úthálózati cella:** tényleges utcák, külterületi utak, földutak, vasutak és vízfolyások által bezárt terület. A helynév és a cella összerendelése következtetés. A külterületi neveknél a földutakat is bevontuk, ezért a keresési terület a tanya környezetét és a mezőgazdasági kerteket is lefedheti. A városi lakótelepeknél összefüggő utcaterületet választottunk; egy ilyen cella a tágabb történeti név csak egy részét is jelentheti.
- **6 tényleges forráspoligon vagy eredeti multipoligon-rész:** Hosszúgaz és Szalmás a névvel jelölt teljes tanyaudvar, Liliom a névvel jelölt teljes tanyatelek, Üveggyár a névvel jelölt teljes gyárterület. Mátészalkán a nyugati iparterület és az ipari park két különálló, eredeti ipari poligon-rész. Ezek határát nem a névpontból állítottuk elő. A rövid helynév hozzárendelése továbbra is becslés; a tanyák összes történeti szántóföldje nincs megállapítva. Hosszúgaz és Szalmás pontja az elnevezett forrástelek mellett található, ezért nem kell a poligonba esnie.
- **6 durva kézi térképi becslés:** Hosszúpályi Szőlőskertek; Orosháza Belváros; Mátészalka Északi lakótelep, Keleti lakótelep, Cinevég és Fogarassy-tanya. A tényleges utcák, beépített területszélek, erdő- és mezőgazdasági átmenetek alapján tágabb helyi keresési terület készült. A csúcsok és az egyedi indoklás a `selection.json` fájlban megmaradnak.

**Kör, pontpuffer, pontból képzett téglalap, Voronoi és konvex burok nem készült.** A forrás térképi poligonok szögletes oldalai vagy úthálózati cellák ettől függetlenül lehetnek közel egyenesek. Különböző történeti/helyi felosztások átfedése megengedett. Az azonos szülőalakzatban levő neveket nem tettük egymás szinonimájává.

## Különösen hasznos helyi bizonyítékok

Orosháza önkormányzata a helyi közösségi projekt oldalán kilenc utca felsorolásával leírja Belváros határát. A forrás szerinti utcák és a tényleges OSM-csomópontok alapján durva nyomvonal készült. A szövegben megadott nevek a jelenlegi térképen három helyen nem kapcsolódnak pontosan; ezek rövid összekötése és az utcagörbék általánosítása becslés. Az önkormányzati TAK 47. oldali szövege mind a négy gyűjtött lakótelep nevét külön felsorolja.

Hosszúpályin és Monostorpályin a névvel jelölt tanyaterületek és külterületi útnevek erősítik a helyazonosítást. Tejfeles történeti szőlőterületként is szerepel a helyi borkultúráról szóló 2001-es tanulmányban; ez a név jellegét támogatja, nem a becsült határt.

Mátészalkán az ipari forrás-multipoligon északi és déli része térben különálló. A rövid helynevek hozzárendelése mindkét esetben becsült, az egész szülőalakzatot nem másoltuk két eltérő név alá. Fogarassy-tanya történeti keresési területében ma ipari betonelem-/betonüzemi parcellák is szerepelnek; az elnevezés nem a vállalkozások jelenlegi művelési ágának állítása.

## Tartalom és újraépítés

- `features.geojson`: az importálható 26 alakzat WGS84-ben.
- `source-areas.geojson`: 1528 valódi helyi OSM területalakzat, változat- és forráshivatkozással.
- `source-lines.geojson`: 8442 tényleges út-, vasút- és vízvonal.
- `source-labels.geojson`, `source-municipalities.geojson`: a nevek és településhatárok megőrzött forrásai.
- `targets.json`: a kiinduló név szerinti lista; `selection.json`: a befagyasztott választások és indoklások.
- `candidate-cells.geojson`: a mentett fizikai hálózatból képzett cellák; csak a kiválasztott 14 kerül a fő rétegbe. A `candidate-footprint-cells.geojson` további, fel nem használt diagnosztikai változat.
- `*-context.png`: a gyűjtéskor átnézett fizikai térképek. A képek szemléltetők, nem önálló hivatalos városrészhatárok.
- `source-evidence.json`, `summary.json`, `validation.json`, `unresolved.json`: eredet, ellenőrzés és korlátok.
- `alias-proposals.json`: üres; új névazonosságot nem állapítottunk meg.

A fő réteg kizárólag az itt mentett állományokból, hálózat és országos PBF nélkül újraépíthető:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/east-small/build.py
```

A cellák újraszámítása szintén hálózat nélkül:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/east-small/analyze.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/east-small/build.py
```

Függőségek: `shapely`, `pyproj`; az opcionális PBF-kivonóhoz `osmium`, a kontextusképekhez `Pillow`. A `select.py` a befagyasztott választásokat állítja elő. A forrás-PBF SHA-256-a minden alakzatban megmarad. A központilag újonnan letöltött helyi PDF-ek külön a kör közös letöltési archívumában maradnak; a fő geometriák újraépítése nem függ tőlük.

Ellenőrzés: mind a 26 alakzat érvényes, nem üres Polygon/MultiPolygon és a megfelelő forrás-településhatáron belül van; nincs kettős település–név pár. Két jelölt forráspoligon határát a településhatár levágta. A név szerinti feldolgozás nem jelenti a tágabb történeti nevek minden részének bizonyított lefedését.

OSM: ODbL-1.0, © OpenStreetMap contributors. A helyi dokumentumok bizonyítékok; külön újrafelhasználási licencet nem állapítottunk meg.
