# Budapest: első bővítési csomag

30 új keresési névhez van poligon: 28 tényleges OSM-felület körvonalát rendeltük a benne található helynévhez, két tágabb keresési terület pedig a kerülethatárok uniója (Buda és Pest).

A lakóterületi, ipari, kert- és parkfelületek koordinátái változatlanul a forrásból származnak. A név és a felszín társítása becslés: nem állítjuk, hogy a felszín megegyezik a teljes köznyelvi városrésszel. Több névpont egy felszínen nem kizáró ok, mert a keresési nevek kisebb és nagyobb, illetve történeti egységeket is jelölhetnek. Minden forrásváltozat megmarad a `footprint-raw-features.geojson` fájlban. Kör, puffer és Voronoi nem készült.

A nagyterületi konvenció: Buda az I., II., III., XI., XII., XXII. kerület együtt; Pest a többi fővárosi kerület együtt, Csepellel és Soroksárral. Ez a mai ingatlankeresési tájolást szolgáló tág becslés, nem az egyesítés előtti történeti városok határa. A külön kerületek és városrészek továbbra is megmaradnak.

A 30 alakzat már rögzített, az újabb Óbuda-térképi levezetések külön fájlba kerülnek. A forrásnévpontok és kerületgeometriák is itt maradnak. A PBF nélküli, byteazonos újraépítés:

```sh
python3 collect-footprints.py --saved-sources
```

Az újraépítéshez `osmium` és `shapely` csomag kell. Az eredeti országos PBF SHA-256-a a forrásrekordokban szerepel; a kutatási munkakörnyezetben ez `/workspace/ingatlan/.local/neighborhoods/hungary-latest.osm.pbf`. Az OSM forrás URL-je, objektumazonosítója, címkéi és ODbL-jelölése minden tényleges felületnél megmarad.

## Óbudai finomabb becslések

Az `additional-features.geojson` további 16 nevet fed le. A 2009-es önkormányzati IVS már 13 tágabb csoportot használ; **nem állítjuk, hogy a 16 kisebb terület határvonala ebben a dokumentumban meg lenne rajzolva**. A kisebb területeket az ottani szöveges/táji összefüggések és a jelenlegi OSM-utcatérkép alapján kézzel becsültük. A konkrét elválasztások bizonytalanok, de valódi utcákhoz, vasutakhoz és vízfolyásokhoz kötött térképi alapjuk van.

Megmarad mind a 9712 felhasznált forrásútvonal, a georeferált utcatérkép, a kézi képpontkontúrok, a teljes 2009-es PDF és az újraépítő program. A térkép földrajzi elhelyezése közvetlenül az OSM koordinátáiból következik; az egyes becsült városrészhatárok pontosságát külön mérés nem igazolja.

```sh
python3 build-obuda-estimates.py
```

A 30-as és 16-os fájl összesen 46 különböző nevű keresési területet ad, körpótlás nélkül. Az országos összevonásba csak a `features.geojson` és az `additional-features.geojson` kerüljenek; a többi GeoJSON forrás- és köztes állomány.
