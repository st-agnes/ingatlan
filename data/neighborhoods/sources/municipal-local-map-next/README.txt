Zalaegerszeg – hét forrásképi városrészjelölt, öt szigorúan importálható alakzat

Importálható: zalaegerszeg-import.geojson
Regiszterbeillesztéshez: zalaegerszeg-registry-entry.json
Nyers teljes feldolgozás: zalaegerszeg-source-raster.geojson (7)
Karantén: zalaegerszeg-quarantine.geojson (2, változatlan geometria)

Az öt importjelölt: Belváros, Páterdomb, Kertváros, Csácsbozsok, Vorhota.
Ola és Landorhegy forrásképi alakzata is elkészült, de a tároló változatlan,
konzervatív JS-geometriaellenőrzője hole_outside_shell hibát jelez. A megmaradt
belső színes foltok 1–2 képpontosak; GEOS szerint mind a hét poligon érvényes.
A két alakzatot nem javítottuk észrevétlenül, és nem számítjuk hozzá az ötös
importeredményhez. Az eredmény a zalaegerszeg-strict-validator-review.json-ban
ellenőrizhető. Az öt importált geometria pontosan azonos a nyers hétből vett
megfelelő geometriával; kiválasztás történt, geometriai javítás nem.

Forrás és jelentés
-----------------
Zalaegerszeg önkormányzati honlapján közzétett ITS 2014–2020, 2014.08.28.
A címlapon „JÓVÁHAGYÁSRA SZÁNT VERZIÓ” szerepel. A 12. PDF-/nyomtatott oldal
1. ábrája: „Zalaegerszeg városrészek szerinti felosztása”. A szöveg szerint
a felosztás a 2009-es és 2011-es statisztikák összehasonlíthatóságát szolgálja;
ez nem bizonyítja, hogy mai, jogszabályi vagy kataszteri határokról van szó.
A 13. oldal számozott táblázata rendeli a neveket a térképhez.

URL: https://zalaegerszeg.hu/wp-content/uploads/2023/05/Zalaegerszeg_ITS.pdf
Teljes eredeti PDF SHA-256:
4534775c49466eba0460e583aa45a12127f0a46cd8c0e768ed689b830e4eb035

A zalaegerszeg-source-pages12-13.pdf a két érdemi oldal helyi archív kivonata.
A zalaegerszeg-p12-image0.jpeg bájtjai az eredeti PDF 105. képi objektumával
és az archivált kivonat képével azonosak, 1663×2360 képpont.
A JPEG SHA-256: cf259e0c7c54c3b58a0cf1e624ef178432ae734336cd3b676a9c7f2675aa8e37

Nem nyilvánítjuk a 9., 15. és 16. összetett területi egység minden résznevét
azonos poligonú önálló városrésszé. A 17–20. külterületi egységek nem finom
városrészek. A keskeny 10–14. egységeken a kör alakú számjel egyes helyeken
eltakarja/kettévágja a határt; ezek hiányát nem hidaltuk át feltételezéssel.
A 6. iparterület több külön cellája és a többi fel nem dolgozott terület sem
számít kész városrészhatárnak. Ola északi részének és a belső szaggatott jelnek
az értelmezése további forrást igényel; Ola ezért sem tekinthető kész adatnak.

Forrásképi előállítás
--------------------
Az eredeti JPEG türkiz képpontjainak feltétele: R<135, G-R>30, B-R>30, G>65.
A négy szomszédos nem-türkiz képpontok összefüggő komponensei adják a forrás
TÉNYLEGESEN ZÁRT belső celláit. A képszélhez érő komponenst a kód elutasítja.
Csak az adott belső cellába teljesen bezárt, kézzel megjelölt számozott kör
mesterséges lyukát állítjuk vissza. Más forrásfoltok/lyukak megmaradnak.

