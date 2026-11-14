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
