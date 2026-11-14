# Kis lakóterületek utcahálózati becslése

24 kiválasztott, eddig csak pontként ismert terület: 8 Székesfehérvárról, 16 Nyíregyházáról. A név szerint megjelölt kis lakótelepekhez/lakóparkokhoz és néhány helyi alközponthoz a tényleges OSM utcák, vasutak, vízfolyások és településhatár által bezárt cellát választottuk.

A poligon teljes körvonala valódi térképi vonalakból áll. A név és az egész körülzárt cella összetartozása azonban becslés: lehet, hogy egy nagyobb lakótelep csak egyik tömbjét fogja meg, vagy beépítetlen szomszédos területet is magában foglal. Ezért a módszer `physical_barrier_cell_estimate`, `qualityScore:10`, és nem eredeti városrészhatárként kezelendő. Egy jobb önkormányzati térképi poligon mindig megelőzheti. Kör, Voronoi, pont körüli puffer és konvex burok nem készült.

A 14 817 eredeti forrásvonal, 126 névpont és 2 településhatár megmaradt. A `street-block-selection.json` rögzíti a kiválasztást; az `extract-street-blocks.py --saved-sources` a nagy országos PBF nélkül is újraépíti az eredményt. A források ODbL-1.0 licencű OpenStreetMap-adatok; © OpenStreetMap contributors.

Újraépítés `osmium`, `shapely` és `pyproj` Python-csomagokkal:

```sh
python3 data/neighborhoods/expansion-20261114-next/fehervar-nyiregyhaza/extract-street-blocks.py --saved-sources
```

A fő adatok: `street-block-features.geojson`; az összesítés és a geometriai ellenőrzés külön `street-block-*.json` fájlokban található.
