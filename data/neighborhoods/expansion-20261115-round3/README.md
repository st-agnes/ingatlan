# Központi területek pótlása – harmadik november 15-i kör

Kiinduló mentés: `9bfa53497ea417ee623e48bfebc4d8fca60da472`;
3899 kiválasztott terület 567 településről, 391 külön tartalékkörrel.

Elsőbbséget kap Hajdúböszörmény és Körmend Belvárosa, Mezőberény, Dabas és
Kisvárda Városközpontja. Dabason a nagyobb településrészeket, Körmenden a
fennmaradó lakóterületeket, Kisvárdán a hat funkcionális egységet is feldolgozzuk.
Mosonmagyaróvár Belvárosát külön kezeljük a már meglévő tágabb Magyaróvár-rétegtől.

## Elkészült csomagok

| Település | Új poligon | Kiemelt eredmény |
| --- | ---: | --- |
| Hajdúböszörmény | 1 | Belváros, a kilenc megnevezett önkormányzati határutca nyomvonalából |
| Körmend | 6 | Belváros és az öt további kijelölt lakóterület |
| Mezőberény | 1 | Városközpont, tizenhét utcából álló önkormányzati határleírásból |
| Dabas | 8 | Városközpont, Alsódabas, Felsődabas, Gyón, Sári és a többi kijelölt egység |
| Kisvárda | 6 | Városközpont és az öt további forrásbeli funkcionális egység |
| Mosonmagyaróvár | 2 | Önálló Belváros és szárazföldi Dunapart |
| Tokaj | 1 | Óváros, a forrásszöveg szerinti tágabb történeti terület |

Összesen 25 új poligonjelölt készült. Kisvárdán két, ugyanazon számozott
forrásegységhez tartozó névváltozat is rögzítve van; ezek nem további poligonok.
Mindegyik új alakzat becsült, alacsony bizonyosságú területként szerepel.
A teljes, közölt utcalista használata sem jelent felmért telekhatár-pontosságot.

A forrásokból levezethető teljes negyedhatár az elsődleges cél. Utcalistából,
történeti térképből vagy tényleges úthálózatból becsült körvonal is elfogadható,
ha a módszer és a bizonytalanság rögzítve van. A névpont önmagában nem indokol
körön kívüli kitalált alakzatot. Egy szülőterület megléte nem igazolja automatikusan
az azonosnak tűnő kisebb egység teljes lefedettségét vagy névazonosságát.

Az aktuális feladatok és a lezárt csomagok: [WORK-STATE.json](WORK-STATE.json).
A fő adat a közös [tömörített GeoJSON](../search-areas.geojson.gz);
a [településenkénti jelentés](../search-areas-report.csv) mindig az összevont,
név szerint egyesített aktuális katalógust mutatja. Az országos gyűjtés nem teljes.

## Forráskezelés

A korábbi csomagok archivált út-, felszín- és térképadatait újrahasználjuk.
Új bináris PDF-letöltés nem előfeltétel: webes elsődleges forrásszöveg vagy
megtekintett PDF-oldal is alapozhat durva, kifejezetten jelölt becslést.
Minden csomag közli, mit látott ténylegesen; nem állít nem megtekintett PDF-ből
végzett poligondigitalizálást. Az offline építéshez szükséges geometriák,
nyomvonalak és tények a csomagokban maradnak. A nagy nyers források szükség
esetén gzipben tárolhatók, az eredeti bájtok visszaállíthatók.

## Megszakítás után is folytatható mentés

Csak a befejezett WGS84-főrétegek kerülnek a közös, SHA-256-tal rögzített
`expansion-20261114/input-registry.json` fájlba. A stabil azonosítókat megtartjuk,
a régi változatokat alternatívaként őrizzük. Az építőprogram helyben előállítja
a tömörítetlen GeoJSON-t; Gitben a gzipet tároljuk. A teljes poligon a ZIP-ben
is benne van, a MySQL-import külön fájl.

A parancssori hálózati engedélykérések korábban hosszú ideig nem tértek vissza.
Ilyen hívásra ne alapozzuk a gyűjtés vagy a mentés haladását. A közvetlen
GitHub-kapcsolaton a teljes adatállomány és forrásarchívum már sikeresen menthető:

Az offline manifest-előkészítés a már beolvasott távoli fejjel:

```sh
python3 scripts/neighborhoods/prepare-api-publish.py --base <ellenorzott-tavoli-commit>
```

Ez a segéd önmagában nem ír GitHubra és nem változtat Git-referenciát. A
`.local/github-api-publish/` könyvtárban készít manifestet és kis UTF-8
fájlcsoportokat; a már az alapcommitban szereplő blobok új feltöltése elhagyható.
Megváltozott, nem commitolt fájllal vagy túl nagy új feltöltési törzzsel megáll.

1. Helyi commit és ellenőrzött Git-fa készül; a távoli branch fejét külön beolvassuk.
2. A GitHub `create_blob` művelete tartalom alapján azonosítja a nagyobb fájlokat.
   A kérés teljes törzse legfeljebb 16MiB, ezért a nagy generált adat gzipben marad.
   A feltöltött blob SHA-jának egyeznie kell a helyi Git-azonosítóval.
3. A `create_tree` a meglevő távoli fából, a kis UTF-8 fájlok tartalmából és a
   feltöltött blobokból épít. Eredménye pontosan egyezzen a helyi ellenőrzött fával.
4. Új commit készül, majd `update_ref` a korábban beolvasott branch-fejre vonatkozó
   egyezési feltétellel, erőltetett felülírás nélkül. A távoli commitot és a ZIP-et
   visszaolvassuk. A mentés nem küld üzenetet és nem telepít alkalmazást.

Csak a fő munkamenet végezzen GitHub-írást: a párhuzamos dolgozók feltöltési
hívásai korábban várakoztak, miközben ugyanezek a hívások a fő munkamenetből
eredményesen lefutottak. A dolgozók helyi, lezárt, hash-sel ellenőrizhető
csomagokat adjanak át.
