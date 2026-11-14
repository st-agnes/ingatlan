Kaposvár – 2014-es forráskörvonalak, külön becsült földrajzi illesztéssel
=====================================================================

Ez a csomag 10 teljes forrásnevet és 16 különálló színezett komponenst őriz.
ELSŐDLEGES / IGAZOLT FÖLDRAJZI POLIGON NINCS BENNE. A WGS84-változat kizárólag
az elkülönített inferred_georeference réteghez készült. Regiszterjelölt:
inferred-registry-entry.json. Közös regisztert az előállító nem módosít.

Forrás
------
Kaposvár MJV Integrált Településfejlesztési Stratégia, 2014. szeptember,
18. PDF-oldal / 18. nyomtatott oldal. Az eredeti PDF 124-es beágyazott képe
pontosan a kaposvar-p18-source.jpeg, változatlan 625×883 JPEG-bájtokkal.
A forrásazonosság és az eredeti oldal szövege: source-extraction.json.

Az önkormányzat a forrás szerint 10 városrészre osztotta a települést:
1. Belváros
2. Északnyugati városrész
3. Északi városrész
4. Kisgát és környéke, Cukorgyár, Pécsi utca és környéke
5. Kecelhegy – Cser
6. Donner – Rómahegy
7. Ivánfahegy – Kaposszentjakab
8. Kaposfüred
9. Toponár – Répáspuszta – Fészerlak – Deseda
10. Töröcske – Zselic kertváros

A teljes forrásnevek megmaradnak. Nem készül például ugyanarról az alakzatról
külön Kecelhegy- és Cser-poligon. Az 1–7. egységnek egy-egy színezett része van;
a 8-asnak HÁROM, a 9-esnek négy, a 10-esnek kettő. A kezdeti 14-es komponensszám
hibás volt: a Kaposfüred főfoltja melletti két apró cián folt is tényleges,
különálló forrásalakzat. Ezeken nincs saját szám; a 8-ashoz rendelésük az azonos,
egyedi cián szín és a térképi összefüggés alapján becsült hozzárendelés.

Natív képi körvonalak
--------------------
A source-contour-components.json megőrzi mind a 16 komponens natív adatait.
A native-legend-unit-contours.json a 10 teljes egység natív geometriáját adja.
Ezek KÉPPONTKOORDINÁTÁK, nem földrajzi hosszúság/szélesség. Külön mező jelzi ezt;
nem szerepelnek földrajzi importregiszterben.

Tizennégy komponens az eredeti JPEG színmaszkjának határát követő becslés.
A dokumentált HSV-tartományok, S≥35/V≥80 küszöb, négy-szomszédos komponensek,
tényleges kiválasztott színpixelek sorfutamos tárolása megmarad. A városrészi
1–10 számjelölések és szürke CAD-utcanyomatok miatt teljesen körbezárt apró
maszklyukakat kitöltjük. Összesen 1368 ilyen képpont van; a legnagyobb összefüggő
maszklyuk 102 pixel. Ezekről nem állítunk földrajzi lyukat.

Az eredeti képen meglévő fehér külterületi hézagokat, külső bevágásokat és
különálló komponenseket NEM kötjük össze. Nincs konvex burok, buffer, képkeretes
lezárás, szabadon kitalált összekötő él vagy a mai úthálózattal helyettesítés.
A képcellák széle x±0,5/y±0,5; csak pontosan kollineáris csúcsok maradnak ki,
zéró területkülönbséggel. A nyers színmaszk területe pontosan a cellaszáma.

Két célzott kivétel javítja a grafikus fedvények kezelését:
- 8-northeast: az áttetsző/átfestő szürke CAD-nyomat hamis mély bevágást okozott
  a puszta színmaszkon;
- 9-north-tip: a felső vonallal összeérő 9-es számjegy hasonló hamis bevágást adott.

E két végső körvonal tényleges sötét forráspixelek zárt, nyolc-szomszédos lánca.
A kézzel azonosított KÜLSŐ vonalat hárompixeles keresési folyosó követi. Minden
sűrű útvonalpont RGB-értéke legfeljebb 165; ez sötét, élsimított vonalképpont,
nem kizárólag tiszta fekete. A 125-ös küszöb a halvány jobb oldali vonalon nem
adott folytonosságot; a 165-ös ténylegesen meglévő, folytonos képpontutat ad.
Nincs hiányzó képpontrés áthidalva. Az összes kezdőpont, tényleges pontlánc és RGB
megmarad a darkSourceOutlineOverride mezőkben; a trace_dark_overrides.py reprodukálja.
Ezek egész képpontközéppont-koordináták. A nyers HSV-maskGeometry külön megmarad,
tehát senki nem keverheti a maszknak és a végső körvonalnak az eltérő területét.
A két végső körvonal 1055,5 és 601 pixel²; nem a színmaszk 868 és 518 pixel²-e.

