# Térképes helyszínválasztás

A kezdőoldali kereső és a keresési igények ötlépéses űrlapja alatt OpenFreeMap-alaptérkép jelenik meg a helyben tárolt MapLibre megjelenítővel. A kereshető települések, budapesti kerületek és városrészek neveire kattintva vagy koppintva ugyanazokat a kanonikus helyszínazonosítókat választjuk ki, mint a szöveges keresővel.

Alapállapotban helynevek és az alaptérkép látszanak. Csak a **kiválasztott** helyek körvonala jelenik meg, kitöltés nélkül. A kiválasztott név kiemelést kap. Újabb kattintás a névre kiveszi a helyet a keresésből, és eltünteti a körvonalát. Az üres területre kattintás nem jelöl ki egy esetlegesen ott fekvő, átfedő poligont.

A szöveges találat kiválasztása a településre, kerületre, utcára vagy városrészre nagyít. Térképes városrészválasztáskor az adott teljes város vagy az őt tartalmazó, korábban kijelölt nagyobb terület helyett a kisebb terület kerül a keresésbe. A többi választás és az 50-es helyszínkorlát megmarad. A térkép nem nyitja fel a telefon billentyűzetét.

A gyors ismételt koppintás a kijelölést váltja, nem nagyítja vagy mozgatja közben a térképet. A nagyítás gombokkal, egérgörgővel és két ujjal érhető el. A feliratok körül biztosított kis érintési ráhagyás segíti a mobilos választást. Több közeli felirat esetén egyértelmű, állandó sorrend dönt; nincs utólagos választóablak. A helynevek opcionális listából, billentyűzettel is kijelölhetők.

A távoli nézet túlnyúlhat Magyarországon, hogy egy széles képernyő széle ne tolja el a kiválasztott települést a középpontból. A nagyítás mindig a választott hely körül történik. A térképes keresés nem kér helyhozzáférést, nem végez címgeokódolást, és nem továbbít vagy jelenít meg ingatlan-koordinátákat.

## Helynevek és keresési határok

A kereshető helyneveket az alkalmazás saját katalógusa rajzolja a vektoros alaptérkép fölé. Ez 3155 település, 23 budapesti kerület és mind a 4308 összegyűjtött városrész azonosítóját megőrzi. A szöveges és térképes választás között nincs bizonytalan, kattintásonként végzett névegyeztetés.

A feliratpontokat előre készítjük el. Ahol a rögzített OSM-helynév megfeleltethető a városrésznek és a pontja az eredeti és az egyszerűsített poligonon belül is van, azt használjuk. Másutt geometriailag a terület belsejébe eső megjelenítési pontot képzünk. A budapesti kerület és az azonos területet leíró városrész felirata közös határra hivatkozhat; ugyanaz a hely nem kap egymásra írt kettős feliratot.

A magyarországi település- és városrésznevek alaptérképi feliratai helyett ezeket a saját, kanonikus neveket jelenítjük meg. Az utcák, utak és a többi háttértérképi elem továbbra is az OpenFreeMap rétegeiből származik. A Magyarországon kívüli alaptérképi helynevek megmaradnak.

A névsűrűséget a hely típusa, a valódi tartalmazási viszonyok, a nagyítás és a MapLibre feliratütközés-kezelése határozza meg. Az egymás mellett fekvő városrészeket nem pusztán a területük alapján osztjuk külön nagyítási sávokba. Egy adott nézetben a feliratok csak annyian jelennek meg, amennyien olvashatóan elférnek; a többi hely a közelítéssel vagy a szöveges keresővel érhető el.

A térkép display-only geometriát használ. Az ingatlanok valódi városrésztagságát továbbra is a teljes felbontású MySQL-geometriák és a meglévő térbeli/tagsági indexek döntik el. Az eladói pontos cím és a szerveroldali Google-geokódolás működése változatlan.

## Adatok és betöltés

