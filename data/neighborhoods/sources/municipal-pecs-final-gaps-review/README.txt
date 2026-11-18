PÉCS – A HÉT UTOLSÓ FORRÁSNÉV KÜLÖN, KORLÁTOZOTT FELÜLVIZSGÁLATA
2026-11-14

Ez a csomag két eltérő bizonyosságú állományt tartalmaz:
- source-inferred.geojson: 5 teljesen megfigyelt eredeti forráskontúr,
  becsült földrajzi elhelyezéssel.
- reconstructed-cap-inferred.geojson: 2 külön, alacsony bizalmú rekonstrukció,
  amelyek teljes gyűrűjére sourceContourIsObserved=false.

A 67 dokumentumbeli név végső elszámolása: 65 megfigyelt forráskontúr és
2 részben rekonstruált jelölt. Ez nem 67 hitelesített vagy mai határ.
Egyik új rekord sem primary; claimedAbsoluteAccuracy=null, címhozzárendelés
nem engedélyezett. Új földrajzi kontroll vagy georeferálási modell nem készült.
Az első 33 és a további 27 fagyasztott kohorsz változatlan marad; e csomag
helyi regiszterbejegyzés-javaslatai nem módosítják a globális regisztert.

Az öt megfigyelt kontúr

Kisbalokány és Siklósi külváros külön eredeti, zárt Figure 12 cellák:89 és 92.
A korábbi közös 92-re vonatkozó feltételezés a Kisbalokány felirat bal oldali
kezdőpontját belső pontként kezelte. Az a felirat túllóg a keskeny ékén;
a tényleges fine-outline és szomszédsági olvasás javította a párosítást.
A 12. ábrán a két negyed azonos narancsosztályba esik, más tematikus ábrákon
viszont a Siklósi test barnája és Kisbalokány sraffozott keskeny éke különül el.
A táblázatok eltérő statisztikái ezt külön megerősítik, nem névpontot használunk.

A teljes helyi 316 oldalas PDF szövegét hét névre és névváltozatokra átnéztük.
Teljes utcás határkör nem került elő; projekt-, funkció- és csoportleírásból
nem gyártottunk körvonalat. A 12–15. tematikus ábra azonos 1341×946 képmérete
mellett eltérő eltolás/skála látszik. Hét közös I-körzeti sarok a 12→13 helyi
(-8,-8) pixelkapcsolatát támasztja alá; ez nem általános földrajzi regisztráció.
A végleges két cella mégis közvetlenül az eredeti 12. ábrából áll elő, tehát
másik színmaszk rávetítésére, metszésére vagy vak koordinátaátvételre nincs szükség.

Kisbalokány 223 és Siklósi 1573 eredeti szabad képpontját őrizzük nyersen.
Három külön jóváhagyott 1 pixeles nyomdai/maszkfolt helyreállítása után az
értelmezett alak 224 és 1575 pixel². A külső forrásél változása 0.

M utca teljes, apró Figure 9 grafikai körvonalát külön kézzel követett,
22 pontos eredeti sötétpixel-útvonal adja; területe 18,5 forráspixel².
Ez a térkép önálló megnevezett negyedalakja, nem betű, névpont vagy
általános földhasználati felület. A kicsi raszterméret és térképi általánosítás
korlátja megmarad; nincs geodéziai pontosságállítás.

Murom és Köztemető 12. ábrájának sraffozása több belső szabad fragmentet ad.
Egyetlen fragment nem helyettesíti a teljes megnevezett negyedet. A végleges
manualis gyűrűk tényleges külső sötét forráspixeleken haladnak, minden
szomszédos lépéssel és RGB-adattal megőrizve. Murom 161 pontos útja a teljes
északi szárat és alsó testet követi,1056 pixel². Köztemető 163 pontos útja a
felső keskeny részt, nyugati közös oldalt, délkeleti szélt és teljes alsó
élt követi,1519 pixel². A sraffozó diagonálok belül maradnak. Független képi
QA külön ellenőrizte a teljes negyed külső határszerepét; a puszta sötétpixel-
tagság vagy fragmenttartalmazás nem lett önmagában elfogadási bizonyíték.
A vastag nyomtatott sávban választott képviselő útvonal bizonytalansága
nincs számszerű geodéziai hibakorláttá alakítva.

A két alacsony bizalmú rekonstrukció

