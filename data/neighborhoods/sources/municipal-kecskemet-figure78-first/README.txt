Kecskemét — a 78-as ábra négy külön történeti forráscellája

Alsócsalános, Homokbánya, Alsószéktó és Szeleifalu teljes, külön feliratos
körvonalai a 2021. májusi egyeztetési vizsgálat PDF 166–167/nyomtatott 164–165.
oldaláról. A forrás külön tárgyalja Szeleifalu saját városrészi identitását,
Alsószéktó Kertvárost, Homokbánya egykori laktanyaterületét és Alsócsalános nevű
területét. Az Alsószéktó–Homokbánya ernyőcsoportot nem másoljuk le négy néven.
A képszélen levágott Alsószéktói kiskertek kimarad; hiányzó kiterjedését nem
egészítjük ki a képkerettel vagy kitalált szakasszal.

Az eredeti JPEG bájthű. A négy gyűrű 1043/1617/1468/1662, összesen 5790 csúcsa
mind tényleges maxRGB≤45 fekete forráspixel, minden lépés 8-szomszédos.
A fő fekete komponens kizárólag az eredeti maszk részhalmaza. Nincs új pixel,
réskitöltés, felirat mögé kitalált határ, pótlóél, képkeretlezárás, buffer,
geometriai snap, egyszerűsítés vagy javítás. A négy cella lyukmentes és
átfedésmentes; közös szakaszaik ugyanabból a képpixel-láncból származnak.
A valódi projektvalidátor mind a négy kimenetet elfogadja.

A földrajzi elhelyezés kizárólag BECSÜLT (inferred). A régi 79-es ábra és a 78-as
eredeti JPEG közös ortofotórészleteit 14 fitted és 16 előre elkülönített ellenőrző
fotótextúrapár kapcsolja össze. A legnagyobb ellenőrző eltérés 0,393 célpixel.
Négy konkrét tető/út részletét egy másik értelmező a modell és földrajzi adat
ismerete nélkül is megmérte; a későbbi összevetés az eredeti kézi ablakokon
belül maradt. Sem név, sem negyedhatár, sem földrajzi koordináta nem szerepel
a textúramatchingben. Az első alacsony korrelációjú képrészlet-próba nem
validáló pár. A korábbi keresések, nyers kivágatok és eredeti, szó szerinti
útvonalakat megőrző kísérleti kódok az exploratory-diagnostics könyvtárban
maradnak; az index.json külön rögzíti korlátaikat. A végső image-registration.json
mind a negyven keresést, köztük a tíz elutasítottat is megtartja.

A geometriai elhelyezéshez az eredeti 79-es csomag öt kézi képi útcsomópontját és
az eredeti OSM-node koordinátákat használó ÚJ, metrikus EOV-affin illesztés készül.
A fagyasztott 79-es csomag változatlan. Annak eredeti földrajzi-fokos modellje a
világ→képpixel legkisebb négyzetes fit inverze; ezt külön reprodukáljuk, és
megőrizzük az új metrikus modellel való összehasonlítást. A két modell közötti
legnagyobb csúcskülönbség 0,824 m; ez modellcsalád-diagnosztika, nem pontossági korlát.

A jó fotóegyezés nem igazolja a teljes földrajzi kiterjedést. A megfigyelt
textúrapontok burkán kívüli csúcsok száma 817/1267/964/1662; az eredeti 79-es
JPEG téglalapján kívül 490/1139/575/1479. Szeleifalu teljes pereme kívül esik a
megfigyelt textúrapontok konvex burkán; a legnagyobb képi extrapoláció itt 644 célpixel.
Ezeken a szakaszokon a KÖRVONAL továbbra is tényleges és zárt forrásnyomat,
a földrajzi modell kiértékelése extrapoláció. Teljes földrajzi validálást és
elsődleges besorolási jóváhagyást nem állítunk.

Mind a négy mai OSM-névnode külön archivált, az eredeti PBF-ből visszaellenőrzött
és a becsült történeti cellán belül van. Névnode nem volt kontrollpont és nem
alakította a határt. Mai előfordulása nem hitelesíti a történeti és mai kiterjedés
azonosságát. A 16 kalibrációs út teljes node-sorrendje és metaadata is közvetlen
PBF-ellenőrzést kapott; a hordozható ellenőrzési bizonyíték megmarad.

Abszolút pontosság: null; usableForAddressAssignment: false. A forráskori állapot,
a mai jogi/kataszteri határ és a nyílt térkép-újrafelhasználási licenc nincs
önállóan igazolva. Az OSM-kontrollokra és névpontokra ODbL vonatkozik.

Offline ellenőrzés a repository gyökeréből:
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure78-first/trace-source-pixels.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure78-first/fit-image-registration.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure78-first/derive.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure78-first/finalaudit-independent.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure78-first/verify-original-pbf.py --check

Az utolsó parancs a helyi, rögzített SHA-jú teljes PBF meglétekor újraolvassa
az eredeti objektumokat; nélküle csak az archivált bizonyíték és bemenetei
hash-egyezését ellenőrzi, és ezt a korlátot külön jelzi. Az alapellenőrzések
a repository projektvalidátorán kívül más forráskönyvtárat nem igényelnek.

A registry-entry.json integrációs jelölt. Ez a csomag nem módosítja a globális
regisztereket vagy a korábbi fagyasztott állományokat. A munkafolyamat kész,
ellenőrzött manifest után, atomikusan helyezi el a csomag másolatát a fenti
külön végső könyvtárban. Az aktív, kizárt munkamappa változatlan marad.
