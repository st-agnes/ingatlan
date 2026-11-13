# Ingyenes városrészhatárok

Ez az adatgyűjtés a későbbi térképes címmegjelenítéshez készül. Nem módosítja a jelenlegi hirdetéseket, helyszínválasztót vagy párosítást, és nem kapcsol be fizetős API-t. A gyűjteményből egyetlen terület sincs automatikus címbesorolásra jóváhagyva.

## Adatállományok

- `data/neighborhoods/sources/whosonfirst/`: eredeti, rögzített Git-verzióból letöltött magyar rekordok, szülőtelepülések, forrásjegyzék és licenc. A névpontok is megmaradnak a források között, de nem válnak területté.
- `data/neighborhoods/sources/openstreetmap/`: a külön adatgyűjtő workflow-val lekért aktuális OSM-válaszok, ha rendelkezésre állnak. Minden válaszhoz település, lekérdezés, időpont, ellenőrzőösszeg és licenc tartozik.
- `data/neighborhoods/sources/national-osm/`: a magyar OSM közigazgatásihatár-export 2022. november 23-i Git-tükörben megőrzött admin10-rétege, **203 budapesti poligonnal**. Megmarad az eredeti öt shapefile-összetevő, a reprodukálható vetületi konvertáló és a GeoJSON. Ez a réteg vidéki városrészt nem tartalmaz. A dátum a tükör commitjának dátuma; a pontos OSM-kivágási időpont nem ismert.
- `data/neighborhoods/sources/national-osm-2025/`: ugyanennek az exportnak a 2025. augusztus 28-i Git-tükörben talált ZIP-állományából származó **202 budapesti poligon**. A letöltött archívum ellenőrzött lenyomata és tartalomjegyzéke, valamint az öt kinyert admin10-komponens és a GeoJSON külön lenyomata megmarad. A teljes országos archívumban sem volt admin11-réteg; a vidéki településhatárokból nem készítünk városrésznek látszó területeket.
- `data/neighborhoods/catalog.geojson.gz`: tömörített GeoJSON, benne a geometriai ellenőrzésen átment, településhez köthető **ellenőrizetlen poligonjelöltek**. Ez nem hiteles országos városrésznyilvántartás. A normál újraépítés a tömörítetlen `catalog.geojson` fájlt is előállítja.
- `data/neighborhoods/coverage.json`: a tényleges találatok, a 26 elsődlegesen vizsgált város, a hiányok és a kihagyott rekordok indoklása. A poligonok száma nem lefedettségi százalék.
- `data/neighborhoods/name-audit.json`: a 64 eredeti WOF-poligon név- és településellenőrzése, a mai névre tett javaslat, a történelmi névváltozatok kapcsolatai, a bizonytalan összerendelések és az ellenőrzés forráshivatkozásai. A névellenőrzés nem igazolja a régi geometria mai pontosságát.
- `data/neighborhoods/osm-association-audit.json`: konkrét OSM-azonosítóhoz és a nyers válasz SHA256-lenyomatához kötött településbesorolási javítások és kizárások. Egy területi OSM-lekérdezés a városhatárt metsző szomszédos elemet is visszaadhatja, ezért a lekérdezett település önmagában nem bizonyítja a városrész hovatartozását.
- `data/neighborhoods/sources/municipality-reference/`: hét település ellenőrzött forrású referenciahatára, reprodukálható kinyerés és a települési hozzárendelések térbeli diagnosztikája. A történeti Frankhegy-poligon jelentős átnyúlását is dokumentálja. A csúcspontarányok nem területi átfedési arányok; ez a diagnosztika önmagában nem hitelesít városrészhatárokat.
- `data/neighborhoods/budapest-local-areas.json`: a friss OSM-kivonat 16 kisebb lakótelepi, lakóparki vagy helyi karakterterülete, elkülönítve a fővárosi rendelet névjegyzékétől.
- `data/neighborhoods/reference-inventories.json`: külön megjelölt időszakra vonatkozó városrészjegyzékek, amelyekhez az ismert határok név szerint összehasonlíthatók.
- `data/neighborhoods/budapest-current-reference.json`: a hatályos fővárosi rendelet átírt névjegyzéke és a név szerint ismert budapesti hiányok bizonyítékai. Külön kezeli a 211 külön nevet és a 212 területi azonosságot: a XII. és XXIII. kerületi Orbánhegy két külön hely. A Gerce/Gercse névváltozat megfeleltetése külön forrást kapott.
- `data/neighborhoods/report.json`, `report.csv`, `report.md`: reprodukálható városonkénti statisztika és hiánylista. A géppel feldolgozható JSON és a táblázatos CSV mellett a Markdown közvetlenül olvasható összefoglaló.
- `data/neighborhoods/neighborhoods.geojson`, illetve `.geojson.gz`: az egységes, EPSG:4326 koordinátájú letölthető városrészállomány. A riportban elfogadott település–városrésznevenként egy valódi forrásgeometriát tartalmaz; a tágabb területi gyűjtőneveket kihagyja. Generált fájl, a csomag és a CI-artifact tartalmazza. A tulajdonságok megőrzik a forrást, licencet, időállapotot és az ellenőrzés szintjét.
- `data/neighborhoods/review.html`: generált, önálló, internetkapcsolat és térképszolgáltató nélkül megnyitható ellenőrző oldal. Város és név szerint lehet kiválasztani, megrajzolni és az eredeti forráshoz visszakövetni az alakzatokat. A repository az előállító kódot tárolja, a kész HTML a letölthető csomagban és a CI-artifactban található meg.

