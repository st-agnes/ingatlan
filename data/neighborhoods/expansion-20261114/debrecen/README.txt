Debrecen és Kecskemét – gyors, forrásalapú bővítés, 2026-11-14

A felhasználó által pontosított gyűjtési szabályok:
- a gépi poligonok további név-/időszerűség-ellenőrzés nélkül átvehetők;
- a történeti és eltérő hierarchiájú felosztások, illetve átfedések megmaradnak;
- az egyedi helynevek összevonása később a központi katalógus feladata;
- a térképi határok közelítő becslése megfelelő, nem szükséges pontos felmérés.

Állományok:
1. features.geojson: 75 változatlan debreceni ArcGIS forráspoligon.
   A 77 nyers rekordból csak az általános Közterület, valamint a duplikált és
   nyilvánvalóan tévesen címkézett Széchenyikert FID11 maradt ki. A helyes
   Széchenyikert FID67 megmaradt. Az eredeti 77 rekord továbbra is megőrzött.
2. additional-features.geojson: 4 debreceni és 9 kecskeméti új alakzat.
   Köztemető szó szerinti OSM területhatár, a többi közelítő térképi levezetés.
3. maps80-82-features.geojson: 8 további kecskeméti térképi levezetés.
4. rural-features.geojson: 18 további kecskeméti külterületi/belterületi alakzat.

Összesen 114 forrásalternatíva ebben a mappában, központi deduplikálás előtt.
Ebből az első 75 gépi rekord részben már szerepelt a korábbi gyűjteményben.
A három további csomag összesen 39 alakzatot tartalmaz (4 Debrecen, 35 Kecskemét).
Körrel helyettesített poligon ebben a mappában nincs.

A gépi poligonok nem jelentenek felmérési pontosságot. A kézi térképi
levezetések és a vidéki áttekintő térkép illesztése kifejezetten közelítő;
a kis takarásokat, levágott térképszéleket egyenes szakaszok zárhatják.
Az eredeti forrásképek, képi illesztési adatok, kézi pontlisták és forrásnevek
az állományok mellett megtalálhatók. Az ismeretlen térképfelhasználási
feltételeket a metaadatok nem helyettesítik vagy minősítik szabad licenccé.

Újraépítés a tároló gyökeréből:
  python3 data/neighborhoods/expansion-20261114/debrecen/build.py
  python3 data/neighborhoods/expansion-20261114/debrecen/additional-build.py
  python3 data/neighborhoods/expansion-20261114/debrecen/maps80-82-build.py
  python3 data/neighborhoods/expansion-20261114/debrecen/rural-build.py

Az első program Python standardkönyvtárat használ. A többihez numpy,
pyproj, shapely, Pillow, a vidéki térképhez scipy is szükséges.
Ebben a munkakörnyezetben ezek a PYTHONPATH=/workspace/ingatlan/.local/geodata
beállítással érhetők el. A programok nem végeznek hálózati letöltést.

A 80-as/82-es ábra fényképillesztésének rögzített eredményei az inputok;
az újraépítés változatlanul ezeket használja. A képi pontmegfelelések nem
igazolják önmagukban a városrész-határok mai pontosságát.
