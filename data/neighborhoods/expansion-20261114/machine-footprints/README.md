# Városrésznév hozzárendelése meglévő térképi felülethez

**759 becsült keresési terület, 330 településről**, közülük 690 névhez a korábbi elsődleges, becsült, tervezési és 424 alakzatos gépi csomagban még nem tartozott kiválasztott poligon.

Az országos OpenStreetMap-kivonatból azoknak a **már megrajzolt, név nélküli lakóterületeknek és kiskertes területeknek** az eredeti poligonját vettük át, amelyek pontosan egy különböző, településhez rendelt `quarter`, `suburb` vagy `neighbourhood` névpontot tartalmaznak. Az adott névpont nevét rendeltük a felülethez. Ez a név és a felület **becsült összerendelése**: a forrásban megrajzolt lakóterület nem feltétlenül azonos az egész városrész kiterjedésével.

Nem készült kör, Voronoi-felosztás, konvex burok, új határvonal vagy településhatárhoz vágás. Minden koordináta egy valódi OSM-terület eredeti tagvonalaiból származik. A felületek 3000 m² és 10 km² közé esnek. Ha ugyanazon névhez több egymásba ágyazott felület tartozik, először a lakóterületi felületet, azon belül a nagyobb területet választjuk. Az alternatív forrásalakzatok is megmaradnak.

- `features.geojson`: a 759 kiválasztott, névvel ellátott keresési terület.
- `raw-source-footprints.geojson`: mind a 762 megfelelő forrásalakzat, így a név szerinti kiválasztás nem veszít el forrásgeometriát.
- `summary.json`: településenkénti darabszám, a forrás-PBF és névpontállomány ellenőrzőösszege, kiválasztási szabályok.
- `validation.json`: 759 érvényes geometria, 759 változatlan forráskoordináta-sorozat, 759 tartalmazott névpont.
- `extract.py`: a teljes helyi kivonatból újra elvégzi az adatgyűjtést. A futás ebben a környezetben körülbelül 28 másodpercig tartott.

A rekordok `method: named_point_source_footprint_estimate`, `estimated: true` és `semanticFootprint: true` jelöléssel rendelkeznek. A `source` az eredeti OSM-területet, a `namePoint` a név eredetét azonosítja. Az összevont katalógusban ezek a valódi városrészpoligonok és térképből becsült városrészhatárok után, a puszta pontból képzett körök előtt választhatók.

Újraépítés a tároló gyökeréből, telepített `osmium` és `shapely` Python-csomagokkal:

```sh
OTTHONRA_NEIGHBORHOOD_PBF=/letoltott/hungary-latest.osm.pbf python3 data/neighborhoods/expansion-20261114/machine-footprints/extract.py
```

A PBF-nek a `summary.json` által rögzített SHA-256 ellenőrzőösszeggel kell rendelkeznie; az eltérő pillanatfelvételt a program elutasítja. A forrás időszelete 2026. november 12. Az adatok ODbL-1.0 licencűek, forrásmegjelölésük: © OpenStreetMap contributors. A gyűjtemény nem állít hivatalos határpontosságot vagy országos teljességet.