Árpádtető látható nyitott lánca 34 lépés és 40,213203436 pixel. A biztos
[328,81] és[329,83] végpont között egy vitás belső pixel:[329,82]. A javasolt
két él 2,414213562 pixel hosszú; a végponti húr 2,236067978 pixel. Az örökölt,
nem hitelesített EOV-rácson e hosszak 78,861 és 73,112 méter, nem pontosságok.
A rekonstruált gyűrű 112 pixel²; az alternatív egyenes húrral 111,5 pixel².

Petőfi-akna látható nyitott lánca 33 lépés és 38,384776311 pixel. A biztos
[501,18] és[503,24] végpont között öt belső pixel negyedhatár-szerepe vitás;
a felső capnál háttér-adminvonal és negyedperem keveredik. A hat javasolt él
6,828427125 pixel; a végponti húr 6,324555320 pixel. Az örökölt rácson 223,308
és 207,067 méter, nem abszolút helyzethiba. A javasolt gyűrű 102,5 pixel²,
az alternatív egyenes húrral 100,5 pixel².

Mindkét teljes sziget a képen belül van, negyedazonosságát és capjának
formáját a 12–15. eredeti ábra is támogatja. A bizonytalan koordinátákat
kifejezetten következtetett szakaszként jelöljük; nem állítjuk róluk, hogy
igazolt határtinta-pixelek. Minden látható láncpont RGB-je, végpont, javasolt
él, pixeles és örökölt-rácsbeli élhossz, alternatív húr és bizonyítékkép
megmarad. Az alternatíva nem konfidenciaintervallum és nem abszolút
hibaburok. A remaining-cap-source-quantification.json az elfogadási döntés
előtti mérési időállapot; a cap-reconstruction-decision.json a külön,
explicit rekonstrukciós döntést rögzíti.

A külön inferred-only besorolás nem változik: mindkét rekonstruált gyűrű
sourceContourIsObserved=false és reconstructionConfidence=low. Teljes
megfigyelt határként, mai hatósági negyedhatárként vagy címek automatikus
besorolására nem használható. A hét névnek nem városkomplementből és nem
szomszéd poligonok lemásolásából készült jelöltje.

Ellenőrzés és rögzített bemenetek

A végleges auditorok külön vizsgálják az eredeti cellák kitett egységéleit,
a konkrét három helyreállítandó pixelt, a három kézi megfigyelt gyűrű minden
sorrendi forráspixelét, valamint a két rekonstrukció őszinte jelöléseit és
összes javasolt élét. A földrajzi átszámítás csak az első kohorsz változatlan
Figure 12→Figure 9 és ÉNy-peremes EOV-mátrixát használja. A másik ábrák kizárólag
forrásazonossági bizonyítékok, új földrajzi modell nem készül belőlük.
A szigorú JS-geometria, egymás közti átfedés és az összes 65 megfigyelt
kontúrral való nemátfedés külön ellenőrzött, javító vágás nélkül.

A gap-source-selected-pages.pdf az eredeti 47/48/61/63/64/65/66/67/68/70/
261/264. oldalát archiválja. Hét térképi JPEG-kép bájtazonosságát ellenőriztük
az eredeti és a kivonat képobjektuma között. A fő konverterek és végső
független auditorok érdemi bemenetei helyi másolatok ebben a csomagban.
A korábbi keresési/negatív/név-review fájlok történeti útvonalakat és
állításokat is megőriznek; a végső index megkülönbözteti a későbbi korrekciókat.

Forrás: https://logoweb.pecs.hu/download/koncepcio/ITS.pdf
Eredeti teljes PDF SHA 256:
995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1.
Korábbi 33 geomSHA:
3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95.
Korábbi 27 geomSHA:
cfdd86a7dc73d6f6a76ebf9a2377a0e7e077992761f3b23fd675abf102c8826a.
Mai névhasználat, jogi/kataszteri kiterjedés és abszolút pontosság ismeretlen.
Az önkormányzati PDF nyilvános elérése nem igazol szabad térkép-újrafelhasználási
engedélyt. Az ODbL a megőrzött OSM-kalibrációs adatokra vonatkozik, nem a teljes
önkormányzati térképre.

Hálózatmentes reprodukció a repository gyökeréből:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-final-gaps-review/derive-final-gaps.py --check
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-final-gaps-review/derive-cap-reconstructions.py --check
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-final-gaps-review/independent-final-gap-audit.py --check
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-final-gaps-review/independent-cap-audit.py --check
  python3 data/neighborhoods/sources/municipal-pecs-final-gaps-review/summarize-final-gaps.py --check
  python3 data/neighborhoods/sources/municipal-pecs-final-gaps-review/freeze-package.py --check
