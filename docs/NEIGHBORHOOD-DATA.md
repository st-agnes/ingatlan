# Ingyenes városrészhatárok

Ez az adatgyűjtés a későbbi térképes címmegjelenítéshez készül. Nem módosítja a jelenlegi hirdetéseket, helyszínválasztót vagy párosítást, és nem kapcsol be fizetős API-t. A gyűjteményből egyetlen terület sincs automatikus címbesorolásra jóváhagyva.

## Adatállományok

- `data/neighborhoods/sources/whosonfirst/`: eredeti, rögzített Git-verzióból letöltött magyar rekordok, szülőtelepülések, forrásjegyzék és licenc. A névpontok is megmaradnak a források között, de nem válnak területté.
- `data/neighborhoods/sources/openstreetmap/`: a külön adatgyűjtő workflow-val lekért aktuális OSM-válaszok, ha rendelkezésre állnak. Minden válaszhoz település, lekérdezés, időpont, ellenőrzőösszeg és licenc tartozik.
- `data/neighborhoods/catalog.geojson`: a geometriai ellenőrzésen átment, településhez köthető **ellenőrizetlen poligonjelöltek**. Ez nem hiteles országos városrésznyilvántartás.
- `data/neighborhoods/coverage.json`: a tényleges találatok, a 26 elsődlegesen vizsgált város, a hiányok és a kihagyott rekordok indoklása. A poligonok száma nem lefedettségi százalék.
- `data/neighborhoods/review.html`: önálló, internetkapcsolat és térképszolgáltató nélkül megnyitható ellenőrző oldal. Város és név szerint lehet kiválasztani, megrajzolni és az eredeti forráshoz visszakövetni az alakzatokat.

## Újraépítés

Nincs szükség npm-csomagra, Google-kulcsra, MySQL-re vagy futó backend­re:

```sh
node scripts/neighborhoods/build.mjs
node scripts/neighborhoods/build.mjs --check
node scripts/neighborhoods/preview.mjs
node tests/neighborhoods.test.mjs
node tests/neighborhoods-fetch.test.mjs
```

A HTML fájlt le lehet tölteni és közvetlenül megnyitni a böngészőben. A rajzhoz nem töltünk be alaptérképet, külső fontot vagy követőkódot. A forrásoldalak csak a forráshivatkozás megnyitásakor töltődnek be.

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

A feldolgozás nem alakít városrész-névpontot, befoglaló téglalapot vagy önkényes sugarú kört határvonallá. Ellenőrzi a gyűrűk zártságát, koordinátáit, elfajulását, önmetszését, lyukait és a megadott befoglaló keretet. Az eredeti geometria ellenőrzés közben nem változik. A forrásfájlok pontos bájttartalma ellenőrzőösszeggel visszakövethető.

Ezek az ellenőrzések önmagukban nem igazolják a városrész nevét, aktualitását, hivatalosságát, a külön területek egymás közötti átfedésmentességét vagy a házszintű besorolás helyességét. A Who's On First állományban például történelmi elnevezések, téves fordítások és hiányos szülőkapcsolatok is vannak. A fordító eltérő jelentésű fordítást nem cserél automatikusan az eredeti név helyére.

Kézi kiegészítésnél először önkormányzati határozatból vagy más megbízható leírásból kell azonosítani a határoló utcákat. A megfelelő utcaszakaszokat szabadon újrahasználható térképadatból lehet összeállítani és a kereszteződéseknél összekapcsolni. Google-térkép vagy kereskedelmi adatállomány átrajzolása nem része ennek a gyűjteménynek. Egy szabadon olvasható PDF nem automatikusan nyílt licencű vektoradat.

### Debrecen – Sestakert, előkészített források

- [Önkormányzati városfejlesztési vizsgálat, 2021–2027](https://hbmo.hu/portal/wp-content/uploads/2023/12/01A_eloterj.mell_DMJV-FVS-2021-27-megalapozo-vizsgalat.pdf), nyomtatott 208. oldal: a történelmi városrészek határtérképe; Sestakert a 48. elem.
- [Dehir helytörténeti cikk, 2022. november 17.](https://dehir.hu/debrecen/regi-debreceni-kertsegbe-kalauzol-nyul-imre/2022/11/17): Nádor utca, Thomas Mann utca, Mikszáth Kálmán utca, Békessy Béla utca, Dóczy József utca, Egyetem sugárút és Füredi út határolják.
- [Önkormányzati határozatok reprodukált melléklete](https://dea.lib.unideb.hu/server/api/core/bitstreams/9c8c07c6-2cd6-4731-8990-2047162be997/content), nyomtatott 140–143. oldal: a 92/2004. (IV. 22.) és 282/2005. (XI. 17.) határozat Sestakertet a 19. városrendezési körzethez kapcsolja.

A friss OSM-lekérésben Sestakert tényleges határrelációja is megtalálható: [17519326](https://www.openstreetmap.org/relation/17519326). Az első sikeres debreceni export 26 városrészt tartalmazott. Sestakert poligonja 110 forráscsúcsból áll, a gyűrű hiányzó szakasz hozzárajzolása nélkül zárható. A feldolgozás ezt a valódi határt használja; az utcanevek felsorolásából nem gyárt koordinátákat.

A végső ellenőrzéshez a határutcák két oldalán és a kereszteződéseknél is mintacímeket kell vizsgálni. Az út középvonala és a hivatalos városrészhatár eltérhet. A `manual-definitions.json` megőrzi a kézi forrásfeltárás eredményét és a hátralévő ellenőrzést.

## Licenc és költség

A Who's On First saját munkájának CC0 jelölése nem váltja ki az eredeti adatforrások feltételeit. A teljes forráslicenc megmarad a gyűjtemény mellett; a Quattroshapes és más CC BY források megjelölése kötelező. Az OSM-ből származó adatokra az [ODbL és az OpenStreetMap forrásmegjelölése](https://www.openstreetmap.org/copyright) vonatkozik. A külön eredetű forrásállományokat külön kezeljük; az összesített jelöltgyűjtemény közlésénél minden alkalmazandó feltételt meg kell tartani.

A saját adatbázisban tárolt határok használata nem igényel minden megjelenítéskor külső határadat-lekérdezést. A későbbi címkoordináta-keresés és az alaptérképcsempék kiszolgálása ettől külön szolgáltatás; az alkalmazás teljes térképes működésének ingyenességét ez az adatgyűjtés önmagában nem garantálja.
