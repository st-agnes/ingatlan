# Szolnok és Veszprém – gyors, hozzávetőleges térképi poligonbecslések

A csomag a 2026. november 14-én kért gyűjtési stratégiával készült: a történeti
és eltérő léptékű felosztások használhatók, az átfedések megmaradnak, a feliratok
és nyilak miatt takart kisebb határszakaszokat szemre kötjük össze.

- **Szolnok:** 21 névvel ellátott terület a KSH 2003-as funkcionális térképének
  Földi Katalin 2012-es disszertációjában szereplő másolatából.
- **Veszprém:** 11 körberajzolt komponens a 2008-as IVS térképéről, valamint
  a 2019-es önkormányzati kézikönyv mind a 16 fő városrésznevéhez egy becsült
  poligon. Ez a 27 rekord végleges név szerinti összevonás előtt értendő.
- Összesen **48 forrásváltozat / 40 eltérő város–név pár**, nulla körpótlás.
  A Csatár–Csatárhegy névváltozatot az alias jelzi; az összevont katalógusban
  egyetlen kereshető helynek kell számítani.

## Mit jelentenek a becslések?

A színes, illetve szaggatott forráskontúrok egyszerűsített kézi rajzolatait
használjuk. Veszprém 2019-es térképének központi részén nincsenek önálló
városrészhatárok: ott a belső választóvonalak kifejezetten becsültek a látható
utak, vízfolyások, a számozott névhelyek és a korábbi IVS-felosztás alapján.
Ezt minden érintett rekord külön megjelöli (`qualityScore: 30`); a követhető
forráskontúrok `qualityScore: 55` értéket kaptak. Ezek csak a forrásváltozatok
közti választást segítő, helyi minőségi értékek.

A földrajzi elhelyezés névvel azonosított forrástérképi helyek és a már megőrzött
OSM helypontok hozzávetőleges párosításából számolt affin transzformáció.
A párosítás nem geodéziai illesztőpont: a térkép felirata és az OSM névpontja
nem szükségképpen ugyanazon fizikai helyet jelöli. Az illesztési maradék
Szolnoknál kb. 376 m, a veszprémi IVS-nél 477 m, a TAK-nál 200 m RMS; ezek
**nem a határok igazolt pontosságai**. A teljes pontosság ismeretlen; a
forrástérképek méretarány- és korszakkülönbsége helyenként ennél nagyobb eltérést
is okozhat. A poligonok hozzávetőleges területi szűrés alapadatai.

Az IVS-csoportok a hagyományos városrészekkel átfedhetnek; emiatt nem kerültek
kizárásra. A Jutasi úti menti lakóövezet tágabb csoport, nem azonos a szűkebb
Jutasi úti lakóteleppel. Az ipari területek és a repülőtér saját névvel ellátott,
kereshető helyi területek.

## Állományok és újraépítés

- `features.geojson`: WGS84 / EPSG:4326 poligonok, forrásnevek, aliasok,
  dátumok, forráshivatkozások és a becslés módja.
- `pixel-specifications.json`: az összes kézzel megadott forráspixel-csúcspont.
- `registration.json`: a térképenkénti névpontpárok és transzformációk.
- `summary.json`: darabszámok és a műszaki ellenőrzések.
- `reproduce.py`: determinisztikus újraépítés, Python + NumPy/PyProj/Shapely.
- `*-source-grid.png`, `szolnok-source-large.png`: a rajzolást segítő
  diagnosztikai forrástérképek; az eredeti térképkivonatok már a `sources/`
  könyvtárban vannak, SHA256-azonosítójuk a kimenetben szerepel.

A csomag könyvtárából: `python3 reproduce.py` (a függőségek legyenek elérhetők).
A kimeneti gyűjtemény minden alakzata érvényes Polygon/MultiPolygon, és a
koordináták magyarországi tartományban vannak. Az összes városon belüli
névduplikátum kiválasztását a közös exportáló végzi.

## Megmaradt hiányok

A veszprémi kézikönyv hét alárendelt nevéhez nincs önálló poligon ebben a
csomagban: Temetőhegy, Pajtakert, Endrődi Sándor lakótelep, Takácskert,
Nádortelep, Egry József utcai lakótelep és Hóvirágtelep. Nem másoltuk rájuk
a szülőterület egészét. Nagykanizsa megnézett FVS-térképe fejlesztési
akcióterületeket rajzol, ezért abból nem neveztünk át önkényesen egy területet
városrésznek. Ezekhez további térkép vagy végső esetben névpont körüli körbecslés
használható.

A dokumentumok nyilvánosan hozzáférhetők; a térképek külön újrafelhasználási
engedélye nincs azonosítva. Az OSM-alapú illesztési adatokra az ODbL vonatkozik.