- A `dist/data/map/labels.json` pontokat, neveket, kanonikus azonosítókat, a rögzített források hashét és a kiválasztható határok hivatkozásait tartalmazza. Az országos feliratpontok betöltése nem tölti le az ország összes városrész-poligonját.
- Az eredeti, 617 tartalomazonosított `city-…json` fájlban lévő 4308 megjelenítési poligon, a bounds-only `index.json` és a külön `hierarchy.json` változatlan forrásadatokra támaszkodik. A teljes keresési geometriát tartalmazó backendcsomag továbbra sem kerül a Hostingra.
- A `town-…json` fájlok a kiválasztott települések egyszerűsített körvonalait adják. Ezek csak akkor kellenek, amikor az adott település ki van jelölve. A városrészek határait szintén csak a kijelölt helyek körvonalához töltjük le, nem a feliratok megjelenítéséhez.
- A térképre eső összes kiválasztott hely, legfeljebb 50, körvonalat kaphat. Egyszerre legfeljebb négy fájl töltődik, az azonos fájlra mutató kérések összevonódnak. A gyorsítótár nyolc teljes települési réteget és a szükséges kiválasztott geometriákat őrzi; legfeljebb 650 felirat kerül a nézetbe. A késleltetett lekérések és a megszakított/elavult válaszok eldobása tovább korlátozza a terhelést. Mozgatáskor nincs poligonmetszet-számítás vagy külső névkeresés.
- A térkép az űrlapoktól függetlenül töltődik be. Hiba vagy WebGL2-t nem támogató böngésző esetén a szöveges kereső működőképes marad. Újrapróbálás külön gombbal indítható; a hibás térkép nem tartja fogva a navigációt.

## Előállítás és ellenőrzés

Rögzített források:

- `data/neighborhoods/search-areas.geojson.gz`: a 4308 keresési terület.
- `data/neighborhoods/sources/country-osm/municipalities.geojson.gz`: településhatárok.
- `data/neighborhoods/sources/country-osm/named-nodes.geojson.gz`: a rendelkezésre álló OSM-helynévpontok.

A generátor nem módosítja a keresési poligonokat vagy a backend adatait. GEOS-szal egyszerűsíti a képernyőre szánt határokat, megtartva a különálló részeket és lyukakat, és előállítja a feliratpontokat.

```sh
python3 scripts/build-neighborhood-map.py
python3 scripts/build-neighborhood-map.py --check
node tests/neighborhood-map-data.test.mjs
node tests/neighborhood-map.test.mjs
node tests/gcp-deployment.test.mjs
```

A generáláshoz `libgeos_c` 3.10 vagy újabb szükséges (Ubuntu 24.04: `libgeos-c1t64`). A Node-adatteszt ellenőrzi a kanonikus azonosítókat, a forráshasheket, a feliratok és határok hivatkozásait, a geometriák épségét és a tartalomazonosított fájlneveket. A telepítő minden hivatkozott fájlt és a hozzájuk tartozó verziókat ellenőrzi, mielőtt lecserélné a korábbi Hosting-állományokat. A Chromium-tesztek helyi hálózati adatokkal ellenőrzik a valódi megjelenítőt asztali, tablet- és mobilméretben.

## Térképszolgáltató és licencek

A MapLibre GL JS 6.19.0 modulja, workerje, CSS-e és licence a `dist/vendor/maplibre/` könyvtárból töltődik. A `provenance.json` megőrzi az npm-kiadás SRI-jét, az archívum SHA-256 hashét és az egyes fájlok hashét; a csomagoló ezek mellett külön rögzített kiadási fájlhasheket is ellenőriz, így egy átírt worker és átírt jegyzék együtt sem fogadható el. A megjelenítőhöz nincs szükség külső JavaScript-CDN-re. Az OpenFreeMap Liberty stílusának rögzített változata a `dist/data/map/style.json`; az alaptérkép vektoros csempéi, karakterkészletei és képi elemei az OpenFreeMaptől érkeznek. Csak a szokásos interaktív nézet kér adatokat, nincs tömeges vagy offline előtöltés.

Az OpenFreeMap nyilvános szolgáltatása jelenleg ingyenes, üzleti alkalmazásban is használható, nem igényel regisztrációt vagy API-kulcsot. A közösségi szolgáltatás nem ad SLA-garanciát. Forrás: https://openfreemap.org/ és https://openfreemap.org/quick_start/.

A keresőmezők mellett továbbra is egyetlen **Források** link vezet a `THIRD-PARTY-NOTICES.txt` jegyzékhez. A térképen is látszik az OpenFreeMap/OpenMapTiles/OpenStreetMap-forrásjelölés. Az alaptérkép adatainak és a saját összeállított városrészkatalógusnak a licence, eredete és korlátai külön szerepelnek a jegyzékben.

A normál tesztdeployhoz nincs szükség új secretre, API-kulcsra, Google Cloud-erőforrásra vagy kézi konfigurációra.
