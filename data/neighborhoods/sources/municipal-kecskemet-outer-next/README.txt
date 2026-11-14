Kecskemét – Petőfiváros I. és II., történeti forráskörvonalak

Importálandó fájl: petofi-source-raster.geojson (két finom forrásjelölt)
Regiszterrekord: registry-entry.json

Petőfiváros I.:881 csúcs, kb.1314460m².
Petőfiváros II.:407 csúcs, kb.372571m².

Módszer
-------
A két alakzat a2021-es önkormányzati Megalapozó VizsgálatII.kötet169.PDF-
oldalán,167.nyomtatott oldalán közölt79.ábra külön feliratozott fekete
körvonalát követi. Az eredeti beágyazott1694x1202JPEG bájtjai változatlanok;
a kiadói PDF208-as képi objektumával való azonosság külön ellenőrzött.

Kézzel kiválasztott vonalpontok vezetik a sötét forráspixelek folytonos láncát.
Minden sűrű pont tényleges forráspixel(maxRGB45), és minden lépés legfeljebb
1pixeles szomszédlépés. A hiányzó összeköttetés hibát okozna; nincs kitalált
résáthidalás. A nyers pixelpontok, a kézi pontok, a közös határszakaszok és az
összes kapcsolódás megmarad a raster-pixel-trace.json fájlban. Csak pontosan
kollineáris pontok maradnak ki az exportból, nulla alakzatkülönbséggel.

Öt szó szerinti jelenlegi OSM-csomópont földrajzi koordinátái és kézzel
azonosított régi képi csomóponthelyek adják az affin georeferálást. A teljes
mátrix, kontrollpontok, képi illesztési hibák és eredetük a raster-georeference.json
fájlban vannak. A kód ellenőrzi a kontrollok egyezését az archivált tényleges
OSM-csomópontokkal és újraszámolja az illesztés mátrixát.

FONTOS: a kimeneti földrajzi csúcsok georeferált JPEG-pixelek, NEM OSM-csúcsok.
A mai Vízmű főút egy szakasza a régi rajzolt határtól eltér. Ezért nem annak
nyomvonalával helyettesítettük a forrás fekete vonalát. Az OSM-utak más
módszerrel készült diagnosztikai változatai nem importálandók.

Minőség és korlátok
------------------
Mindkét körvonal szó szerint zárt, érvényes, lyukmentes és Kecskeméten belüli.
A közös rész pontosan ugyanaz a pixelút; nincs belső átfedés. Független
ellenőrzés igazolja az eredeti rasterazonosságot, valódi forráspixeleket,
kollineáris tömörítés változatlanságát és a végleges földrajzi rekonstrukciót.
Ez a raster-independent-review.json fájlban van megőrizve.

A forráson szereplő finom nevek2021-ből igazoltak; a mai pontos névhasználat
külön ellenőrzése hiányzik. Az alapul szolgáló légifotó felvételi ideje ismeretlen.
A képi kontrollhelyek és a vonalvastagság bizonytalansága miatt az illesztési
hiba NEM az abszolút határpontosság. Aktuális jogi/kataszteri határ vagy
címhozzárendelés nincs igazolva. Minden rekordnál a címhozzárendelés kikapcsolt.
Az önkormányzati térkép újrafelhasználási licence nincs külön igazolva; az ODbL
az OSM-georeferálási kontrollokra vonatkozik, nem automatikusan a teljes térképre.

Reprodukció a tároló gyökeréből:
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-kecskemet-outer-next.py --check
A --check csak összehasonlít; normál előállítás --check nélkül. A --extract
kizárólag a helyi teljes Magyarország PBF-ből újragyűjti a nyers utakat;
a négyszög csak adatgyűjtési terület, soha nem válik városrészhatárrá.

Nem importálandó: *-diagnostic.geojson, raster-trace-diagnostic.geojson,
explore_outer.py és trace_raster_diagnostic.py. Ezek a munka korábbi hipotéziseit
őrzik; a Vízöntő utcás kezdeti felosztást a forráskép alapján elvetettük.
A nyugati Felsőszéktó–Felsőcsalános összetett forrásterületet nem másoljuk át
két önálló név alatt; ebből a batchből nem exportáltuk. A175.PDF-oldali81.ábra
még öt további, feldolgozatlan finom körvonalat tartalmaz, tehát a kecskeméti
önkormányzati forrás feldolgozása még nem teljes.
