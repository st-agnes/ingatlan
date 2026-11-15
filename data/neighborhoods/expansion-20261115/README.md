# Városrészgyűjtés – 2026. november 15.

Kiinduló mentés: `27dbf56e252674c69b8029801e1510af814035bd`, 3404 kiválasztott
terület 564 településen, 861 külön pontból becsült tartalékkörrel.

A kör célja a korábbi név szerinti hiányok pótlása: elsőként Budapest,
Nyíregyháza és Szombathely, továbbá Ózd, Szekszárd és további települések.
Makó és Mosonmagyaróvár önálló kiegészítő csomagot kap.

- Az aktuális állapot, a kész csomagok és a folytatandó feladatok:
  [WORK-STATE.json](WORK-STATE.json).
- Az összevont, név szerint egyesített eredmény:
  [kereshető területek](../search-areas.geojson),
  [darabszámok településenként](../search-areas-report.csv).
- A teljes aktuális, importálható adatcsomag:
  [ZIP](../../../downloads/neighborhoods/otthonra-keresheto-varosreszek.zip).

## Források és becslések

A változatlan gépi poligonok mellett forrástérképből, utcahatár-leírásból,
tényleges úthálózatból és beépített felszínekből becsült területeket gyűjtünk.
A történeti és eltérő részletességű felosztások átfedhetnek. Az azonos nevű,
azonos helyet jelölő forrásváltozatokból egy kerül a fő rétegbe; a bizonyított
névváltozat kereshető alias, a különálló szülő- és részterületek megmaradnak.

Minden csomagnak saját `README.md`, forrásbizonyíték, építőprogram és összesítő
jelentés tartozik a poligonjaihoz. Csak az `input-registry.json` fájlban
ellenőrző összeggel regisztrált, befejezett WGS84-rétegek kerülnek a fő exportba.
A képpontkoordinátás munkafájlok és az alternatív jelöltek nem automatikus
importforrások. A teljes letöltött dokumentumok URL-jei és SHA-256 összegei a
`downloaded-sources/acquisition-status.json` állományban vannak; sikertelen régi
URL-eket is őrzünk, ezek nem bizonyítják egy forrás végleges elérhetetlenségét.

## Mit nem jelentenek a darabszámok?

Egy névhez gyűjtött poligon nem feltétlenül fedi a teljes városrészt.
Az úthálózati cellák kisebb tömbcsoportok lehetnek; egyes külterületi neveknél
csak a ténylegesen térképezett tanyaudvarok beépített felszíne ismert.
Ezek `estimated`, `lowConfidence` vagy `confidence: low`, illetve `partialSourceFootprint` vagy
`partialSettlementFootprint` jelölést kapnak. A fő export megőrzi ezeket a
`sourceProperties` mezőben, a forrásokkal és az egyedi indokolással együtt.
Az ismert névjegyzék feldolgozottsága ezért nem azonos a teljes országos
vagy egy adott városon belüli területi lefedettséggel.

Térképi forrás és névpont eltérésekor a bizonyítékkal alátámasztott területet
nem növeljük meg pusztán a névpont befogadásához. Az eltérést külön jelöljük.
A technikai ellenőrzés a geometriák érvényességét és az azonosítók
egyediségét vizsgálja; nem igazol jogi vagy ingatlan-nyilvántartási pontosságot.

Ez továbbra is **adatgyűjtés és import-előkészítés**. A csomagok létrehozása
nem telepíti az alkalmazást és nem módosítja a Cloud-adatbázist.

## Folytatás megszakítás után

Őrizzük meg a kész csomagokat és a stabil azonosítókat. A munkafolyamat:

1. A kész fő rétegek útvonala és SHA-256 összege az előző napi
   `expansion-20261114/input-registry.json` fájlba kerül; a regiszter továbbra
   is közös, nem kell naponta új katalógust létrehozni.
2. `build-search-areas.py --update-identities`, majd az inventory és a külön
   tartalékkörök újraépítése.
3. `checkpoint-search-areas.py` frissíti a munkafolyamat állapotát, a technikai
   jelentést és a ZIP-et. Ellenőrizzük a fő exportot, a 13 adatfeldolgozási
   regressziós tesztet és a ZIP ellenőrző összegeit.
4. Commit és push a `codex/neighborhood-research-506-191` branchre.

Az országos gyűjtés nincs lezárva; a fennmaradó nevek az inventory
`known-names.json` és `municipality-backlog.json` állományaiban folytathatók.
