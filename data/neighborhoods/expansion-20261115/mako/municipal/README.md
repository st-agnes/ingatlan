# Makó – nyolc nagy önkormányzati városrészcsoport

A `features.geojson` nyolc érvényes WGS84 alakzatot tartalmaz. Az önkormányzati FVS 282. oldalának 43. ábráján látható tényleges színes körvonalakat kézzel, durván követtük. A hét hozzávetőleges térképi csoportszám és a már ismert OSM-névpont alapján számított affin illesztés 167 m RMS maradékot ad; ez nem független földrajzi pontosságmérés. Minden alakzat kifejezetten alacsony biztonságú becslés, és átfedhet kisebb történeti városrészekkel.

A forrás Városközpont csoportját a Belváros névhez közelítően társítottuk. Ez nem két pontos határú névváltozat igazolása. Az Üdülőtelep a Maros-parti üdülőterület forráscsoporthoz tartozik. A forrás Iparterület elnevezése az Ipari terület célnévvel szerepel.

A `source-traces.json` és `native-pixel-polygons.geojson` csak forrásképpont-koordinátát tartalmaz, nem WGS84; alkalmazási importba közvetlenül nem vehető fel. A nyolc alakzatot önmagukban a `features.geojson` adja; a szülő Makó-csomag ezeket ugyanúgy tartalmazhatja, ezért a két összesítést ne importáljuk egyszerre.

Újraépítés kizárólag helyi fájlokból, `numpy`, `pyproj`, `shapely` csomagokkal:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/mako/municipal/build.py
```

Forrás: [Makó FVS](https://mako.hu/wp-content/uploads/2024/04/melleklet-fvs-mako-0706-fin-30.pdf), 282. oldal, 43. ábra; a teljes PDF a közös `downloaded-sources/mako-fvs2024.pdf`, eredeti beágyazott képe a szülőmappa `fvs-p282-image1.jpeg` fájlja. Az illesztési névpontok OSM-forrásai és maradékai a `registration.json` fájlban szerepelnek. OSM: © OpenStreetMap contributors, ODbL-1.0.
