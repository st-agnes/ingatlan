# Ózd és Szekszárd – 2026-11-15

A csomag 20 alakzatot tartalmaz: Ózd 10, Szekszárd 10. A `features.geojson` a csomag egyetlen összevonandó bemenete; a részfájlokat ugyanabban az importban ne vegyük fel újra. Minden koordináta WGS84 hosszúság–szélesség. Az alakzatok tudatosan alacsony biztonságú becslések: nem hivatalos vagy mai kataszteri határok, és a nagyobb, kisebb vagy szomszédos területek átfedhetnek.

Ózd nyolc belső nevéhez a megőrzött 2024-es önkormányzati ITS 54. oldalának tényleges utca- és tömbrajzán kézzel húzott, durva kontúr készült. A korábbi képi illesztést változtatás nélkül használtuk; a helynévpontok csak a névazonosítást segítik, nem határoznak meg sugarat vagy téglalapot. A fejlesztési akcióterületek színes kitöltését nem nevezzük át egész városrészhatárrá.

Bánszállás és Center esetében a 2015-ös önkormányzati vizsgálat 250., 277. és 283. oldalának helynévi/utcai bizonyítékát a 2026-11-12-i OSM tényleges utcáival és épületsoraival kapcsoltuk össze. A becslés a lakott foltot követi; a statisztikai szegregátum piros négyzetrácsos felülete nem került teljes városrészként átcímkézésre. Az eredeti oldalképek és az utcai áttekintő ábra megmaradnak.


Szekszárd nyolc városrésze a 2025. novemberi önkormányzati SUMP 49. oldalán közölt, a Településképi Arculati Kézikönyvből átvett térkép **tényleges zárt körvonala**. A 527×582 képpontos eredeti PDF-képet megőriztük. A fehér, összefüggő belső tartományokat digitálisan emeltük ki; csak a belső számozás lyukai lettek kitöltve. A külső kontúrokból nem készült kör, téglalap vagy mesterséges szektor. Hat hozzávetőleges térképi névfelirat és OSM-névpont alapján durva affin elhelyezés készült; az illesztési maradék RMS értéke 112 m, ami **nem független földrajzi pontosságmérés**. A sematikus forrás és a feliratok eltolása miatt ezek is alacsony biztonságú becslések.

Palánkihegyhez a tényleges Borkút/Pál/Bor utcák és a Fuksz/Faddi-völgyi utak által kirajzolt domboldali-szőlőskerti folt készült. Csörge-tónál a szó szerinti, névvel ellátott OSM-tókontúr szerepel keskeny forráslábnyomként: **a tó körüli nagyobb városrész teljes határa nincs megállapítva**. Ez a két név nem szerepel külön körvonalként a SUMP 13-as városrészábráján.

A `szekszard-native-pixel-polygons.geojson` kizárólag forrásképpont-koordinátákat tartalmaz; nem WGS84, közvetlenül nem importálható. A `szekszard-features.geojson` és `ozd-outer-features.geojson` az összesített fájl részhalmazai. A nagy utcai és épületforrások veszteségmentes gzip archívumban maradnak.

Újraépítés a `numpy`, `scipy`, `Pillow`, `pyproj`, `shapely` csomagokkal, kizárólag helyi fájlokból:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/ozd-szekszard/build-ozd-outer.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/ozd-szekszard/build-szekszard-extra.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/ozd-szekszard/build-szekszard.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/ozd-szekszard/build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/ozd-szekszard/validate.py
```

A `summary.json` a geometriák ellenőrzését és a névlistát adja. A forráspont befoglalása technikai konzisztenciajelzés, önmagában nem földrajzi pontosságigazolás. Az OSM források licence ODbL-1.0, forrásmegjelölés: © OpenStreetMap contributors. A magyarországi PBF SHA256 értéke `224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a`.