A küszöbérzékenység ténylegesen kiszámolt, nyers HSV-maszkdiagnosztika:
S25/V70 és S45/V95 mellett a határváltozás legnagyobb Hausdorff-eltérése 6,3246 px.
Ez nem az igazi határhibát méri, és a két rögzített sötét körvonal végső geometriájára
nem alkalmazható. Ezt az applicableToFinalContour mező külön is jelzi.

Miért csak becsült földrajzi illesztés?
-------------------------------------
A képnek nincs ismert földrajzi vetülete, koordinátarácsa vagy mért kontrollja.
Két belvárosi, kézzel feltételezett képi/mai útcsomópont-megfeleltetésből készült
egy ideiglenes EOV-hasonlósági transzformáció. A mai OSM-csomópontok földrajzi
koordinátái szó szerint igazoltak a helyi PBF-ből, viszont a képi megfeleltetések
NINCSENEK függetlenül igazolva. A hat további külvárosi jelöltet a halvány
CAD-rétegen nem lehetett egyértelműen azonosítani. Elfogadott független fizikai
kontrollok és kihagyott fizikai ellenőrzőpontok száma: NULLA.

A provisional-georeference.json és control-review.json ezt tételesen rögzíti.
A két pont pontosan meghatározza a matematikai hasonlóságot; a közel nulla belső
illesztési maradék nem bizonyítja a pontmegfeleltetés helyességét vagy a pontosságot.
Az eredeti mai OSM-utak és nodeRef-ek az all-city-roads-rails.geojson fájlban vannak.
A hozzávetőleges névpontegybeesések csak durva térségi diagnosztikák: az OSM-névpont
nem helyettesítheti a ténylegesen azonosított régi utcacsomópontot.

A registration-sensitivity.json 16 esetet számol: a két feltételezett képi horgony
négy koordinátáját egymástól függetlenül ±3 pixellel módosítja. A legnagyobb
kiszámolt elmozdulás nagyságrendileg 1 km. Ez CSAK feltételezett bemenetre adott
modellérzékenység: nem megfigyelt hiba, nem statisztikai konfidenciaintervallum,
nem valódi hibahatár vagy keresési sugár. A hárompixeles bemenetet sem mértük.

A claimedAbsoluteAccuracyMetres mindenütt null. Nincs kijelölt pontossági sugár.
Az összes WGS84-rekord estimated:true, inferred_georeference besorolású,
elsődleges rétegbe nem kerül és usableForAddressAssignment:false. A jelenlegi
kanonikus településhatártól való
eltérést diagnosztikaként megőrizzük; nincs hozzá vágás vagy újraillesztés.
A mai pontos névhasználat, jogi/kataszteri határ és házszintű címbesorolás nincs igazolva.

Reprodukció és ellenőrzés
------------------------
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-kaposvar-raster-next.py
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-kaposvar-raster-next.py --check

A --check csak összehasonlít, nem ír fájlokat. Függőségek: numpy, scipy, Pillow,
Shapely, pyproj; az eredeti JPEG és archivált földrajzi referenciák helyben vannak.
A geographic-source-extraction.json rögzíti a teljes változatlan OSM-utak helyi
kinyerését; a gyűjtési téglalap soha nem vált városrészhatárrá. Nincs hálózati művelet.

Független forrás-/szemantikai ellenőrzés: visual-review.json; kontrollvizsgálat:
control-review.json; végső számítási/körvonal-audit: independent-review.json.
Az audit a szerkesztett adatok és a matematika reprodukálhatóságát ellenőrzi,
nem minősíti igazoltnak a továbbra is feloldatlan földrajzi illesztést.
Külön, alapból csak olvasó reprodukció:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-kaposvar-raster-next/independent_audit.py --check

Az önkormányzati térkép nyílt újrafelhasználási licence nincs külön igazolva;
az ODbL az OSM-referenciaadatokra vonatkozik, nem automatikusan a teljes térképre.
