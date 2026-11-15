# Makó – 2026-11-15

A csomag a helyi forráspont-jegyzék mind a 34 nevéhez tartalmaz WGS84 alakzatot. Az összevonásba **csak a `features.geojson`** kerüljön; a részfájlok ismételt felvétele duplikációt okozna. Ez névjegyzék-lefedés, nem Makó teljes mai városrész-lefedésének igazolása.

Nyolc nagyobb városrész körvonala a 2024-ben közzétett önkormányzati FVS 282. oldalának 43. ábráját követi. A tényleges színes határok képpontkontúrjai megmaradnak, durva névfelirat-illesztéssel. A Belváros név és a forrás Városközpont csoportjának kapcsolata becsült; nem tettünk globális névváltozat-állítást.

További 17 névhez Tóth Ferenc múzeumi tanulmányának 30. ábráján közölt **valódi történeti területfoltok** szerepelnek. A nyomtatott 79. oldal a rövid PDF 40. oldala. Tizenhárom zárt fehér tartomány digitális kiemeléssel, négy apró munkásháztelep az eredeti körvonal kézi követésével készült. A térkép az 1700-as évektől az 1970-es évek elejéig kialakult foltokat mutatja. Ezek közül sok kisebb a mai városrésznél. A durva affin elhelyezés tíz hozzávetőleges névfelirat-kontrollt használ; a 177 m-es illesztési maradék nem független pontosságmérés. Tizenegy mai névpont kívül esik a történeti/alacsony biztonságú folton: ezt a `validation.json` és az `unresolved.json` nyíltan jelzi. A történeti alakokat nem mozgattuk önkényesen a mai pontok köré.

Kilenc kisebb lakótelep vagy városrész reprezentatív foltja tényleges, zárt OSM-utca-, vasút-, vízfolyás- vagy kertiútkörből készült. A névpont csak egy meglévő fizikai kör kiválasztását segíti. Ez nem állít teljes hagyományos városrészhatárt. A 2021-es önkormányzati örökségvédelmi tanulmány 16. oldalának utcai és történeti leírásai adják a névkapcsolati hátteret. Újszentlőrincnél a valódi kerti utak is szerepelnek a kör határán.

Minden alakzat kifejezetten alacsony biztonságú becslés. Nincs pont köré generált kör vagy téglalap. Az eredeti forráson eleve szögletes telek-/telepfoltok szögletességét megőriztük. A nagyobb és kisebb egységek átfedése szándékos; hivatalos vagy mai kataszteri pontosságot nem állítunk.

A `historic-native-pixel-polygons.geojson` és `municipal/native-pixel-polygons.geojson` **képpont-koordinátás forrásgeometriák, nem WGS84**, közvetlenül nem importálhatók. A teljes PDF-ek a közös `../downloaded-sources/` mappában maradnak; az eredeti képek, a képi illesztések, a szöveges oldal és az utcai forrásgeometriák itt is megmaradnak.

Újraépítés kizárólag helyi fájlokból, `numpy`, `scipy`, `Pillow`, `pyproj`, `shapely` csomagokkal:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/mako/municipal/build.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/mako/build-historic.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/mako/build-road-cells.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/mako/build.py
```

Az utolsó lépés ellenőrzi a 34 különböző nevet, a geometriák érvényességét, földrajzi tartományát, települési befoglalását és a mai névpontok viszonyát, majd elkészíti a `validation.json` fájlt. Az OSM-forrás licence ODbL-1.0; forrásmegjelölés: © OpenStreetMap contributors.
