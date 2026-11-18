Pécs – első, lezárt 33-as becsült földrajzi csomag

Import: source-inferred.geojson, kizárólag inferred-candidate-registry.json-ba.
Regiszterrekord: registry-entry.json.
33 becsült jelölt; 0 primary jóváhagyás. A jelöltek között 32 finom
városrésznév és 1 teljes gazdasági tervezési egység szerepel. A nevek és a
forráskontúrok ténylegesen megfigyeltek; a földrajzi elhelyezés nincs hitelesítve.
Automatikus címhozzárendelés minden rekordnál kikapcsolt.

Ez önálló, fagyasztott snapshot. A municipal-pecs-next munkamappából sem a
konverter, sem a kimenet előállítása nem olvas változó fájlt. A további 27
név/cella és az útcsomópontos georeferálás nem része ennek a kiadásnak.

Forrás
------
Pécs MJV ITS 2021–2027 önkormányzati közzététele; a PDF címlapján a
261/2014. (09.25.) határozat is szerepel. A 48. PDF-oldal 9. ábrája a finom
neveket, a 63. PDF-oldal 12. ábrája a részletes körvonalakat tartalmazza.
Az utóbbi térképen 2011-es népszámlálási adat és 2014-es készítői jelölés
szerepel; a határok tényleges felmérésének időpontja ismeretlen.

https://logoweb.pecs.hu/download/koncepcio/ITS.pdf
Teljes eredeti PDF SHA-256:
995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1

A pecs-source-selected-pages.pdf az eredeti 1/47/48/60/61/62/63. oldal
archivált kivonata. A két JPEG az eredeti PDF-képobjektummal és a kivonat
képeivel byte-azonos; a source-extraction-proof fájl ezt rögzíti.
A forrásképek és a reprodukció összes rögzített bemenete helyben megtalálható.

Geometriák és nevek
------------------
A forrás eredeti szín-/lokáliskontraszt-maszkjának valóban zárt, négy
oldalszomszédos pixelcelláiból indulunk ki. A független névolvasás a
13 gyűjtőegységet nem másolja át 67 finom névre. A forrás táblázatának és
térképének római számozása több helyen eltér, ezért tényleges címke/alak/
szomszédság alapján történik a párosítás. Bálics és Szkókó korábbi
provizórikus felcserélését független képi olvasással javítottuk.

A raw-pixel-cells.json mind a 33 eredeti, módosítatlan pixelgeometriát őrzi.
A pontos sorfutások halmazuniójából készül az értelmezett kontúr. Nincs
képszélből képzett záróél, résáthidalás, puffer, földrajzi javítás vagy kivágás.

74 egypixeles maszkfolt és 12 fekete római feliratgrafika nem földrajzi
enklávé. A független kartografikus audit kizárólag ezeknek a konkrét,
hash-azonosított 1 076 képpontnak a pixeloldali visszaállítását támasztja alá.
Másik szabad cellát egyik sem tartalmaz vagy érint oldalszomszédként, és
egyetlen külső forrásél sem változik. A konverter csak ezeket állítja vissza;
általános lyukkitöltést nem végez. Az engedélyezett halmaz és minden nyers
cellakontúr megmarad, így az értelmezés számszerűen visszaellenőrizhető.

Az archivált eredeti kartografikus/név-review néhány mezője történeti
munkamappa-elérési utat tartalmaz. Az érdemi forrásadat és a képi kivágások
byte-azonos másolatai ebben a csomagban is megvannak, azonos fájlnévvel;
a végső independent-review és az artifact-manifest a helyi másolatokra mutat.
Ezek a történeti szöveges útvonalak nem konverterfüggőségek.

A földrajzi elhelyezés bizonytalansága
------------------------------------
A részletes és a névképi térképet fagyasztott affin képregisztráció kapcsolja
össze. A névkép 34 északi/nyugati, valóban látható szürke településhatár-
képpontjának illesztése adja a becsült EOV-keretet, majd EPSG:4326-ba vetítünk.
A névhelyek nem határképző pufferek vagy végső földrajzi kontrollok.

A keret délkeleti extrapolációja még bizonytalan. Később, a világvonal
megtekintése nélkül kiválasztott keleti/déli szürke forráspontoknál akár
kb.349 m eltérés mutatkozik a mai településhatártól. Ebből nem bizonyított,
hogy mennyi a régi térkép, a mai határ vagy a regisztráció eltérése.
Ezért a csomag EGYETLEN rekordja sem kap primary/georeferencia-hitelesítést.
A pontossági mező null/ismeretlen, nem a kis ÉNy-i illesztési reziduum.
A folyamatban levő útvonal-kontrollokat nem állítjuk ennek a kiadásnak az
igazolásává. Későbbi eredmény külön csomagban kezelendő.

A mostani jogi/kataszteri határ és a térkép újrafelhasználási licence nincs
igazolva. Az ODbL az OSM-kalibrációs adatokra vonatkozik, nem automatikusan
a teljes önkormányzati térképre.

Reprodukció, hálózat nélkül:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-first-inferred/derive.py --check
Előállítás --check nélkül. Függőségek: numpy, scipy, Pillow, shapely, pyproj.
A független auditor és a teljes, fájlonkénti hash-lista a csomag része.
