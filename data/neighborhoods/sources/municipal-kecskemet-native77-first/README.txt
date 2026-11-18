Kecskemét — a 77. ábra első, önálló natív forráscsomagja

Forrás: Megalapozó Vizsgálat II., egyeztetési változat, 2021. május;
PDF 163–164., nyomtatott 161–162. oldal. Az eredeti PDF SHA256 értéke:
83f78c5dbb85964a1fc4aecb2df014254e1985fdb446d8135182dedad56da939.
A hordozható source-pages163-164.pdf megőrzi az eredeti natív Form streamet.
A source-form188-stream.txt az eredeti xref 188 dekódolt streamjének pontos mása.
Az archív rész-PDF xref számai természetesen eltérnek az eredetitől.

Kimenet: fine-inferred.geojson — Kósafalu, Muszáj, Rendőrfalu.
E három önálló lakónegyedet a PDF 164. oldal prózája külön is megnevezi.
Mai, pontosan egyező OSM-névpontjaik külön archiválva vannak. A névpont
előfordulása nem hitelesíti a történeti körvonal mai kiterjedését.

Kimenet: local-units-inferred.geojson — a középső Szent László város forráscella,
Déli iparterület I–II., Nyugati iparterület. Az ipari funkció önmagában nem
kizáró ok: e cellák tényleges külön forrásnevei és teljes natív körvonalai
megmaradnak. Finom városrész-jellegük nincs automatikusan igazoltnak tekintve.
A kétlyukas középső cella NEM a teljes, azonos nevű fejlesztési városrész:
a cím és próza tágabb Szent László Város fogalma az összes környező lakó- és
gazdasági egységet magában foglalja. Az ernyőkörzetből nem gyártunk másolatokat.

A 7 eredeti natív út 497 nemnulla szakasza Decimal-parserrel is igazolt.
Minden részút már eredeti lineto utasítással visszatér a kezdőpontjára.
Nincs hozzáadott lezárás, képkeretszakasz, buffer, javítás, snap vagy egyszerűsítés.
A két eredeti középső lyuk pontosan a külön Kósafalu- és Muszáj-cella.
Déli iparterület II. és Nyugati iparterület tényleges natív utasításai a megjelenített
raszter/clip szélén túl is folytatódnak. Kizárólag ezeket az eredeti folytatásokat
őrizzük meg; nem a képkeret alapján állítjuk helyre a körvonalat.

A földrajzi illesztés hat valódi, a történeti alaptérképen kézzel azonosított
útkeresztezés és mai, eredeti PBF-node koordináta közötti EOV-affin illesztés.
A kontrollok azonosítói, pontmérései és teljes eredeti kontrollútjai archiváltak.
Másik kecskeméti ábra kontrollját vagy illesztését nem vesszük át. Nincs GeoPDF
regisztrációs szótár; nyomtatott koordináta, lépték vagy északnyíl sem azonosítható.
A kis kontrollmaradék nem abszolút határpontosság. A déli Daimler-jelöltet
a fitből kihagytuk. A mai node két kerékpárút bekötése; a történeti képen
látható közúti csomópont közepével való fizikai azonossága nem igazolt, ezért
nem minősül független regisztrációigazolásnak. Az első szűk kézi ablakhoz
viszonyított eredménye georeference.json-ban változatlanul szerepel, az eltérést
nem tüntetjük el az ablak modellhez igazításával. A kontrollkihagyásos és a hasonlósági
modellel végzett érzékenységi vizsgálat is ugyanott található.

Ez az első csomag konzervatívan becsült földrajzi elhelyezésű (inferred).
Az eredeti forráskontúr lezártsága ettől külön igazolt. Abszolút pontosság: null.
usableForAddressAssignment minden rekordban false. Mai jogi, kataszteri vagy
házszintű határállapot nem igazolt. Az önkormányzati forrás nyilvános olvashatósága
nem jelent önálló nyílt újrafelhasználási licencet; az OSM kontrollok ODbL-adatok.

Offline reprodukció a repository gyökeréből:
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-native77-first/derive.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-native77-first/audit-independent.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-native77-first/verify-original-pbf.py --check

Két külön PBF-auditor is ellenőrizte a 20 teljes kontrollút mind a 206 eredeti
nodeRef/koordináta-párját és metaadatait, valamint a három mai névnode-ot.
A verify-original-pbf.py a teljes PBF hiányában az archivált ellenőrzési
bizonyítékot és a bemenetek lenyomatát ellenőrzi, és külön jelzi, hogy abban a
futásban nem történt új PBF-olvasás. A forráskori/melyik mai fizikai ponttal
azonos kérdést a PBF-adatok bájthűsége önmagában nem oldja fel.

A két registry-entry fájl kész integrációs jelölt. A globális regisztereket ez a
csomag nem módosítja. A folytatható raster-more munkamappa további változásai
nem írják át e csomag befagyasztott bemeneteit.
