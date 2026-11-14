Miskolc – 17 tényleges forrástérképi cella: 5 városrészjelölt és 12 gyűjtőegység

Kimenet: miskolc-source-raster.geojson
Regiszterrekord: miskolc-registry-entry.json
Szemantikai besorolás: miskolc-source-semantics.json és .csv
Reprodukáló: miskolc-derive.py (a tároló derive-local-map-next.py cellaeszközeit használja)

Öt önálló nevű statisztikai egység: Avas Dél, Miskolc-Tapolca, Lyukóvölgy,
Pereces, Bükkszentlászló. A másik 12 alakzat tervezési gyűjtőegység,
boundaryKind=planning_unit és canonicalNameIsNeighborhood=false jelöléssel.
A forrás a 32 KSH-egységet 17-re vonja össze. A 32 komponens mind egyszer
szerepel a hozzárendelési táblában; nem kapják meg külön-külön a gyűjtőalakzatot.
Az 5., 9. és 15. egység ugyan egy KSH-azonosítót tartalmaz, de a neve/leírása
összetett: ezeket sem tekintjük egyetlen finom, önálló nevű városrésznek.

Forrás
------
https://www.miskolc.hu/sites/default/files/dokumentumtar/mellekletek/2024-11/197_melleklet.pdf
Miskolc MJV Fenntartható Városfejlesztési Stratégiája 2021–2027,
2022. július; a 197/2023. (XII.14.) határozat melléklete.
228. PDF-/nyomtatott oldal, 23. térkép: „Miskolc városrészei a KSH
lehatárolások összevonásával”; az 58. táblázat a 228–229. oldalon, a
városrészek leírása a 229–231. oldalon szerepel. A 6. sor oldalváltáson át
folytatódik: Tetemvár mellett Bábonyibérc és Bedegvölgy–Bodótető is benne van.

A térkép saját forrásmegjelölése ITS 2014. Ezt képi eredetvizsgálat is
megerősíti: a későbbi melléklet 3691-es JPEG-objektuma byte-azonos a helyi
2014-es ITS 254. PDF-oldalán levő 1160-as JPEG-objektummal. Nem állítjuk,
hogy 2023-ban újramérték a körvonalakat. A légifelvétel ideje ismeretlen.
A jelenlegi, jogi vagy kataszteri határok és a pontos mai névhasználat ebből
nem bizonyítottak.

Teljes PDF SHA-256: c68fe45e74c9caa0ec9d36d5b35d686ee71d6bd75cf5603fb652e9f070e90744
Eredeti 884×557 JPEG SHA-256:
ae66dab154832f52a833d7c696a4b10882e8fadbc47a22d9128932ab7d684384
A miskolc-source-pages228-231.pdf eredeti oldalakat archivál; beágyazott képe
is byte-azonos. A részletes eredetvizsgálat a source-extraction-proof.json-ban.

Valódi rasztercellák, geometriamódosítás nélkül
---------------------------------------------
A forrás türkiz képpontjainak feltétele B-R>40, G-R>24, B>70. A négy oldalon
szomszédos nem-türkiz képpontok 17 külön, ténylegesen zárt cellát adnak.
Az adott számfeliratnál kézzel választott belső magpont azonosítja a cellát.
Az összes tényleges bevont pixel sorfutásainak pontos halmazunióját exportáljuk.
Minden poligonél mellett eredeti türkiz pixel van, a maszk teljesen újra
előállítható. Egyetlen lyukat sem töltünk ki: a fennmaradó összes 7 belső
forrásfolt változatlanul megmarad. A kép körvonalainak belső szélét követjük,
nem a vastag vonal feltételezett közepét; a vonal szélessége miatti rések
megmaradnak a szomszédos egységek között.

Nincs résáthidalás, névpont köré rajzolt alakzat, mai utakra cserélt körvonal,
poligonjavítás, geometriakivágás vagy képszélből képzett záróél. Mind a 17
forráscella távol van a raszter szélétől. A teljes város legészakibb türkiz
külső vonala helyenként a JPEG felső széléhez ér; az 5 pixelen belüli jeleket
kihagyjuk a georeferálási kalibrációból. A városhatárt nem exportáljuk a
képszéllel bezárt alakzatként.

A gyengébb színküszöbök több JPEG-krominanciafoltot eredményeznek. B-R 30,
40 és 50 mellett mind a 17 cella továbbra is külön zárt; 60-nál egy szomszédos
pár már összefolyik. A választott 40-es maszknál nem kellett körvonalat
javítani vagy lyukat eltüntetni. Mind a 17 változatlan geometria átmegy a
tároló konzervatív validateGeometry ellenőrzőjén.

Georeferálás és korlátok
-----------------------
3396 valódi külső türkiz vonalpontot illesztünk a mai, archivált OSM-
településhatárhoz EOV-ban, robusztus legközelebbi-határpontos affin módszerrel.
Az összes eredeti képi pont és transzformációs mátrix megmarad. A diagnosztikai
reziduum mediánja kb.20,8 m, 95. percentilise kb.66,4 m. EZ NEM FÜGGETLEN,
ABSZOLÚT HATÁRPONTOSSÁG: a vetület, a légifotó, a vonalszélesség és a forrás
térképi általánosítása bizonytalan. Önálló belső felmérési kontroll nincs.
A pontos abszolút határpontosság null/ismeretlen, címhozzárendelés kikapcsolt.

A 6. és 17. gyűjtőegység a mai OSM-határon kb.344, illetve 607 négyzetméterrel
túlnyúlik; ezt eltérésként megőrizzük, nem vágjuk le. A többi 15 egység teljesen
belül van. A mai Miskolctapolca névpont kb.24 m-rel a régi maszkterületen kívül
van; ez is változatlanul dokumentált. A kimeneti földrajzi csúcsok a raszter-
cellák transzformált sarkai, nem szó szerinti OSM-csomópontkoordináták.

A közzétett önkormányzati térkép újrafelhasználási joga nincs külön igazolva.
Az ODbL az archivált OSM-kalibrációra és névhelyekre vonatkozik, nem
automatikusan a teljes eredeti térképre. Ez forráskorhoz kötött kutatási adat.

Reprodukció a tároló gyökeréből, hálózat nélkül:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-local-map-next/miskolc-derive.py --check
A --check nélküli futtatás újraírja a kimenetet. A miskolc-fit.py az affin
kalibráció külön reprodukálója; a fő export a fagyasztott registration.json-t
használja. Az eredeti JPEG változatlan. A teljes országos feladat nem kész,
és a 17 gyűjtőábra nem szolgáltatja a 32 külön városrész összes finom határát.
