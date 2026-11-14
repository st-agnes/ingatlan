Kecskemét — Árpádváros és Kossuthváros, a 73. ábra első külön csomagja

Két tényleges, teljes történeti forráskontúr. A pontos eredeti JPEG az önkormányzati
2021. májusi egyeztetési vizsgálat PDF143/nyomtatott141. oldaláról származik.
A PDF147 Árpádvárost, a PDF153 Kossuthvárost külön szövegesen is lehatárolja.
A négy releváns eredeti oldal hordozható PDF-kivonatban is megmarad.

Az Árpádváros-gyűrű 991, a Kossuthváros-gyűrű 791 eredeti, legfeljebb 45 maxRGB
értékű fekete képpontot tartalmaz a záróponttal együtt. Minden lépés 8-szomszédos.
A fő fekete komponens kizárólag az eredeti fekete maszk részhalmaza: a leváló
fotófekete foltok kihagyása nem ad pixelt a képhez és nem tölt ki rést.
A teljes közös parkolófolyosó és annak északi zigzagja a forrásnyomatot követi.
Nincs feliraton átkövetkeztetett szakasz, pótlóél, képkeretlezárás, buffer, repair,
geometriai snap, egyszerűsítés vagy törölt lyuk. A két cella átfedése nulla.

A teljes eredeti helyi útkivonat minden highway-típusa és a névtelen utak is
rendelkezésre álltak. A parkolófolyosó északi részére nem sikerült egyértelmű,
forrástérképpel megegyező mai node-láncot igazolni. A mai Forrás utca északi
hurka eltérően kerüli az épületeket. Nem gyártunk hiányzó gráfélt, és nem
használunk a forráscellán átvágó shortest-path útvonalat. A mai gráf részhalmaza
és a megmaradó kutatási kérdés külön fájlban szerepel. A poligon forrása a
tényleges zárt történeti fekete körvonal.

A földrajzi elhelyezés kizárólag BECSÜLT (inferred). Hat kézzel értelmezett régi
képi útcsomópont-párosítás és eredeti mai OSM-node koordináta között készül EOV
affin illesztés. Négy korábbi megfigyelés ugyanennek a 73. ábrának ugyanazon
képpontjaihoz tartozik. Az eredeti PDF képelhelyezési mátrixa és az archivált
oldalkép közös képtéglalapjának teljes pixelegyezése igazolja az átszámítást;
nem másik ábra vagy másik alapkép transzformációját vettük át. Két déli pontot
külön azonosítottunk. Egy korábbi Jókai/Piaristák jelölt fizikai azonossága
nem igazolt és az új modell ellenőrzésén kívül esik; az eredeti megfigyelést
és a sikertelen eredményt megtartjuk, nem tekintjük validáló kontrollnak.
A fitted maradék és modellérzékenység diagnosztika, nem abszolút határpontosság.

A mai OSM-névhasználat mindkét névnél külön igazolt. A névpontok a történeti
cellákon kívül vannak: a becsült poligontól Árpádvárosnál kb. 28,72 m, Kossuthvárosnál
kb. 45,14 m távolságban. Sem a fit, sem a körvonal nem használ névpontot kontrollként.
A név mai előfordulása nem igazolja a történeti és mai névterjedelem azonosságát.
Kossuthvárosnál a PDF144 a Belváros felépítésében „északi részt” említ, a PDF153
pedig külön KOSSUTHVÁROS cím alatt konkrét lehatárolást ad. A kimenet pontosan
a 73/153 szerinti forráskori cellát őrzi, és nem állítja minden tágabb történeti
Kossuthváros-változat teljes kiterjedésének egyezését.

A tényleges projekt validateGeometry függvénye mindkét geometriát elfogadja.
A sourcepixel-, PBF-, source-to-world-, scope- és projektvalidátor-ellenőrzések
külön független auditban is szerepelnek. A 23 kontrollút teljes node-sorrendje,
koordinátája és metaadata, valamint a 2 mai névnode közvetlenül az eredeti országos
PBF-ből visszaellenőrzött. Hordozható ellenőrzéshez a bizonyíték is megmarad.

Abszolút pontosság: null; usableForAddressAssignment: false. Mai jogi, kataszteri
vagy házszintű határállapot nem igazolt. Az önkormányzati térkép nyílt újrafelhasználási
licence nincs önállóan igazolva; a külön OSM-kontrollokra ODbL vonatkozik.

Offline ellenőrzés a repository gyökeréből:
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure73-first/trace-source-pixels.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure73-first/derive.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure73-first/audit-independent.py --check

A registry-entry.json kész integrációs jelölt; a globális regisztert ez a csomag
nem módosítja. A korábbi fagyasztott kecskeméti csomagok változatlanok maradnak.
