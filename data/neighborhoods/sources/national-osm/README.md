# Budapest: eredeti OSM admin10 határvonalak

Ebben a könyvtárban **203 budapesti városrész valódi területi geometriája** szerepel. Az `admin10.geojson` egységes, WGS84 (EPSG:4326) GeoJSON; az eredeti öt shapefile-összetevőt is megőriztük. Az eredeti forrás nem tartalmaz OSM-azonosítókat, ezért az új azonosítók az eredeti rekord sorszámát őrzik.

Az eredeti export az [OpenStreetMap magyar közigazgatásihatár-állományából](http://data2.openstreetmap.hu/hatarok/kozighatarok.zip) származik. Az állományt Ferenci Tamás változatlan `kozighatarok` könyvtárából szereztük be, a [2022. november 23-i rögzített commitból](https://github.com/ferenci-tamas/MagyarorszagKozutiElerhetoseg/tree/7d3749a06d785d9329fc2f113c8fbc4cec43256a/kozighatarok). A tároló [README.Rmd fájlja](https://github.com/ferenci-tamas/MagyarorszagKozutiElerhetoseg/blob/7d3749a06d785d9329fc2f113c8fbc4cec43256a/README.Rmd) dokumentálja az eredeti letöltési URL-t. Az elemzés későbbi, feldolgozott település-geometriáit nem használtuk; Margitsziget külön városrész maradt.

**Forrásmegjelölés:** © OpenStreetMap contributors. A térképadatokra az [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) és az [OSM forrásmegjelölési feltételei](https://www.openstreetmap.org/copyright) vonatkoznak. A tükröző kutatás elemzőkódjának GPL licence nem helyettesíti az eredeti OSM térképadatok licencét.

A commit dátuma nem azonos egy dokumentált OSM-adatkivágási dátummal: az eredeti kivágás pontos időpontja ismeretlen. Ezek régebbi forrásgeometriák, jelenlegi hivatalos határként nem ellenőriztük őket. A városrésznevek mai létezésének egyedi ellenőrzése külön feladat. Ez az állomány kizárólag Budapestet fedi le, vidéki városrészt nem tartalmaz. A tükörben nincs admin11-réteg.

A `manifest.json` tartalmazza az összes fájl bájtméretét, eredeti Git blob SHA1 és SHA256 lenyomatát, a 203 nevet, a forrásokat és a korlátozásokat. Az eredeti fájlok Git blob SHA1 lenyomata egyezik a GitHub API által visszaadott lenyomattal.

Újra előállítható további csomag telepítése és hálózati kérés nélkül:

```sh
python3 data/neighborhoods/sources/national-osm/convert.py
```

A konvertáló a `.prj` szerinti EPSG:3857 vetületből képez EPSG:4326 koordinátákat, megőrzi az eredeti gyűrűket és azok lyuk/multipart kapcsolatát, majd a GeoJSON gyűrűirányt normalizálja. Nyolc tizedesre kerekít. Nem helyettesít geometriát befoglaló téglalappal vagy pont köré rajzolt területtel, és nem rajzol át kerületi határt.
