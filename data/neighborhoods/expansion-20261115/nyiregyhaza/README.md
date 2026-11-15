# Nyíregyháza – 2026. november 15-i kiegészítés

**13 új névhez 13 becsült poligon vagy multipoligon, továbbá 1 forrással igazolt névváltozat-javaslat.** Mind a 13 új alakzat `estimated: true`, `lowConfidence: true`. A korábbi 14 elemű név szerinti hiánylistát ez feldolgozza; teljes városi, hivatalos vagy folytonos területi lefedettséget nem állít.

Az önálló alakzatok: Alispántanya, Báthory-lakópark, Felsőbadúrbokor, Kerti lak, Kun lakópark, Nagylapos, Salamonbokor, Samókabokor, Szabadságbokor, Sóstóhegyi lakópark, Tópart, Vadastanya, Őzdomb-lakókert.

## Mit jelentenek az alakzatok?

- **Salamonbokor és Szabadságbokor:** a névvel jelölt helyi utak mentén már ténylegesen létező, változatlan OSM falusias lakóterület-poligonok. A név hozzárendelése következtetés. Az előbbi a Tiszavasvári út déli, az utóbbi az északi oldalán van; nem a teljes, korábban gyűjtött „Kertváros, Salamonbokor, Szabadságbokor” szülőalakzat másolatai. A bokrok teljes mezőgazdasági határát nem állítják.
- **Alispántanya, Vadastanya, Nagylapos, Samókabokor, Felsőbadúrbokor:** ténylegesen térképezett, változatlan tanyaudvarokból álló széttagolt, **részleges beépített felszínek**. A `partialSettlementFootprint` jelző igaz. A környező szántóföldek nincsenek kitalált kerületté összezárva; a névpont emiatt kívül is maradhat az udvarokon. A helynevekhez való hozzárendelés becslés.
- **A hat kis városi/üdülőterületi egység:** helyi utcák, vasút, tópart és a tényleges lakóterület-szél alapján kézzel rajzolt durva keresési terület. A `selection.json` megőrzi az egyes csúcsokat és az egyedi indokolást. Nem felmért telekhatárok. Kerti lak és Tópart közeli önálló névpontjai, valamint eltérő, átfedő becslései megmaradnak; azonosságuk nincs igazolva.

Kör, pontpuffer, Voronoi-felosztás és konvex burok nem készült. A szülőterületekkel vagy történeti/helyi felosztásokkal való átfedés megengedett. A nagy, városi CLC lakóterületet nem neveztük át kis lakóparkká.

## A Belső lakóterület név

Az `alias-proposals.json` önálló javaslat; globális névjegyzéket nem módosít. A megőrzött hivatalos ITS 15. oldala az 1. egységet „Belső lakóterület (Belváros)”, a 16. oldal ugyanazon 1. egységét „Belső lakóterület” néven közli, és a szöveg is összekapcsolja a két kifejezést. Emiatt a rövid nevet az addig is létező teljes névhez javasoljuk, új másolatpoligon nélkül. Ez a konkrét tervezési egység névpárjára érvényes; nem minden szűkebb Belváros-használat azonosságának állítása.

## Megőrzött bizonyítékok és újraépítés

A `source-landuse.geojson` 1956 helyi tényleges OSM területalakzatot őriz a 2026-11-12-i PBF-ből. A `source-labels.geojson`, `source-roads.geojson` és `source-municipality.geojson` a felhasznált névpontokat, útvonalakat és a településhatárt tárolja. A `source-evidence.json` forrás-URL-eket, dokumentumoldalakat, indoklásokat és az ITS SHA-256-át tartalmazza. A `*-context.png` képek a gyűjtéskor átnézett helyi fizikai térképek; a korábbi önkormányzati karaktertérképben a jelen célnevek helyét a `character-label-context.png` mutatja.

A teljes forrás-PDF-ek a korábbi, változatlan csomagokban maradnak: `sources/municipal-east/nyiregyhaza-its-2022.pdf`, illetve `expansion-20261114-next/fehervar-nyiregyhaza/nyiregyhaza-tak2017.pdf`. Utóbbi a 31/2017-es településképi rendelet 28. oldali melléklete; a régi fájlnév ellenére nem külön városrész-határkatalógus.

A fő réteg újraépítése kizárólag e mappa mentett állományaiból, hálózat és országos PBF nélkül:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/nyiregyhaza/build.py
```

Függőségek: `shapely`, `pyproj`. Az opcionális `extract-local-osm.py` a helyi országos PBF-ből újra kivonja a forrásterületeket, ehhez `osmium` is szükséges. A `render-context.py` a korábbi mentett teljes útanyagból készíti a szemléltető térképeket (`matplotlib`).

Ellenőrzés: mind a 13 alakzat érvényes, nem üres WGS84 Polygon/MultiPolygon, és a forrás szerinti Nyíregyháza településhatáron belül van. Ugyanazon település–név pár kétszer nem szerepel. A `validation.json` és a `summary.json` megőrzi az eredményt; a `unresolved.json` a még nem igazolt pontossági/terjedelmi kérdéseket.

OSM-adatok: ODbL-1.0, © OpenStreetMap contributors. A hivatalos PDF-ek és a fejlesztői lapok bizonyítékok; külön újrafelhasználási licencet nem állapítottunk meg.
