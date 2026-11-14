Szeged – forrásleírás alapján követett utcai körvonalak
====================================================

2 új poligon, nem2 mai, teljesen ellenőrzött városrész:

* Tarjánváros:924141m²; a2009-es IVS-ben szereplő, a2017-ben elfogadott
  ITS-ben idézett városrészi alosztás. A6 megnevezett út egy zárt kört alkot.
  A2019-es várostörténeti tanulmányban leírt mai Tarján lakótelep kiterjedése
  eltér ettől. A történeti IVS-körvonalat nem állítjuk mai lakótelephatárnak.
* „Felsővárosi lakótelep”:164605m²; a2017-es dokumentumban ekként megnevezett
  4 utcás alosztás, kizárólag planning_unit besorolással. Egy másik városi
  dokumentum ugyanezt a területet kertvárosiasnak írja le: a név és kiterjedés
  viszonya vitás. Ez nem növeli a jelenleg ellenőrzött városrészek számát.

A forrás2017-es mellékletének96. nyomtatott oldalán a számozott városrészi
felosztás külön szerepel a Belső-Tarján akcióterülettől. Nem az akcióterületet,
nem választókörzetet és nem a teljes Felsőváros makroegységet exportáljuk.

Az eredeti PDF letöltése nem sikerült. Nyilvános webes keresőindexből olvasható
a tényszerű utcajegyzék és a környező hatókörleírás; ennek forrása, elérési
módja és kézi tényátirata a source-facts.json fájlban megmarad. A nem letöltött
PDF-hez nem adunk kitalált fájllenyomatot. A szöveget csak tényekké és néhány
szavas idézetté dolgoztuk fel, a teljes dokumentumot nem másoljuk ide.

A körvonalak51 változatlan OSM útszakasz részleteiből állnak. A kimenet minden
egyes éle két eredeti, egymást követő OSM csomópont közötti él. Nincs kitalált
összekötés, puffer, konvex burok, Voronoi, javítás, vágás vagy illesztési
hézagzárás. Mindkét poligon érvényes, lyukmentes, Szegeden belüli, belsejük
nem fedi egymást. Az utcaközépvonalak és osztott útpályák követése közelítés;
ez nem kataszteri felmérés, és az abszolút pontosság ismeretlen.

Az útgeometria ODbL-1.0, © OpenStreetMap contributors. A városi szövegből
tényszerű útnevek és hatóköradatok származnak. Az eredmény nem hivatalos GIS.
Automatikus cím–városrész hozzárendelésre egyik poligon sem használható.

Újragenerálás/ellenőrzés, a már archivált forrásokból, hálózat nélkül:
PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-szeged-next.py
PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-szeged-next.py --check

További pozitív források/akadályok: boundary-obstacles.json.
Kálvária2012-ben elfogadott körvonalleírása megvan, de a mai Bakay Nándor utca
nem éri el egyértelműen a megnevezett vasútvonalat. Móraváros rövid leírása
egy több mint600m-es déli folytatást elhagy. Klebelsberg-telephez a2007-es
helytörténeti kiadvány zárt természetes határokat ad; a nyugati csatorna
egyértelmű térképi azonosítása még hátra van. Ezek további munka, nem annak
bizonyítékai, hogy semmilyen forrás nem létezik.