## Újraépítés

Nincs szükség npm-csomagra, Google-kulcsra, MySQL-re vagy futó backend­re:

```sh
node scripts/neighborhoods/build.mjs
node scripts/neighborhoods/report.mjs
node scripts/neighborhoods/export.mjs
node scripts/neighborhoods/build.mjs --check
node scripts/neighborhoods/report.mjs --check
node scripts/neighborhoods/export.mjs --check
node scripts/neighborhoods/preview.mjs
node tests/neighborhoods.test.mjs
node tests/neighborhoods-fetch.test.mjs
node tests/neighborhoods-osm.test.mjs
node tests/neighborhoods-national.test.mjs
node tests/neighborhoods-association.test.mjs
node tests/neighborhoods-report.test.mjs
python3 tests/neighborhood-national-fetch.test.py
```

A kész állományokból az összes forrást, licencet, riportot és újraépítő kódot tartalmazó, SHA256-tal ellenőrzött csomag készíthető:

```sh
python3 scripts/neighborhoods/package.py --output .local/neighborhoods/downloads
```

Ez kizárólag a meglévő helyi fájlokat csomagolja; nem indít adatlekérést. Az egységes exportot és a CSV-, szöveges és HTML-jelentést közvetlenül is kimásolja a megadott könyvtárba.

A HTML fájlt le lehet tölteni és közvetlenül megnyitni a böngészőben. A rajzhoz nem töltünk be alaptérképet, külső fontot vagy követőkódot. A forrásoldalak csak a forráshivatkozás megnyitásakor töltődnek be.

Az eredeti budapesti shapefile-ból a köztes GeoJSON külön is újra előállítható, Python 3 standard könyvtárral:

```sh
python3 data/neighborhoods/sources/national-osm/convert.py
python3 data/neighborhoods/sources/national-osm-2025/convert.py
```

