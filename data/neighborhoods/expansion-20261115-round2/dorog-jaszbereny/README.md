# Dorog és Jászberény – 2026-11-15, második gyűjtési kör

**17 új kereshető terület:** Dorog 10 lakótelepe és Jászberény 7 korábban csak ponttal ismert helyneve. A befagyasztott céljegyzék mind a 17 neve kapott poligont; ez a csomag céljainak teljesítése, nem a két település minden elképzelhető városrészének vagy az ország teljességének állítása.

## Beemelendő állomány

- `features.geojson`: mind a 17, WGS84 / EPSG:4326, hosszúság–szélesség sorrendben.
- Ugyanezek külön: `dorog-features-v2.geojson` (10) és `jaszbereny-features.geojson` (7). Vagy az összevont, vagy a két külön állományt kell regisztrálni, együtt nem szabad őket kétszer betölteni.
- A korábbi `dorog-features.geojson` az első, túl szűk Schmidt/Zsigmondy becslést megőrző diagnosztikai állomány. **Nem beemelendő.** A v2 már mind a 213, a lakótelepek címnevét viselő, archivált OSM-címet tartalmazza. Nem csak a névpontokat körülvevő épülettömb került kijelölésre.

## Módszer és korlátok

Dorogon a lakótelepi címcsoportok és név szerint térképezett utcák, a teljes épületegyüttesek, közös udvarok, zöldfelületek és külső utcák alapján értelmezett, kézzel felvett határ készült. A 213 cím ellenőrzése kiterjedési kontroll, nem hatósági határellenőrzés. A Schmidt és Zsigmondy különböző névhasználatú határai részben átfedhetnek.

Jászberényben a Hűtőgépgyár teljes, 49,5 hektáros, névvel ellátott iparterülete és a Necsőtelephez kapcsolt teljes 70,8 hektáros Jász Plasztik-telep nyers forráskontúrja szerepel. A cím/településrész és az iparterület közötti jelentésbeli megfeleltetés becslésként van jelölve; nem állítjuk, hogy egy cégnév önmagában hivatalos városrészhatár.

A többi jászberényi terület az archivált utcák, vasút/vízfolyás, épületcsoportok és beépítési átmenetek alapján értelmezett körvonal. Újerdő a déli erdős-tanyás út- és udvarrendszer szabálytalan becsült területe, nem egy nagy erdőfolt automatikus átvétele. Itt a ritkás beépítés és a hagyományos külterületi névhasználat miatt különösen bizonytalan a határ.

**Mind a 17 rekord becslés, `estimated=true`, `lowConfidence=true`.** Ebből 15 kézi fizikai térképi becslés, 2 teljes, tényleges forráspoligonhoz kapcsolt szemantikai területbecslés. Nincs kör, pontokból képzett doboz, Voronoi-felosztás vagy ponthalmaz burka. Az adat a későbbi cím–poligon keresés kiindulópontja, nem hivatalos földmérési nyilvántartás.

## Megőrzött bizonyíték és újraépítés

- `source-roads.geojson.gz`: 4670 tényleges OSM-út/vízfolyás/vasút-vonal.
- `source-areas.geojson.gz`: 1589 tényleges földhasználati/természeti kontúr.
- `source-buildings.geojson.gz`: 18241 épület a két korlátozott vizsgálati ablakból.
- `source-addresses.geojson.gz`: 5231 cím, ebből a vizsgált dorogi lakótelepi címek 213 darab.
- `source-manifest.json`: PBF-forrás, időbélyeg, SHA256, kiterjedések és licenc.
- `source-municipalities.geojson`: Dorog korábban archivált referenciahatára és Jászberény tényleges OSM-közigazgatási határa; ezekre történik a levágás.
- `*-context.png`, `*-registration.json`: a fenti tényleges térképi forrásokból rajzolt, EOV-térbe regisztrált áttekintők. A pixelek alapján felvett határpontok a `trace-specifications.json` fájlban szerepelnek.
- `source-facts.json`: további tervezési és névhasználati hivatkozások. A letöltésre javasolt PDF/PNG csak kiegészítő forrás; a jelen geometriák nem ezek nem archivált határvonalainak másolatai.

Az OSM-adatok forrása a Geofabrik magyarországi kivonatának 2026-11-12T21:23:05Z állapota, ODbL-1.0, © OpenStreetMap contributors. Az eredeti objektumazonosítók, tagek és URL-ek a forrásfájlokban maradnak. A tényleges letöltési/geometriaforrás és a tervezési szövegre alapozott következtetés külön szerepel.

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/dorog-jaszbereny/build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/dorog-jaszbereny/verify.py
```

Az offline újraépítéshez csak a csomag helyi állományai, Shapely és pyproj kellenek. A térképi áttekintő újbóli előállításához Pillow is szükséges (`render-context.py`). Az `extract.py` a nagy eredeti PBF-ből újra kinyeri a nyers bizonyítékot, de a poligonok újraépítéséhez nem szükséges ezt újrafuttatni. A `verify.py` bizonyítja a bájtra azonos újraépítést, a 17 egyedi célnevet, a geometriák érvényességét és a 213 dorogi cím befoglalását.

Az `unresolved.json` ebben a befagyasztott 17-es csomagban üres. Ettől további források vagy más helynevek még létezhetnek; a tágabb országos gyűjtés folytatandó. Alkalmazáskódot, globális katalógust, adatbázist vagy Cloud-környezetet ez a csomag nem módosít.
