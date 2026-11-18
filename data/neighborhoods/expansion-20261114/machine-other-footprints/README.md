# További térképi felületek városrésznévhez rendelve

**196 becsült keresési terület, 102 településről**, közülük 160 névhez a korábbi poligonok és a 759 lakóterületi/kiskertes becslés között még nem tartozott kiválasztott alakzat.

A `machine-footprints` csomag módszerével az országos OpenStreetMap-kivonat további **ipari, kereskedelmi, erdő-, rekreációs, felhagyott, építési és katonai** területi poligonjait dolgoztuk fel. Csak a név nélküli, 3000 m² és 10 km² közé eső, érvényes alakzatok kerültek be, amelyek pontosan egy különböző, településhez rendelt városrész-/negyed-/városkörnyéki névpontot tartalmaznak. Mezőgazdasági táblákat és temetőket ez a gyűjtés nem használ.

A név és a tartalmazó terület összerendelése **becslés**. A poligon minden koordinátája egy már megrajzolt, valódi OSM-felületből származik; új határvonalat, köröket vagy Voronoi-felosztást nem készítettünk. A felület lehet az egész városrésznél kisebb vagy nagyobb. A módszer célja, hogy puszta koordináta köré rajzolt kör helyett lehetőleg valódi térképi támpontot használhassunk.

- `features.geojson`: 196 névhez kiválasztott alakzat.
- `raw-source-footprints.geojson`: mind a 197 megfelelő forrásalakzat, az alternatívákkal együtt.
- `summary.json`: településenkénti darabszámok, OSM-PBF és névpontforrás ellenőrzőösszege, szűrési szabályok.
- `validation.json`: mind a 196 geometria érvényessége, változatlan koordinátái és a névpont tartalmazása.
- `extract.py`: teljes újraépítés az országos PBF-kivonatból; a futás ebben a környezetben körülbelül 32 másodperc volt.

A rekordok `method: named_point_source_footprint_estimate`, `estimated: true` és `semanticFootprint: true` jelölést kapnak. A `sourceRole` megőrzi, hogy ipari, erdő- vagy más területről van szó. Ha a városrésznek rendelkezésre áll valódi városrészpoligonja vagy térkép alapján becsült határa, az összevont kiválasztásban az élvez elsőbbséget.

Újraépítés a tároló gyökeréből telepített `osmium` és `shapely` csomaggal:

```sh
OTTHONRA_NEIGHBORHOOD_PBF=/letoltott/hungary-latest.osm.pbf python3 data/neighborhoods/expansion-20261114/machine-other-footprints/extract.py
```

A forrás-PBF SHA-256 értékét a program ellenőrzi. Az adatok időszelete 2026. november 12. Licenc: ODbL-1.0; forrásmegjelölés: © OpenStreetMap contributors. A csomag nem állít hivatalos városrészhatárokat vagy országos teljességet.