Ezután a katalógust, a riportokat és az előnézetet a fenti sorrendben kell újraépíteni. A konvertálók ellenőrzik az eredeti komponensek lenyomatait. Az importáló mindkét forrás mind az öt eredeti komponensének bájtméretét, SHA256- és Git blob SHA1-lenyomatát, valamint az előállított GeoJSON külön SHA256-lenyomatát is ellenőrzi. A 2025-ös kinyert fájlok Git blob SHA1 értéke helyi tartalomlenyomat; a távoli repositoryban az egész ZIP blob-azonosítója visszaellenőrizhető. A nemzeti forrás tesztje mind a 203 korábbi és 202 újabb poligon összes élét összeveti az eredeti SHP tényleges csúcsaiból számolt vetületi transzformációval.

A böngészős ellenőrzőteszt a projekt CI-ben előkészített Playwright-környezetét használja: `node tests/neighborhoods-browser.test.mjs`. Ez külön ellenőrzi a generált oldal működését; az offline adatellenőrzésekhez nem szükséges böngészőt telepíteni.

## Összevonás és a statisztika értelmezése

Ugyanazon település ugyanazon normalizált városrésznevéhez elsőbbséget kap a frissen lekért OSM-határ, utána a 2025-ös, majd a 2022-es megőrzött nemzeti OSM-kivonat, végül a WOF-poligon. A csak a korábbi kivonatban szereplő valódi poligon jelöltként megmarad, saját forrásdátumával: ilyen a 2022-es Millenniumtelep. A 2025-ös adatban hiányzó rekordból nem következtetünk a városrész megszűnésére. A névazonosítás figyelmen kívül hagyja a kis- és nagybetűk, ékezetek, szóközök és írásjelek eltéréseit, ezért a Magdolna negyed / Magdolnanegyed írásváltozatból is egy név marad. Eltérő jelentésű nevek csak a `name-audit.json` kifejezett, forrással alátámasztott összerendelése alapján kapcsolhatók össze: például Auwinkel és Zugliget nem két külön mai városrész.

A gyengébb prioritású rekord `shadowed_by_*` indokkal és a megtartott rekord azonosítójával kerül a `coverage.json` kihagyott listájába. A forrásfájlt és annak eredeti geometriáját nem töröljük, a poligonokat nem egyesítjük és nem rajzoljuk át. A hibás településhez kötött vagy jelentősen bizonytalan geometria nem kerül át automatikusan egy másik településre. A támogatott mai név önmagában nem oldja fel ezt a hibát.

Külön, bizonyítékhoz kötött település-asszociációs audit javíthatja a név besorolását, az eredeti lekérdezési település megőrzésével. Például az Esztergomra kiadott lekérdezésből érkező Kolónia nevet Dorog önkormányzati forrása alapján Doroghoz rendeljük. A poligon ettől változatlan marad: 18 egyedi csúcsából 10 a 2025-ös Dorog-, 8 az Esztergom-referenciahatárba esik. Ezek **csúcspontszámok, nem területarányok**; a geometria átlépi a referencia-településhatárt, teljes Doroghoz tartozását nem állítjuk. Az azonos lekérdezésből érkező, bizonytalan azonosságú ipari-gazdasági területet kizárjuk a fő exportból. A forrásazonosító vagy a nyers válasz megváltozása esetén az auditot újra kell ellenőrizni: a nem egyező lenyomat megállítja az importot.

A riport külön közli a geometria darabszámát, az elfogadott különböző városrészneveket, a nagyobb területi gyűjtőneveket, a névellenőrzéssel alátámasztott neveket és a friss, illetve történeti OSM-források mennyiségét. Az „elfogadott név” az adatgyűjtésben használható név: lehet OSM-forrásnév is, amelyet még nem ellenőriztünk egyenként másik jegyzékben. **Nem jelenti azt, hogy az összes név mai létezése vagy az összes határ pontossága igazolt.**

Budapesten a friss OSM-adat kisebb lakótelepeket, lakóparkokat és kerületi karakterterületeket is lehatárol. Ezeket megtartjuk, és a riport külön felsorolja a fővárosi rendelet névjegyzékében nem szereplő neveket. A térképen névvel rendelkező területek darabszáma ezért nem azonos a fővárosi rendelet szerinti hivatalos városrészek számával.

