# Vác és Kiskunfélegyháza – gyors térképi városrészbecslések

51 kimeneti alakzat: Vác 26, Kiskunfélegyháza 25. Az eredeti poligonok és a pontból rajzolt körök helyett itt látható önkormányzati térképek és utcaképi/vonalas térképi szerkezet alapján becsült kontúrok szerepelnek. Kör és Voronoi nem készült.

Vácnál az önkormányzati HEP 2023–2028 dokumentum 7. oldali térképe öt nagyobb színezett területet és sok névvel jelölt kisebb városrészt mutat. A nagyobb színezett területeket egyszerűsített kontúrral, a finomabb területeket a látható belső utcák/elválasztók, névkapcsolatok és a mai OSM-névpontok elhelyezkedése alapján, durva kézi elválasztással becsültük. A lakótelepek körvonala különösen közelítő utcatömb-becslés; nem állítjuk, hogy a térképen nyomtatott városrészhatár lenne.

Kiskunfélegyházán a 2016-os ITS 25. oldali térképe több zárt színes körvonalat, nagyobb összevont egységeket és külterületi úthálózatot ábrázol. Ezekből új tágabb egységek, a belterületen névvel azonosított finomabb részek és út-/mezőhatárokhoz igazodó durva külterületi részek készültek. A kombinált Déli Kertváros–Móraváros–Bikahegy terület és a három kisebb rész külön név alatt, szándékos átfedéssel szerepel. A forrástérkép régi Halesz-kontúrja és a mai névpont jelentősen eltérő helyre utal; a kimeneti Halesz ezért új, alacsony bizonyosságú külterületi út-/mezőhatár-becslés, nem a régi nyomtatott körvonal másolata.

Az elhelyezéshez a már archivált hárompontos váci és ötpontos kiskunfélegyházi EOV-affin illesztést használjuk. A képpontok, a teljes transzformációs mátrix, az eredeti natív forrástérképek, a névpontok és a feldolgozó program itt megmaradnak. A mostani új, közelítő belső elválasztók nem jogi vagy felmért határok; a régi térképek mai pontosságát nem igazoltuk. Egyes finom részek és szülőterületek átfedése szándékos.

Fájlok:

- `features.geojson`: a teljes 51 alakzat.
- `vac-features.geojson`: a változatlanul lefagyasztott 26 váci alakzat.
- `kiskun-features.geojson`: a 25 kiskunfélegyházi alakzat.
- `trace-specifications.json`, `registrations.json`: minden kézzel megadott csúcspont és a koordináta-transzformáció.
- `*-source-map.*`, `*-trace-overlay.png`: natív forrásképek és áttekintő kontúrábrák.
- `name-points.geojson`: a kapcsolódó jelenlegi névpontok eredeti forráshivatkozással.
- `validation.json`: technikai érvényesség, új nevek és kiváltható körök az adott bemeneti katalógushoz képest.

Újraépítés `numpy`, `pyproj` és `shapely` csomagokkal:

```sh
python3 data/neighborhoods/expansion-20261114-next/medium-cities/build.py
```

A részletezett, régebbi forráskivonatok a `sources/municipal-vac-hep2023-next/` és `sources/municipal-kiskunfelegyhaza-its2016-next/` könyvtárban maradnak. A mostani munka csak ezt az új csomagot írja; a központi név szerinti összevonást és GitHub-mentést a fő munkafolyamat végzi.

## Pápa – további 21 alakzat

A `papa-features.geojson` külön lefagyasztott csomag, nem módosítja a fenti 51 alakzatot. A 2015-ös önkormányzati ITS 120. oldalán levő színezett városrésztérkép natív képe 719×832 képpont. A nagyobb területek egyszerűsített, kézzel követett színkontúrjai és az ismertetett utca szerinti határok adják az alapot. A lakótelepi alrészek a térképen látható utcatömbök és a kapcsolódó névpontok alapján becsült belső felosztások; a forráskép nem állít külön határt mindegyik lakótelephez.

Négy, a forrásképen megkülönböztethető lakótelepi jelölő és a mai megfelelő névpont segíti az EOV-affin elhelyezést. A 22,4 méteres illesztési maradék csak ennek az elhelyezésnek a diagnosztikája, **nem abszolút pontossági garancia**. A térképi jelölő azonosítása és a névpont elhelyezése is közelítő. Az eredeti teljes, 343 oldalas PDF, a natív JPEG, a képpontkontúrok, a kontrollok és a mátrix itt megmaradnak. A jelenlegi 3404 OSM-útszakasz, vízfolyás és vasút, a településhatár és a 27 névpont is megőrzött forrásadat.

Pápa nagy területei és a kisebb lakótelepek szándékosan átfedhetnek. A Várkert szülőterület a külön megtartott Belső és Külső Várkert uniója. A Tókert/Tókertváros és Malomkert/Malomkerti lakópark névváltozatok ugyanahhoz a területhez tartoznak. Kishegy és Öreghegy a színezett térképi kiterjedésen kívül marad; ezekhez ebből a csomagból nem állítunk elő találomra teljes városrészhatárt.

```sh
python3 data/neighborhoods/expansion-20261114-next/medium-cities/papa-build.py
```

A bemeneti országos PBF nélkül újraépíthető minden kimeneti poligon a megőrzött képpontlistából, mátrixból és forrásképből. A `papa-extract-roads.py` csak az eredeti, kiegészítő OSM-utak kivonatolásához kell; a poligonok újraépítése nem futtatja.
