Esztergom – történeti, forrásalapú városrészjelöltek

Importjelölt: esztergom-candidates.geojson
Regiszterrekord: esztergom-registry-entry.json
Bizonyíték és tételes ellenőrzés: esztergom-proof.json

A Click That Hood nyilvános tárolójából, rögzített Git-hivatkozással átvett
eredeti állomány 33 tényleges MultiPolygon geometriát tartalmaz. Az eredeti
41 761 bájt és Git-blob SHA1 külön ellenőrzött; az eredeti fájl és metaadat
változatlanul megmarad. Az importjelölt ugyanazokat a koordinátákat használja:
nincs vetületváltás, levágás, puffer, illesztés, javítás vagy új zárószakasz.

A javaslat 32 történeti városrészjelölt és egy külön helyi terület. Az
Ipari park önmagában a nevéből nem minősül hibásnak, de a közvetlen
önkormányzati lehatárolás/osztályozás nincs megvizsgálva, ezért a finom
városrészek számát egyelőre nem növeli. A neve és geometriája megmarad.

A forrás metaadata egy 2008-as önkormányzati előterjesztés/rendelet
elérhetőségére hivatkozik; az eredeti kormányzati dokumentumot itt nem
töltöttük le és nem ellenőriztük. A forrás jellemzőinek időbélyege
2013-11-28; ez nem igazolt felmérési dátum és nem mai jogi határ.

Mind a 33 geometria érvényes. Kenyérmező és Tábor néhány kisebb darabja
átnyúlik a mai OSM-településhatáron; ezeket nem vágtuk le. A tételes
adatlap az eltérések területét és arányát is megőrzi.

26 névnek van megfelelő jelenlegi OSM-névpontja Esztergomban; ezek közül
Libád, Bánom és Szentanna névpontja a régi poligonon kívül van. A
névpont nem bizonyítja a történeti körvonal pontosságát. A város hivatalos
2023-04-21-i szolgáltatási közleménye több további név tényleges használatát
is alátámasztja, de nem ad hozzá határgeometriát. Kerektó mai névellenőrzése
egyelőre hiányzik; ezt külön jelöljük.

A szoftver MIT licence archivált, de ebből nem következik a külön adatállomány
vagy az eredeti önkormányzati térkép szabad újrafelhasználhatósága. Az egyedi
adatlicenc/jogállás nincs megállapítva. Minden poligon felülvizsgálatra vár,
automatikus címhozzárendeléshez nincs jóváhagyva. A 33 elem nem Esztergom
mai teljes és hiteles városrésznyilvántartásának állítása.

Reprodukció a tároló gyökerében, hálózat nélkül:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/public-vector-next/convert-esztergom.py --check

A repository-index.json a teljes, nem csonkolt 603 elemű Git-falista
metaadatfájljainak jegyzékét őrzi. A magyar településnevekkel való
fájlnévegyeztetés csak Esztergomot találta; a Hungary-adat a megyéké.
Más magyar város állománya ebben a pillanatképben nem volt azonosítható.