Hiányzó határnak csak megadott jegyzékhez képest nevezünk meg konkrét városrésznevet. Debrecennél például a hivatkozott történeti jegyzék 79 nevéhez hasonlítjuk az összegyűjtött határokat; a jegyzék időszaka és a hiányzó nevek is megjelennek. Az ország összes jelenlegi városrészének teljes száma nincs megállapítva. Sikertelen vagy időtúllépéses lekérésből nem következtetünk arra, hogy az adott városnak nincsenek elérhető határai.

## Friss OSM-adatok gyűjtése

A `Collect draft neighborhood data` GitHub Actions workflow külön adat-előkészítő művelet. Csak olvasási repository-jogosultságot használ, nem telepít alkalmazást és nem kér Google Cloud-hozzáférést. Az eredményt `neighborhood-osm-draft` artifactként teszi letölthetővé. Az első gyűjtés hét várost vizsgált; az alapértelmezett `scope=all` a 26 célvárost vizsgálja. A `scope=core` a hétvárosos kisebb gyűjtés.

Ugyanez olyan környezetben, ahol a nyilvános OSM-szolgáltatás elérhető:

```sh
node scripts/neighborhoods/fetch-osm.mjs --scope core
node scripts/neighborhoods/fetch-osm.mjs --scope all
node scripts/neighborhoods/fetch-osm.mjs --cities Budapest,Debrecen --output .local/neighborhoods/osm
```

A lekérdezések városonként, egymás után futnak, idő- és méretkorláttal. A hibás vagy hiányos választ nem tekintjük üres városrészlistának. Az üres, de sikeres lekérdezés is csak azt jelzi, hogy a használt forrásból és lekérdezésből nem került elő terület; más forrás létezését nem zárja ki. A közösségi szolgáltatás rendelkezésre állása nem garantált, ezért a webalkalmazás működése nem függ ezektől a lekérdezésektől.

Minden gyűjtést új, üres kimeneti könyvtárba kell menteni; ismételt helyi futtatásnál adj másik `--output` útvonalat. A workflow minden alkalommal friss munkakönyvtárat használ. Újonnan gyűjtött állományokat ellenőrzés után lehet a rögzített forrásokhoz adni. Korábbi sikeres snapshot megtartásakor a forrás saját adatállapota marad irányadó; egy későbbi sikertelen lekérdezést külön kell feltüntetni, és nem szabad új sikeres adatállapotként feltüntetni.

## Minőség és kézi kiegészítés

A felhasználó által elfogadott gyűjtési elv szerint a régebbi, tényleges határpoligon is megfelelő jelölt lehet, ha a városrész mai neve és települése alátámasztható. A gyűjtéshez nem feltétel minden határ mai pontos vonalvezetésének újraellenőrzése. A forrás életkora, a név ellenőrzése és a geometria ellenőrzése ezért külön adat. Amíg valamelyik név ellenőrzése hiányzik, ezt láthatóan megőrizzük; nem írjuk át igazolttá pusztán attól, hogy bekerült a katalógusba.

A feldolgozás nem alakít városrész-névpontot, befoglaló téglalapot vagy önkényes sugarú kört határvonallá. Ellenőrzi a gyűrűk zártságát, koordinátáit, elfajulását, önmetszését, lyukait és a megadott befoglaló keretet. A WOF-geometria változatlan marad, az OSM-relációkat kizárólag a valóban közös végpontokkal rendelkező eredeti határszakaszokból állítjuk össze. A történeti nemzeti export eredeti EPSG:3857 csúcsait EPSG:4326-ba transzformáljuk, nyolc tizedesre kerekítjük, és a gyűrűk irányát/sorrendjét normalizáljuk. Egyik művelet sem rajzol új határszakaszt vagy közelítő területet. A forrásfájlok pontos bájttartalma ellenőrzőösszeggel visszakövethető.

