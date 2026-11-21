# Térképes helyszínválasztás

A kezdőoldali kereső és a keresési igények ötlépéses űrlapja alatt OpenStreetMap-alapú térkép jelenik meg. A szöveges találat kiválasztása a településre, budapesti kerületre vagy városrészre nagyít. Közelebbi nézetben a városrész-poligonok kattinthatók; a választás ugyanazokat a kanonikus helyszínazonosítókat használja, mint a keresőmező.

Térképes városrészválasztáskor az adott teljes város vagy a korábban kiválasztott, őt tartalmazó nagyobb terület kijelölése a választott városrészre szűkül. A többi kiválasztott helyszín megmarad. Az 50-es helyszínkorlát cserénél is érvényes. A már kijelölt terület ismételt kattintással kivehető a keresésből; a címkék törlőgombjai is megmaradnak.

A gyors ismételt koppintás is a kijelölést váltja, nem nagyítja vagy mozgatja közben a térképet. Nagyítani a térkép gombjaival, egérgörgővel vagy két ujjal lehet.

A térképre kattintva közvetlenül változik a kijelölés, nincs utólagos választóablak. A városrészeknek csak a körvonala látszik; kijelölve és billentyűzetfókusszal sem kapnak kitöltést. A körvonal belsejére kattintás is működik. Ha a látható poligonok átfedik egymást, a kattintás a ténylegesen legkisebb területűt választja ki. A lyukakat levonjuk, a különálló poligonrészeket összeadjuk, nem a befoglaló téglalap mérete dönt. Az azonos méretű találatoknál a stabil helyszínazonosító ad egyértelmű sorrendet. A látható területek opcionális listából és billentyűzettel is kijelölhetők.

A nagyítási szinteket a területek egymásba ágyazódása határozza meg. A független városrészek a 8-as szinttől látszanak, és közelítéskor is megmaradnak, mérettől függetlenül. Debrecenben például Nagyerdőalja és Szentlászlófalva együtt látható. Valóban tartalmazott területek további két nagyítási lépésenként jelennek meg: például Pest körvonalán belül később a VI. kerületé. A szülőterület körvonala is megmarad, így a hiányos részletes felosztás nem tünteti el a még fel nem osztott részeket.

Az eladói pontos cím űrlapja változatlan. A térkép nem kér helyhozzáférést, nem hív Google-geokódolást és nem jelenít meg ingatlan-koordinátákat. A térképes kereséshez nincs szükség API-kulcsra vagy új Google Cloud-erőforrásra.

## Adatok és betöltés

- Mind a 4308 kanonikus városrész szerepel a külön megjelenítési katalógusban, 617 települési fájlban. A `dist/data/map/index.json` csak neveket, fájlazonosítókat és nagyítási határokat tartalmaz. Mind a 3155 településre, 23 budapesti kerületre és 4308 városrészre van nagyítási célterület.
- A térkép megnyitásakor a Leaflet, a megjelenítési index és a külön `dist/data/map/hierarchy.json` metaadatfájl töltődik be. Ez utóbbi 94 KB, tömörítve körülbelül 27 KB; országos poligonkoordinátákat nem tartalmaz. A poligonokat csak 8-as vagy közelebbi nagyításnál, a látható környékhez kérjük le. Egyszerre legfeljebb nyolc települési fájl és 650 terület kerül a nézetbe. A nyolcelemű memória-gyorsítótár és a késleltetett, megszakítható lekérések korlátozzák a terhelést.
- A tartalmazási kapcsolatokat előre, GEOS-szal számítjuk az eredeti geometriákból. A szülő a gyermek legalább 95%-át tartalmazza, és legalább 25%-kal nagyobb nála; a puszta átfedés vagy területméret nem elég. A legkisebb megfelelő szülőt választjuk. Az 5%-os határengedmény a különböző, részben becsült adatforrások eltéréseit kezeli. A bizonytalanul elhelyezett terület önálló marad, nem erőltetjük másik terület alá.
- A jelenlegi hierarchia 1169 kapcsolatot, 3139 önálló gyökérterületet és legfeljebb négy tartalmazási szintet tartalmaz. A böngésző csak a már kiszámolt kapcsolatokat és befoglaló határokat szűri; mozgatáskor nem számol poligonmetszetet. A szöveges kiválasztás természetes nagyítását megtartjuk, és szükség esetén közelítünk a kijelölt terület megjelenési szintjéig.
- A tényleges poligonterületeket a kattintásnál szükséges sorrendhez egyszer számítjuk ki, és a városi rétegek gyorsítótárához kapcsolva megőrizzük. Csak az éppen kirajzolt területek vehetnek részt a kiválasztásban.
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

A generáláshoz `libgeos_c` 3.10 vagy újabb szükséges (Ubuntu 24.04: `libgeos-c1t64`). A Node-adatteszt külön GIS-csomag nélkül ellenőrzi az összes kanonikus azonosítót, a lyukak és különálló részek megtartását, az állományméreteket, a hierarchiát és a tartalom alapján képzett fájlneveket. A telepítő ellenőrzi a hivatkozott városi rétegeket és a hozzájuk tartozó hierarchia verzióját, hivatkozásait és körmentességét; hibás adatokkal nem írja felül a korábbi Hosting-állományokat.

## Térképszolgáltató és licencek

A Leaflet 1.9.4 JavaScript és CSS helyben, a `dist/vendor/leaflet/` könyvtárból töltődik; nincs külső JavaScript-CDN-függőség. A BSD 2-Clause licencet és az ellenőrzött kiadás forrását a mellékelt `LICENSE`, illetve `THIRD-PARTY-NOTICES.txt` tartalmazza.

A landing és az onboarding keresőmezője mellett egyetlen **Források** link vezet a részletes forrás- és licencjegyzékhez. A KSH-, OSM- és Magyar Posta-hivatkozások ezen az oldalon maradnak elérhetők. A térképcsempék kötelező OpenStreetMap-jelölése közvetlenül a térképen is látszik.

Az alaptérképet a `tile.openstreetmap.org` adja, a térképen látható OpenStreetMap-forrásjelöléssel. Csak a szokásos interaktív nézet tölt csempéket, nincs tömeges vagy offline előtöltés. A közösségi kiszolgáló [használati szabályai](https://operations.osmfoundation.org/policies/tiles/) érvényesek; ez nem garantált, korlátlan tárhely. A Chromium-tesztek helyi képpel váltják ki a csempekéréseket, nem terhelik az OSM-kiszolgálót.
