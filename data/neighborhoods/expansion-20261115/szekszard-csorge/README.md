# Csörge-tó – külön keresési területbecslés

Az egyetlen importálandó fájl a `features.geojson`: egy WGS84 Polygon, alacsony biztonságú, kézzel becsült városrészi keresési terület. Javasolt forrásprioritása **30**, hogy a korábbi, 40-es prioritású szó szerinti tókontúr forrásalternatívaként megmaradhasson.

A becslés a tavat és a Nyámándpuszta felőli szomszédos szárazföldet, valamint a Bogyiszlói út keleti megközelítését együtt fogja át. A nyugati megközelítés a Bogyiszlói út tényleges vonalát követi a Galamb utcai csomópont közelében; a keleti oldalt tényleges útcsúcsok és a Sárközi-összekötőcsatorna fordulói támasztják alá. A kert- és szántóföldi szakaszokat összekötő elválasztók kézi becslések. Minden forráscsúcs és becsült összekötés külön megjelölést kap a `source-anchors.json` fájlban.

A 0,458 km²-es alakzatból 0,440 km² szárazföld. Így a keresés az útközeli szárazföldi címeket is elérheti, a teljes területet nem vízfelületre korlátozza. Nem hivatalos, nem kataszteri pontosságú határ, a szomszédos ipari és külterületi egységekkel átfedhet. Nem készült kör, pontból származtatott sugár vagy téglalap.

A `source-context.geojson` eredeti OSM-utakat és vízrajzi alakzatokat tartalmaz. A korábbi 20 alakzatos csomag változatlan maradt. Újraépítés helyi forrásokból, `shapely` és `pyproj` csomagokkal:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/szekszard-csorge/build.py
```

© OpenStreetMap contributors, ODbL-1.0.
