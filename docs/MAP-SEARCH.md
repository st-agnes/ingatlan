# Térképes helyszínválasztás

A kezdőoldali kereső és a keresési igények ötlépéses űrlapja alatt OpenStreetMap-alapú térkép jelenik meg. A szöveges találat kiválasztása a településre, budapesti kerületre vagy városrészre nagyít. Közelebbi nézetben a városrész-poligonok kattinthatók; a választás ugyanazokat a kanonikus helyszínazonosítókat használja, mint a keresőmező.

Térképes városrészválasztáskor az adott teljes város kijelölése a választott városrészekre szűkül. A többi kiválasztott helyszín megmarad. A jelölések eltávolíthatók a helyszíncímkékből, a térkép színezése követi a választást. Az 50-es helyszínkorlát cserénél is érvényes, az ismételt kattintás nem hoz létre duplikátumot.

A térképre kattintva azonnal hozzáadódik egy terület, nincs utólagos választóablak. Távolabbról nagyobb, közelebbről kisebb városrészek láthatók. Budapest 11-es nagyítási szintjén csak Buda és Pest jelenik meg; közelítéskor kisebb területek váltják fel őket. Ha a látható poligonok átfedik egymást, a kattintás a ténylegesen legkisebb területűt választja ki. A lyukakat levonjuk, a különálló poligonrészeket összeadjuk, nem a befoglaló téglalap mérete dönt. Az azonos méretű találatoknál a stabil helyszínazonosító ad egyértelmű sorrendet. A látható területek opcionális listából és billentyűzettel is kijelölhetők.

Az eladói pontos cím űrlapja változatlan. A térkép nem kér helyhozzáférést, nem hív Google-geokódolást és nem jelenít meg ingatlan-koordinátákat. A térképes kereséshez nincs szükség API-kulcsra vagy új Google Cloud-erőforrásra.

## Adatok és betöltés

- Mind a 4308 kanonikus városrész szerepel a külön megjelenítési katalógusban, 617 települési fájlban. A `dist/data/map/index.json` csak neveket, fájlazonosítókat és nagyítási határokat tartalmaz. Mind a 3155 településre, 23 budapesti kerületre és 4308 városrészre van nagyítási célterület.
- A térkép megnyitásakor a Leaflet és a kiszolgált megjelenítési index töltődik be. A poligonokat csak 11-es vagy közelebbi nagyításnál, a látható környékhez kérjük le. Egyszerre legfeljebb nyolc települési fájl és 650 terület kerül a nézetbe; közelebbi nagyítással a többi is elérhető. A nyolcelemű memória-gyorsítótár és a késleltetett, megszakítható lekérések korlátozzák a terhelést.
- A méretsávok településenként a legnagyobb városrészhez igazodnak, így kisebb városokban is használható a távoli nézet. Egy nagyítási lépés körülbelül négyszer kisebb területű poligonokat enged megjelenni. Ha a látható környéken még nincs az adott szinthez tartozó kisebb terület, az utolsó elérhető nagyobb méretsáv marad látható. A legközelebbi, 18-as szinten a legapróbb területek is elérhetők. A szövegesen kiválasztott városrészre nagyítás a megfelelő méretsávhoz is igazodik.
- A poligonterületeket egyszer számítjuk ki, és a városi rétegek gyorsítótárához kapcsolva megőrizzük. Mozgatáskor a látható határok és ezek a kiszámolt területméretek alapján szűrünk; kattintáskor csak az éppen kirajzolt területek vehetnek részt a kiválasztásban.
- A határokat csak a rajzoláshoz egyszerűsítjük, minden eredeti poligonrész és lyuk megtartásával. A valódi ingatlankeresés továbbra is a változatlan, teljes felbontású MySQL-geometriát és a meglévő tagsági indexeket használja.
- A térkép betöltési hibája nem blokkolja a szöveges keresőt. Az újrapróbálás külön gombbal indítható; a háttértérkép hiányában a már betöltött városrészek továbbra is kijelölhetők.

## Előállítás és ellenőrzés

Az eredeti, rögzített források a `data/neighborhoods/search-areas.geojson.gz` és a `data/neighborhoods/sources/country-osm/municipalities.geojson.gz`. A generátor nem módosítja a keresési poligonokat vagy a backend adatait.

```sh
python3 scripts/build-neighborhood-map.py
python3 scripts/build-neighborhood-map.py --check
node tests/neighborhood-map-data.test.mjs
node tests/neighborhood-map.test.mjs
```

A generáláshoz `libgeos_c` 3.10 vagy újabb szükséges (Ubuntu 24.04: `libgeos-c1t64`). A Node-adatteszt külön GIS-csomag nélkül ellenőrzi az összes kanonikus azonosítót, a lyukak és különálló részek megtartását, az állományméreteket és a tartalom alapján képzett fájlneveket. A telepítő ellenőrzi, hogy minden hivatkozott városi réteg megvan és egyezik az ellenőrzőösszegével; ismeretlen vagy hiányzó réteggel nem írja felül a korábbi Hosting-állományokat.

## Térképszolgáltató és licencek

A Leaflet 1.9.4 JavaScript és CSS helyben, a `dist/vendor/leaflet/` könyvtárból töltődik; nincs külső JavaScript-CDN-függőség. A BSD 2-Clause licencet és az ellenőrzött kiadás forrását a mellékelt `LICENSE`, illetve `THIRD-PARTY-NOTICES.txt` tartalmazza.

Az alaptérképet a `tile.openstreetmap.org` adja, a térképen látható OpenStreetMap-forrásjelöléssel. Csak a szokásos interaktív nézet tölt csempéket, nincs tömeges vagy offline előtöltés. A közösségi kiszolgáló [használati szabályai](https://operations.osmfoundation.org/policies/tiles/) érvényesek; ez nem garantált, korlátlan tárhely. A Chromium-tesztek helyi képpel váltják ki a csempekéréseket, nem terhelik az OSM-kiszolgálót.
