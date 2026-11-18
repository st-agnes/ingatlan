# Miskolc és Ózd: következő gyűjtési csomag

50 bemeneti alakzat, pont köré rajzolt pótlás nélkül: Miskolc 26, Ózd 24. A teljes csomag a `features.geojson`; a városonkénti GeoJSON-ok ugyanennek a két részhalmazai, ezért egy összevonásba a teljes fájlt vagy a két városi fájlt kell felvenni, nem mindhármat.

Miskolcnál a korábban megőrzött önkormányzati 17-csoportos térképet és a hozzá tartozó városrészleírásokat használjuk. Két teljes csoport más elnevezése névváltozatként szerepel; a kisebb lakótelepi és domboldali területek belső elválasztói kézzel becsült, kifejezetten durva szektorok. Lillafüred és Ómassa–Jávorkút szétválasztása is becslés a közös forráscsoporton belül, nem az eredeti, külön nem közölt KSH-vonal.

Ózdnál a 2024. novemberi önkormányzati ITS teljes PDF-je, a 43–54. oldal eredeti térképképei és a kézi képpontkontúrok megmaradnak. A forrás fejlesztési akcióterületeket rajzol ki. Ezeket nem nevezzük át hamisan teljes városrészhatárrá: a városrészbecslések a tényleges utca-, beépítés- és völgyrajz alapján készültek. A p49 műholdképen közelítő helynévfelirat-kontrollokat, a p54 utcai térképhez közös körvonalsarkokat használtunk. Abszolút pontosságmérés nincs; a kis eltérések az alkalmazási becslés részei.

Minden alakzat érvényes Polygon/MultiPolygon WGS84 hosszúság–szélesség koordinátákkal. Az ismert saját névpontok beleesnek a hozzájuk tartozó becslésbe; ez technikai konzisztenciajelzés, nem a valós határvonal igazolása. A nagyobb és kisebb területek átfedése szándékos.

Újraépítés `numpy`, `pyproj`, `shapely` csomagokkal:

```sh
python3 data/neighborhoods/expansion-20261114-next/miskolc-ozd/build-miskolc.py
python3 data/neighborhoods/expansion-20261114-next/miskolc-ozd/build-ozd.py
```

A globális deduplikáció, tartós azonosítás és importálás a központi `build-search-areas.py` feladata. E csomag önmagában nem állítja egyik város teljes mai lefedését sem. Ózd külterületi/északi településrészeihez további térképi forráskutatás szükséges; a 2024-es városmag-térkép kiterjedésén kívül nem találtunk ki határt.

## Külön 2015-ös kiegészítés

Az `additional-features.geojson` további 7 ózdi alakzatot tartalmaz: a 2015-ös megalapozó vizsgálat 247. oldalának négy nagy városrészcsoportját, valamint Susa, Uraj és Szenna becsült lakott foltját. Ez a fájl a változatlan első 50 mellé vehető fel. A színes térképen látható nagy körvonalak megmaradnak, a színes feliratdobozok nem kerülnek a geometriákba. Az egész térkép elhelyezése durva becslés; a képi illesztés 13 egyező utcahálózati foltot használ, a helynévfeliratokkal végzett végső illesztés nem jelent független pontosságellenőrzést.

A három kisebb foltnál a forrás völgyes településszerkezetének alakját használtuk fel, és a meglévő helynévponthoz igazítottuk. A név és a képi folt kapcsolata is becsült. Ezek nem hivatalos, teljes külterületre kiterjedő határok, és nem egyszerű sugaras körök. A nagy és kisebb egységek átfedése itt is szándékos. A 2015-ös teljes PDF és az eredeti térképkép megmarad a csomagban.

**A `ozd-2015-native-pixel-polygons.geojson` kizárólag forrásképpont-koordinátát tartalmaz. Ez nem WGS84, az alkalmazás földrajzi katalógusába közvetlenül nem importálható.**

A kiegészítés reprodukálása `numpy`, `scipy`, `Pillow`, `pyproj`, `shapely` csomagokkal:

```sh
python3 data/neighborhoods/expansion-20261114-next/miskolc-ozd/extract-ozd2015-native.py
python3 data/neighborhoods/expansion-20261114-next/miskolc-ozd/build-ozd2015-additional.py
```

A későbbi folytatás fő hiányai Ózdon: a 2015-ös vizsgálat részletes külső településrészi térképei (pl. Bánszállás, Center), illetve a jelenlegi 50+7-en kívüli kisebb nevek. A négy nagy csoport megléte nem jelenti az összes belső név külön határának elkészültét.
