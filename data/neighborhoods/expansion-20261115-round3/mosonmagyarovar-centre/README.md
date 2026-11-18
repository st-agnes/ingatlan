# Mosonmagyaróvár: Belváros és Dunapart

Két külön, alacsony megbízhatóságú becsült keresési poligon készült a korábbi két fennmaradt névhez. **Belváros189639m², Dunapart198131m².** Mindkettő `estimated:true`, `lowConfidence:true`; egyik sem hivatalos, ellenőrzött városrész- vagy telekhatár. Nem készült kör, pontból generált téglalap, Voronoi vagy a teljes szülővárosrészre mutató alias.

## Belváros

A korábban gyűjtött **Magyaróvár** nagyobb szülőterület; a Belváros névpontját már lefedte, de nem jelentett külön belvárosi szűrőt. Az új poligon a Fő utca és Magyar utca történeti magját különíti el. Területe a tágabb Magyaróvár-becslés területének **8,29%-a**; 99,5%-ban annak belsejében van. **Nem azonos geometria és nem névalias.** A már meglévő Vár és a Wittmann park környezetét nem másolja a belvárosi maghoz.

Az önkormányzati[2008-as IVS](https://www.movinnov.hu/docs/IVS-1.pdf)37–38.oldala külön nevezi az Óvár belváros, Városközpont és Mosoni belváros egységeket; az eredeti teljes PDF és a vonatkozó szöveg itt mentve van. A nagyobb statisztikai Óvár-egységet nem neveztük át automatikusan Belvárossá. A[2017-es településképi kézikönyv](https://mosonmagyarovar.hu/websites/www.mosonmagyarovar.hu/files/hirek/2017/telepuleskepi-arculati-kezikonyv/Telepuleskepi_Arculati_Kezikonyv.pdf)20.PDF-oldala külön kezeli a történeti magot, a vár környezetét és a Wittmann parkot, és a Fő/Magyar, Kötélgyártó/Lakatos/Győrikapu/Tímár utcákhoz köti a belvárost. A[HÉSZ](https://njt.jog.gov.hu/jogszabaly/2014-20-SP-5Y3437.2)az Óvár történeti belváros előírásainál szintén e történeti utcákat és a Malom-ági Lajtát nevezi meg.

A választott körvonal nyugaton az eredeti Ady Endre, Városkapu és Fő utca vonalát, keleten a Malom-ági Lajta vonalát követi. Három rövid összekötés becsült: kb.20m,124m és15m; mindet koordinátával és hosszal rögzíti a `validation.json`. A történeti/övezeti határ ezekkel való pontos egyezését nem állítjuk. A `belvaros-context.png` saját, mentett OSM-vonalakból rajzolt ellenőrző kép, nem élő térképcsempe.

## Dunapart

A név egy szárazföldi folyóparti városrészt jelöl, ezért **nem vízfelület-poligont** kapott. A becslés a Fazekas/Petőfi/Duna/Felsőötház/Aranyossziget környéki utcákat és telkeket foglalja össze, a déli Rév-kapcsolat felé. Keleti széle a Mosoni-Duna változatlan forrás-középvonalának megfelelő szakasza; ezért keskeny mederrész is maradhat benne. A geometria túlnyomó része a nyugati, szárazföldi utcás/negyedkörnyezet, nem folyópuffer.

A `dunapart-trace.json` kézzel kijelölt nyugati utcás/telektömbös élt tárol a mentett `dunapart-context.png` koordinátáiban. A `build.py` az eredeti folyóvonal megfelelő szakaszával zárja le. A kézi összekötések alacsony megbízhatóságúak; nem vélelmeznek hivatalos negyedhatárt. A helyazonosságot a mentett OSM-névpont, a megnevezett utcák, az önkormányzati vízparti fejlesztési környezet és a `source-facts.json` további hivatkozásai támasztják alá.

## Forrás és offline újraépítés

A `source-roads.geojson.gz`, `source-areas.geojson.gz`, `source-named-points.geojson` és `municipality.geojson` változatlan eredeti geometriai források a korábbi Mosonmagyaróvár-csomagból. Az országos OSM-pillanatkép2026-11-12; PBF SHA256: `224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a`. © OpenStreetMap contributors, ODbL1.0. Objektumazonosítók, címkék, verziók, forrás-URL-ek a mentett adatokban maradtak. A `prior-quarters.geojson` a szülő-gyermek összehasonlítás fagyasztott bemenete.

```bash
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round3/mosonmagyarovar-centre/build.py
python3 data/neighborhoods/expansion-20261115-round3/mosonmagyarovar-centre/render.py
```

A normál újraépítés nem igényel hálózatot, PBF-et, globális hiánylistát vagy a korábbi csomag fájljait. Python, Shapely és pyproj kell a geometriához; Pillow csak az ábrákhoz. A `manifest.json` a teljes újraépítési bemenetet hash-eli. A `validation.json` geometriai érvényességet, saját névpont tartalmazását és a szülővel való különbséget ellenőriz; **nem földrajzi pontossági audit és nem MySQL-import**. A rögzített két kiinduló névhez az `unresolved.json` üres; ez nem új országos teljességi állítás.