Minden sor tényleges cellafutásai fél-egész pixelkoordinátájú téglalapokká
válnak, amelyek pontos halmazuniója adja a belső területet. A kész poligon
a vastag rajzolt határsáv BELSŐ SZÉLÉT követi. Ez nem a sáv középvonala és
nem felmérési nyomvonal. A szomszédos jelöltek között így a forrás határsávja
miatti rések maradhatnak. Minden egységnyi raszterhatárél mellett van valódi
eredeti türkiz képpont; minden rekordnál nulla a hiányzó forráspixelek száma.
Nincs képszélből képzett határ, generált záróhúr, réshíd, névpontpuffer,
mai úthálózattal helyettesített alakzat, földrajzi javítás vagy kivágás.

A zalaegerszeg-conversion-proof.json tartalmazza a kézi belső magpontokat,
az érintetlen pixelcella-geometriákat, a számjel-lyukak méretét, minden
eredeti színhez támaszkodó határél számát és a teljes affin transzformációt.
A seven-source-polygons.png a tényleges forrásra rajzolt ellenőrző ábra.

Georeferálás és pontossági korlát
--------------------------------
A forrás kicsi türkiz szaggatott komponenseinek tényleges képi súlypontjait
illesztjük a mai OSM-településhatárhoz. A fagyasztott affin illesztés EOV-ban
történik, majd EPSG:4326-ba vetítünk vissza. A nyers településpoligon és a
313 felhasznált képi pont, illesztési mátrix, maradékok archiválva vannak.
A diagnosztikai maradék mediánja kb.35,3 m, 95. percentilise kb.150,4 m.
EZ NEM FÜGGETLEN, ABSZOLÚT HATÁRPONTOSSÁG. A vetület, forrásfelmérés ideje,
a vastag vonal és az önkormányzati alaprajz általánosítása bizonytalan.
A forrás és a mai településhatár keleti oldala több száz méterrel eltér.
A registration-preview.png ezt a különbséget is megőrzi. A mai úthálózat
rávetítése csak vizuális diagnosztika, nem független, számszerű pontosságmérés.

A kimeneti csúcsok a képcellák transzformált SARKAI, nem szó szerinti OSM-
csomópontkoordináták. A névpontok a mai azonos városbeli OSM-nevet ellenőrzik,
a történeti határ helyességét nem igazolják. A Páterdomb névpont 7,8 m-rel,
Kertvárosé 3,8 m-rel, Csácsbozsoké kb.215 m-rel van a régi maszkterületen kívül;
az eltérés megmarad a rekordokban, nem igazítjuk hozzájuk a geometriákat.
Minden pontossági mező ismeretlen; automatikus címhozzárendelés kikapcsolt.
A mai pontos városrésznév, jogi határ és újrafelhasználási jog nincs igazolva.
A közzététel önmagában nem nyílt licenc; az ODbL az OSM-kalibrációs adatokra
vonatkozik, nem automatikusan a teljes önkormányzati térképre.

Reprodukció a tároló gyökerében:
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-local-map-next.py --check
Előállítás --check nélkül. Python-függőségek: numpy, scipy, Pillow, shapely,
pyproj. Hálózat nem kell. A fit.py a korábbi önálló regisztrációs kísérletet
őrzi; a fő reprodukáló a fagyasztott registration.json-t használja, így nem
állítja azt, hogy a mai OSM-határból újra felméri a régi városrészeket.

Veszprém: negatív, ténylegesen ellenőrzött forrás
-----------------------------------------------
A helyben meglevő 259 oldalas ITS szövege 14 városrészt sorol fel, de a
76. oldal térképe 20 fejlesztési beavatkozási célterületet ábrázol. Ezek nem
a 14 városrész poligonjai. A veszprem-source-review.json rögzíti a teljes
forrásszemlét; veszprémi poligon ebből a batchből nem készült. Ez kizárólag
a vizsgált PDF hiányossága, nem bizonyítja, hogy máshol sem létezik térkép.

A teljes országos feladat és még Zalaegerszeg feldolgozása sem teljes.
