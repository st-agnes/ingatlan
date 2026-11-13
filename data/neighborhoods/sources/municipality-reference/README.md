# Településhatár-referenciák a városrész-hozzárendelés ellenőrzéséhez

Ez a külön referenciaállomány **hét település valódi határgeometriáját** őrzi. Budapest az eredeti országos OSM-export `admin6` rétegéből, Budaörs, Debrecen, Dorog, Esztergom, Sopron és Székesfehérvár az `admin8` rétegből származik. Ezek településhatárok, nem városrész-találatok; nem szabad őket a városrészek számába beszámítani.

Forrás: a `ferenci-tamas/BudapestiElerhetoseg` tároló [rögzített 2025-ös archívuma](https://github.com/ferenci-tamas/BudapestiElerhetoseg/blob/2f7a91ee1f320e6a08488ef8413715be13abf226/kozighatarok.zip), amely az eredeti magyar OSM közigazgatásihatár-exportot őrzi. A commit dátuma 2025-08-28; az eredeti OSM-kivágás pontos időpontja ismeretlen. © OpenStreetMap contributors, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), [OSM copyright](https://www.openstreetmap.org/copyright).

A `manifest.json` tartalmazza az egész ZIP ellenőrzött bájtméretét, Git blob SHA1 és SHA256 lenyomatát, az eredeti admin6/admin8 shapefile-összetevők külön lenyomatait, a kiválasztott rekordok sorszámát és a kimeneti GeoJSON ellenőrzőösszegét. A több megabájtos eredeti admin8 réteget nem ismételjük meg ebben a könyvtárban.

Reprodukálás a korábban ellenőrzötten letöltött archívummal:

```sh
python3 data/neighborhoods/sources/municipality-reference/extract.py --archive .local/neighborhoods/national-2025/kozighatarok.zip
python3 data/neighborhoods/sources/municipality-reference/audit.py
```

A kinyerés az archívumot is újra ellenőrzi, majd a `national-osm-2025/convert.py` tiszta geometriakezelő függvényeit használja: vetületváltás EPSG:3857-ről EPSG:4326-ra, nyolc tizedes, eredeti gyűrűk megőrzése. Az `audit.py` a már megőrzött aktuális OSM-forrásokat és a projekt saját `osmGeometry` feldolgozóját használja, hálózati kérés nélkül.

Az `association-audit.json` minden feldolgozható, tárolt OSM városrészjelöltre megadja a forrásfájl lenyomatát, a befoglaló téglalap középpontját és sarkait, a síkbeli területi súlypontot, valamint az egyedi csúcspontok referencia-településenkénti eloszlását. **A százalékok csúcspontarányok, nem területi átfedési százalékok.** Nem tanúsítják az összes él teljes befoglalását vagy a határok mai pontosságát. A 2025-ös referencia és a frissebb OSM kisebb határeltérései önmagukban nem kizáró okok.

Az Overpass települési keresőterületének metszése nem bizonyítja, hogy egy találat a lekérdezett városhoz tartozik. Konkrét példa az Esztergomhoz lekért, Dorog környéki Kolónia és ipari-gazdasági terület. Az audit diagnosztikát ad; a tényleges hozzárendeléshez a megbízható név- és települési bizonyítékot külön kell rögzíteni.
