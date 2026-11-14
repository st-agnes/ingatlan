Szeged – a második szakasz konkrét forrás- és geometriai akadályai
================================================================

Ez a folytatás az előző, lezárt municipal-szeged-next csomagot nem módosítja.
Új, teljes városrészpoligont itt nem állítunk elő:3 pozitív határleíráshoz
megőriztük az eredeti OSM-részleteket és a pontosan feloldandó kérdéseket.

Klebelsberg-telep / Hattyas
-------------------------
A helytörténeti egyesület2007-es könyvének9. oldalán négy természetes határ
szerepel: nyugati belvízcsatorna, déli Holt-Tisza, északi Körtöltés és keleti
vasúti töltés. A2018-as városi cikk és2026-os Szegedi Tükör megerősíti a
Klebelsberg-telep/Hattyas névazonosságot. Kecskés külön szomszédos városrész.
Az OSM-ben ettől délebbre egy külön Hattyas pont is szerepel: a történeti
névazonosság alapján nem olvasztjuk össze automatikusan annak földrajzi helyét
a telep északi lakóterületével.

A korábbi vízfelület-kulcsszavas gyűjtésből hiányzó, önmagukban címkézetlen
54 Holt-Tisza-partvonalat most az eredeti1483931-es OSM-reláció tagsága alapján
is kivettük a teljes országos PBF-ből. A nyugati csatorna és egy áteresz
ténylegesen találkozik az északi partvonallal.183 jelenlegi és korábbi vasúti
nyomvonal ellenőrzése után sem áll össze a keleti/délkeleti lezárás. Egy
lehetséges keleti iparvágány és a jelenlegi Holt-part közötti legkisebb rés
EPSG23700-ban625,628m. Ezt nem kötöttük össze kitalált vonallal.

A forrás vasúti TÖLTÉST mond, nem sínközépvonalat. A töltés a síneken túl is
folytatódhat, a mai vízfelület pedig eltérhet a történeti meder szélétől.
Egy régi helyszínrajz, töltésfelmérés vagy körvonalas városrésztérkép még
feloldhatja ezt. Ez tehát egy konkrét térképi illesztési akadály, és nem
annak kijelentése, hogy nincs több adat vagy nincs valós határ.

A független ellenőr241 eredeti elemet közvetlenül a PBF-fel összevetett:
minden vizsgált csomópontsor, koordináta, címke és objektumverzió egyezik.
Az independent-obstacle-review.json tartalmazza a részleteket és egy2015-ös
városi kerékpárhálózati terv használható, egykori kisvasúti töltésre utaló
forrását. Az még nem adja meg az egész keleti városrészhatárt.

Tarján,2019-es forrásváltozat
----------------------------
A várostörténeti folyóirat jelenlegi lakótelep-leírásában Retek és Murányi
szerepel, továbbá a József Attila sugárút különböző szakaszain eltérő
házszámoldalak. Az eredeti helyi úthálózatból előkerült a Murányit a
Körtöltéshez kapcsoló2019-es kerékpáros feljáró. Tehát a rövid hiányt nem
kellene kitalált egyenessel lezárni. Ettől azonban a városrészhatár még nem
egyértelmű: a két Murányi/József Attila csomópont, a szervizutak és a
páros oldali házak bevonása több kiterjedést enged. Egyszerű útcella-unióval
egyes kifejezetten bevonandó házakat kihagynánk. Nem készült hamisan pontos
mai pótlás, és ugyanazt a Tarjánt nem számoljuk még egy városrésznek.

Odessza
-------
A2018/2019-es városi történeti cikk az egész lakótelephez öt megnevezett
korridort ad. A2009-es IVS48. oldalán szereplő AKCIÓTERÜLET hosszabb
felsorolása Szőregi utat is említ. Ez segíti a mai névváltás/csomópont
értelmezését, de önmagában nem jogosítja fel egy akcióterület mai teljes
városrésszé minősítését.771 eredeti helyi közút-/vasúti elem átvizsgálásával
a közeli sínnyomvonal nem érinti a Szőregi út vonalát. A régi állomási töltés
vagy udvar szélét, illetve a forrás eredeti térképét kell azonosítani.
Nem helyettesítettük a hiányzó fizikai határt egy új összekötő szakasszal.

Az eredeti út- és vízpartgeometria ODbL-1.0, © OpenStreetMap contributors.
Az önkormányzati/egyesületi szövegekből tényszerű név- és határadatokat
dolgoztunk fel, a teljes kiadványokat nem másoljuk ide. Nyilvános webes
READ-eszközt használtunk, parancssoros hálózatot vagy új engedélykérést nem.

A reproducibilis akadályellenőrzés, hálózat nélkül:
PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-szeged-more.py --check

Nincs kitalált geometria, új poligon vagy automatikus címhozzárendelés.
