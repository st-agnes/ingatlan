# Budapest: újabb eredeti OSM admin10 archívum

Ez a forrás **202 budapesti városrész valódi Polygon geometriáját** tartalmazza, WGS84 (EPSG:4326) GeoJSON formában. A 2022-es forrást külön megőriztük; ez az újabb állomány nem írja felül az eredeti forrásfájlokat.

Az [eredeti magyar OSM közigazgatásihatár-export](http://data2.openstreetmap.hu/hatarok/kozighatarok.zip) tükre Ferenci Tamás [BudapestiElerhetoseg tárolójának rögzített ZIP fájlja](https://github.com/ferenci-tamas/BudapestiElerhetoseg/blob/2f7a91ee1f320e6a08488ef8413715be13abf226/kozighatarok.zip). A forráscommit dátuma **2025. augusztus 28.** Ez a tükrözés dátuma; az eredeti OSM-kivágás pontos időpontja ismeretlen.

Az archívumot letöltés után, kibontás előtt ellenőriztük:

- Méret: `6285474` bájt.
- Git blob SHA1: `e7f24b8ef283cffee740cd3cd3a3c3ec16b71d0d`.
- SHA256: `2c38117de636dc03d7452db14ecb6c8e66a426e05e2a6d7c8932717bf609db7a`.

Az archívumból az öt eredeti `admin10` shapefile-összetevőt változtatás nélkül megőriztük. A `manifest.json` mindegyik bájtméretét, SHA256 és Git blob SHA1 tartalomlenyomatát tartalmazza. Ezek a komponenslenyomatok helyben számolt tartalomazonosítók; a tükörtároló a komponenseket a ZIP belsejében, nem külön Git objektumként publikálja. A ZIP nincs ebben a könyvtárban megismételve, a rögzített URL-ről a `scripts/neighborhoods/fetch-national.py` ellenőrzötten letölti.

**Forrásmegjelölés:** © OpenStreetMap contributors. A térképadatok licence [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), [OSM copyright](https://www.openstreetmap.org/copyright). A tükröző elemzőkód GPL licence nem helyettesíti az eredeti térképadatok licencét.

A `convert.py` a korábbi forrás konvertálójának azonos geometriakezelését használja. Külső csomag és hálózat nélkül futtatható:

```sh
python3 data/neighborhoods/sources/national-osm-2025/convert.py
```

Az eredeti EPSG:3857 vetületű csúcspontokat alakítja EPSG:4326 formába, nyolc tizedesre kerekíti, és a gyűrűk irányát normalizálja. Nem helyettesít területet ponttal vagy befoglaló téglalappal. A shapefile nem tartalmaz OSM relation ID-ket, ezért a stabil azonosító az exporton belüli sorszámot őrzi: `osm-hu-20250828:admin10:REKORD`.

Az `archive-inventory.json` minden archívumbeli réteg rekordszámát, geometriatípusát és neveit tartalmazza. Az `admin10` 202 poligonja kizárólag Budapesthez tartozik; **vidéki városrész és admin11-réteg nincs benne**. Az `admin9` 23 budapesti kerület, az `admin8` 3175 település; ezek más területi szintek. A `bpplace` 220 és a `place` 3158 rekordja pontgeometria, városrészhatárként nem használható.

A 2022-es állományhoz képest `Magdolna negyed` neve itt `Magdolnanegyed`. `Millenniumtelep` geometriája hiányzik az újabb exportból; ezt a 2022-es forrásban megőriztük. A többi 201 név egyezik. A mai hivatalos határokat és a nevek jelenlegi létezését nem ellenőriztük egyenként; a nyers forrás státusza továbbra is történeti, ellenőrizendő geometria.