Ezek az ellenőrzések önmagukban nem igazolják a városrész nevét, aktualitását, hivatalosságát, a külön területek egymás közötti átfedésmentességét vagy a házszintű besorolás helyességét. A Who's On First állományban például történelmi elnevezések, téves fordítások és hiányos szülőkapcsolatok is vannak. A fordító eltérő jelentésű fordítást nem cserél automatikusan az eredeti név helyére.

Kézi kiegészítésnél először önkormányzati határozatból vagy más megbízható leírásból kell azonosítani a határoló utcákat. A megfelelő utcaszakaszokat szabadon újrahasználható térképadatból lehet összeállítani és a kereszteződéseknél összekapcsolni. Google-térkép vagy kereskedelmi adatállomány átrajzolása nem része ennek a gyűjteménynek. Egy szabadon olvasható PDF nem automatikusan nyílt licencű vektoradat.

### Debrecen – Sestakert, előkészített források

- [Önkormányzati városfejlesztési vizsgálat, 2021–2027](https://hbmo.hu/portal/wp-content/uploads/2023/12/01A_eloterj.mell_DMJV-FVS-2021-27-megalapozo-vizsgalat.pdf), nyomtatott 208. oldal: a történelmi városrészek határtérképe; Sestakert a 48. elem.
- [Dehir helytörténeti cikk, 2022. november 17.](https://dehir.hu/debrecen/regi-debreceni-kertsegbe-kalauzol-nyul-imre/2022/11/17): Nádor utca, Thomas Mann utca, Mikszáth Kálmán utca, Békessy Béla utca, Dóczy József utca, Egyetem sugárút és Füredi út határolják.
- [Önkormányzati határozatok reprodukált melléklete](https://dea.lib.unideb.hu/server/api/core/bitstreams/9c8c07c6-2cd6-4731-8990-2047162be997/content), nyomtatott 140–143. oldal: a 92/2004. (IV. 22.) és 282/2005. (XI. 17.) határozat Sestakertet a 19. városrendezési körzethez kapcsolja.

A friss OSM-lekérésben Sestakert tényleges határrelációja is megtalálható: [17519326](https://www.openstreetmap.org/relation/17519326). Az első sikeres debreceni export 26 városrészt tartalmazott. Sestakert poligonja 110 forráscsúcsból áll, a gyűrű hiányzó szakasz hozzárajzolása nélkül zárható. A feldolgozás ezt a valódi határt használja; az utcanevek felsorolásából nem gyárt koordinátákat.

A későbbi, automatikus házszintű címbesorolás bevezetése előtt a határutcák két oldalán és a kereszteződéseknél is mintacímeket kell vizsgálni. Az út középvonala és a hivatalos városrészhatár eltérhet. Ez a szigorúbb ellenőrzés nem előfeltétele a jelenlegi adatgyűjtésnek. A `manual-definitions.json` megőrzi a kézi forrásfeltárás eredményét és a hátralévő ellenőrzést.

## Licenc és költség

A Who's On First saját munkájának CC0 jelölése nem váltja ki az eredeti adatforrások feltételeit. A teljes forráslicenc megmarad a gyűjtemény mellett; a Quattroshapes és más CC BY források megjelölése kötelező. Az OSM-ből származó adatokra az [ODbL és az OpenStreetMap forrásmegjelölése](https://www.openstreetmap.org/copyright) vonatkozik. A külön eredetű forrásállományokat külön kezeljük; az összesített jelöltgyűjtemény közlésénél minden alkalmazandó feltételt meg kell tartani.

A saját adatbázisban tárolt határok használata nem igényel minden megjelenítéskor külső határadat-lekérdezést. A későbbi címkoordináta-keresés és az alaptérképcsempék kiszolgálása ettől külön szolgáltatás; az alkalmazás teljes térképes működésének ingyenességét ez az adatgyűjtés önmagában nem garantálja.
