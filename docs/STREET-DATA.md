# Magyar Posta közterületnév-katalógus

A Magyar Posta Partner Extra 2026. november 18-án letöltött országos
`StreetNames.xml` állományát változatlan XML-tartalommal, tömörítve megőrizzük a
`data/streets/sources/StreetNames.xml.gz` fájlban. A belőle képzett
`dist/data/streets.json.gz` **123 354 közterület-azonosságot** tartalmaz,
**mind a 3155 kanonikus településen**. Mind a **124 188 forrássor** feldolgozott;
nincs kihagyott vagy ismeretlen településnév.

## Forrás és felhasználás

- Szolgáltató: **Magyar Posta Zrt., Partner Extra**.
- [Hivatalos adatközlő oldal](https://www.posta.hu/partnerextra).
- [Mezőleírás és frissítés](https://www.posta.hu/partnerextra_leiras), különösen
  a 4.3. `StreetNames.xml` és a 6. Frissítések szakasz.
- Az adatközlő oldalon ténylegesen szereplő forráslink:
  <http://httpmegosztas.posta.hu/PartnerExtra/Out/StreetNames.xml>.
  Az oldal HTTP-linkjét változtatás nélkül rögzítjük.
- Letöltés: **2026-11-18 20:04:19 UTC**. Az XML 12 613 459 bájt;
  SHA-256: `e6ce188aa0c01399eb31ea8385cebce94292af0890d8d72a663fd5d41f0005ca`.
- A hiteles adatforrás elérését a
  [44386982485 számú GitHub Actions futás](https://github.com/st-agnes/ingatlan/actions/runs/44386982485)
  végezte korlátozott méretű és idejű letöltésekkel. A forrás URL-jét előbb a
  hivatalos oldal linkjei között ellenőrizte. A pontos adatok, az oldalak
  tartalmi hash-ei és a letöltési művelet azonosítói: `data/streets/source.json`.

A Magyar Posta az adatközlő oldalon ezt írja:

> „Az adatok letölthetőek és saját alkalmazások háttér-adatbázisaként
> felhasználhatók (webshop, vállalatirányítási rendszer stb.).”

Az oldal a szolgáltatásról azt is közli, hogy „A szolgáltatás díjmentes.”;
a közterületnév-állományt pedig így írja le: „A Magyarországon található összes
közterület nevének felsorolása.” E szolgáltatói felhasználási engedélyre
hivatkozunk; nem rendelünk az adathoz saját vagy kitalált CC/MIT-licencet.
A szolgáltató megjelölése a keresési választó mellett és a harmadik féltől
származó adatok jegyzékében is szerepel.

A mezőleírás szerint az adatbázis naponta frissül. A tárolt fájl verziózott
pillantkép: futás közben nincs automatikus Posta-letöltés, és a dátum után
keletkezett változásokat nem állítjuk benne szereplőnek.

## Ellenőrzött tartalom és feldolgozás

A gyökérelem `streetNames`; 124 188 darab `street` rekord szerepel benne.
Minden rekordnak pontosan egy `ZipCode`, `city`, `name`, `type` eleme van.
Az irányítószám négy ASCII-számjegy. A települések írásmódja mind a 3155
esetben közvetlenül egyezik a meglévő `dist/data/settlements.json`
katalógussal; nincs kézi település-átnevezés vagy kikövetkeztetett hozzárendelés.

| Ellenőrzés | Eredmény |
| --- | ---: |
| Forrássorok | 124 188 |
| Egyedi közterület-azonosságok | 123 354 |
| Megőrzött közterület–irányítószám párok | 124 188 |
| Több irányítószámú közterület | 705 |
| Ismételt, azonos közterület–irányítószám sor | 0 |
| Lefedett kanonikus települések | 3155 / 3155 |
| Ismeretlen vagy hiányzó települések | 0 |

Az audit településenkénti forrásszámai és kivételei a
`data/streets/coverage.json` fájlban ellenőrizhetők. A lefedettség a letöltött
országos névjegyzékre vonatkozik, nem az egyes házszámok létezésére.

A közterület-azonosító `street:` és 24 hexadecimális számjegy. A SHA-256
bemenete a `[település, kerület_vagy_üres_szöveg, név, típus]` kompakt UTF-8
JSON-tömbje; a település, név és típus NFC-normalizált, összevont szóközű,
kisbetűsített (`casefold`) szöveg. Az ékezeteket az azonosság megőrzi.
Az irányítószám nem része az azonosítónak, ezért az egy kerületben vagy
településen több postai körzetbe eső utca egyetlen választás marad, minden
forrásbeli irányítószámával. Például a XI. kerületi Bartók Béla út egyetlen
`street:cf625e9eb4715d7593eb8de3` rekord, a `1111`, `1113`, `1114`, `1115`
irányítószámokkal. Az eredeti írásmód-változatokat az `aliases` mező és a
teljes forrásarchívum őrzi; házilag kitalált névváltozatokat nem adunk hozzá.

### Budapest és a postai kivételek

A forrás nem tartalmaz külön kerületmezőt. A szokásos `1ddz` budapesti
közterületi irányítószámnál a `dd=01..23` rész képezi a kerületet, ha az
utolsó számjegy `1..9`. Ez postai besorolásból képzett keresési metaadat,
nem közigazgatási határvonal vagy címkoordináta. A különböző kerületekben
szereplő azonos nevű utca külön azonosítót kap.

**130 forrássor** kivételes postai kódot használ, ezért ezek kerülete
`null` marad. Nem következtetünk kerületre az utcanévből:

| Irányítószám | Forrássorok |
| --- | ---: |
| 1007 | 2 |
| 1826 | 31 |
| 1836 | 45 |
| 1838 | 11 |
| 1857 | 14 |
| 1871 | 27 |

Ezek a rekordok a budapesti, illetve országos névkeresés részei maradnak.
Kizárólag a nem igazolt kerületi hozzárendelést hagyjuk üresen.

## Futásidejű formátum

A gzip egy JSON-tömböt tartalmaz: `[fejléc, rekord, rekord, ...]`.
A .NET soronként olvashatja a tömörített állományt.

- Fejléc: `schemaVersion`, `datasetVersion`, `sourceSha256`, `count`, `stats`, `source`.
- Rekord: `id`, `city`, `district`, `name`, `type`, `streetName`, `label`,
  `postalCodes`, `aliases`.
- A `district` római számos, ponttal zárt szöveg (például `"XI."`) vagy `null`.
- A `postalCodes` minden rekordnál nem üres, rendezett és ismétlésmentes tömb.
- A `datasetVersion` a `[1, forrás_SHA256, végleges_rekordok]` kompakt UTF-8
  JSON SHA-256 azonosítója. Az adatátalakítás megváltoztatása is új verziót ad.
- Jelenlegi adatkészlet-verzió:
  `e397f60ecfbbd8c0708137d9f87e19bb3f6634917a3cab7b594f6c1d1ff7a0a7`.

A `dist/street-demo-data.js` csak 12, ugyanebből az állományból képzett valódi
utcanév-metaadatot tartalmaz a fiktív demópéldákhoz. Ez nem országos katalógus.
Az utcaforrásban **nincs házszám, koordináta vagy utcageometria**. A név
kiválasztása nem igazol egy konkrét címet és nem helyettesíti a külön
tulajdonosi címgeokódolást. A meglévő 4308 környékpoligon nem része ennek
az adatfeldolgozásnak.

## Újragenerálás és frissítés

Az ellenőrzés és az újragenerálás offline, csak a Python standard könyvtárával
működik:

```sh
python3 scripts/import-streets.py --check
python3 tests/street-data.test.py
```

A `--check` ellenőrzi a forráshash-t, az előre rögzített sor- és
közterületszámot, valamint az archívum, a futásidejű gzip, az audit és a kis
demómodul determinisztikus egyezőségét. Kapcsoló nélkül újragenerálja ezeket.

Frissítéskor előbb az adatközlő oldal hivatkozását, felhasználási engedélyét és
a mezőleírást kell újra ellenőrizni. A letöltést idő- és méretkorláttal kell
elvégezni. Ezután ellenőrizni kell az XML tényleges rekord- és mezőszámait,
a települési lefedettséget és a budapesti postai kivételeket; a `source.json`
hash-ét, dátumát, darabszámait és a dokumentációt együtt kell frissíteni.
Ugyanebben a változtatásban frissíteni kell a
`backend/Otthonra.Api/StreetCatalog.cs` `ExpectedSourceSha256`, `ExpectedCount`
és `ExpectedDatasetVersion` rögzített ellenőrzőértékeit, valamint a
`tests/street-data.test.py` forráshoz kötött regressziós ellenőrzőértékeit is.
Az új, már ellenőrzött forrásból a
`python3 scripts/import-streets.py --source /tmp/StreetNames.xml` parancs
készíti el az archívumot és a származtatott adatokat. Ismeretlen település
vagy hibás rekord megszakítja az előállítást; ilyen sort nem dobunk el
csendben, és nem társítunk találgatással egy másik településhez.
