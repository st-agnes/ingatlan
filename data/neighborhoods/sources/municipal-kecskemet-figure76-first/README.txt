Kecskemét — a 76. ábra három külön történeti forráscellája

Külső Árpádváros, Mezeiváros és Ürgés eredeti, zárt fekete raszterkörvonalai.
Forrás: a 2021. májusi önkormányzati egyeztetési vizsgálat PDF161–162.,
nyomtatott 159–160. oldal. A szöveg a tágabb Mezeiváros és környezete városrészt
kifejezetten e három meghatározó egységre osztja; a kimenet a három külön
feliratos cellát őrzi, nem a teljes ernyőkörzetet másolja le három néven.

Az eredeti 1702×1204 JPEG bájthűen archivált a hordozható PDF-kivonat mellett.
A három gyűrű 1617/1996/1022 csúcsa a záróponttal együtt 4635 eredeti fekete
forráspixel. Minden maxRGB≤45 és minden lépés 8-szomszédos. A közös osztóvonalak
egyetlen forráspixel-láncból származnak. Nincs felirat mögé kitalált határ,
réskitöltés, képkeretlezárás, pótlóél, buffer, geometriai snap, javítás,
egyszerűsítés vagy törölt lyuk. Mindhárom cella lyukmentes és területileg
átfedésmentes. A valódi projektvalidátor mindhárom kimenetet elfogadja.

A földrajzi elhelyezés mindhárom rekordnál kizárólag BECSÜLT (inferred).
A 73 és 76 ábra közös ortofotórészleteit valódi képi textúrák kapcsolják össze:
10 előre kijelölt fit-pár és 10 külön ellenőrző NCC-pár ad képi affin kapcsolatot.
A legnagyobb ellenőrző eltérés 0,47 célpixel. Ezen felül egy másik értelmező
négy konkrét tetőrészletet mért meg a modell és geopozíció ismerete nélkül;
a későbbi összevetés mind a négy eredeti kézi bizonytalansági ablakon belül van.
A képmatching sem földrajzi koordinátát, sem negyednevet, sem határgeometriát
nem használ. A különböző világosítás/sötétítés ellenére a tényleges tetőalakok,
árnyékok és udvarminták ugyanazokat az ortofotórészleteket támogatják.

A képi kapcsolat inverzét a külön fagyasztott 73-as csomag becsült EOV-modelljével
komponáljuk. A hat régi úti kontrollból számolt modell önállóan újrafittelhető
a másolt, eredeti node-koordinátákból. A korábbi földrajzi bizonytalanság és a
kizárt fizikai kontroll sikertelensége ettől megmarad. A jó képi matching nem
teszi a földrajzi regisztrációt hitelesítetté.

A 76 peremeinek jelentős része a megfigyelt közös képi átfedésen kívül van.
A forráskontúr ezekben a részekben is tényleges és zárt; a földrajzi modell
kiértékelése extrapoláció. A matched textúrapontok konvex burkán kívüli csúcsok
száma 1339/954/846, a 73-as kép téglalapján kívül 1055/415/556. A legnagyobb
képi távolság a megfigyelt textúrapontok konvex burkától 523/219/351 célpixel. Ezek forrásképi
diagnosztikák, nem abszolút földrajzi hibakorlátok.

Ürgés mai pontosan egyező OSM-névnode-ja külön archivált és az eredeti PBF-ből
visszaellenőrzött; a becsült poligonon belül van. Külső Árpádváros és Mezeiváros
mai pontos névhasználata e körben nincs külön igazolva. Nem találunk ki alias-t,
és egyik névpont sem vesz részt a georeferálásban vagy a határ alakításában.
A név mai előfordulása nem hitelesíti a történeti körvonal mai kiterjedését.

Abszolút pontosság: null; usableForAddressAssignment: false. Jogi/kataszteri/mai
határállapot nincs igazolva. Az önkormányzati térkép nyílt újrafelhasználási
licence nincs önállóan igazolva; a külön OSM-kontrollokra ODbL vonatkozik.

Offline ellenőrzés a repository gyökeréből:
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure76-first/trace-source-pixels.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure76-first/fit-image-registration.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure76-first/derive.py --check
PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kecskemet-figure76-first/finalaudit-independent.py --check

A textúramatching reprodukciója a helyben rendelkezésre álló NumPy/SciPy/Pillow
könyvtárakat használja; nem telepít és nem tölt le semmit. A registry-entry.json
kész integrációs jelölt; globális regisztert és korábbi fagyasztott batch-et ez a
csomag nem módosít.
