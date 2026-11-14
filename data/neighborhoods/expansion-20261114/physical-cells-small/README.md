# További 14, térképi vonalakkal határolt becslés

Egy utolsó, korlátozott helyi gyűjtés **14 további névhez** rendelt közelítő keresési területet: Baja 4, Szekszárd 3, Pápa 3, Cegléd 2, Dunakeszi 1, Ózd 1.

Az OpenStreetMap meglévő fő-, másod- és harmadrendű útvonalai, vasútjai, folyó-/patak-/csatornavonalai és a településhatár által bezárt térképi felületekből választottunk. Csak olyan 0,08–8 km² közötti felület került be, amelyben pontosan egy különböző városrésznév pontja található, és a névhez az előző gyűjtésekben még nem volt kiválasztott poligon. Egy felület legfeljebb a település területének felét foglalhatja el.

**A bezárt térképi cella a városrész kiterjedésének becslése.** Az útvonalak valódi térképi vonalak, de nem állítjuk, hogy minden ilyen út valódi városrészhatár, vagy hogy a teljes városrész belefér a kiválasztott cellába. Külön szintű útkereszteződések is osztóvonalat képezhetnek. A névpont tartalmazása a hozzárendelés támpontja. Kör, Voronoi-felosztás vagy legközelebbi név szerinti felosztás nem készült.

- `features.geojson`: 14 becsült alakzat `method: physical_barrier_cell_estimate`, `estimated: true` és `semanticFootprint: true` jelöléssel.
- `source-barriers.geojson`: mind a 3010 érintett eredeti úti/vasúti/vízfolyási forrásvonal, OSM-azonosítóval és címkékkel.
- `source-municipalities.geojson`, `source-labels.geojson`: a településhatárok és a 131 vizsgált névpont forrásadatai.
- `all-candidate-cells.geojson`: az összes megfelelő jelölt; ebben a körben mind a 14 bekerült.
- `summary.json`, `validation.json`: városonkénti darabszámok, források ellenőrzőösszege és a 14 érvényes geometria/névpont-tartalmazás ellenőrzése.
- `extract.py`: újraépítés az országos PBF-ből `osmium`, `shapely` és `pyproj` csomaggal; ebben a környezetben 40 másodperc.
- `selection.json`: az eredetileg kiválasztott 14 név, így a reprodukció a később bővülő katalógustól független.

Az egyes alakzatok `boundingSourceWays` mezője felsorolja a poligon határán legalább 25 méteren végigfutó, tényleges forrásvonalakat. EOV-méteres vetületben történt a poligonizálás, a kimenet WGS84 hosszúság/szélesség. Az eredeti vonalak megmaradnak; a belőlük képzett alakzat becslés.

Újraépítés a tároló gyökeréből:

```sh
OTTHONRA_NEIGHBORHOOD_PBF=/letoltott/hungary-latest.osm.pbf python3 data/neighborhoods/expansion-20261114/physical-cells-small/extract.py
```

A már eltárolt vonalakból, településhatárokból és névpontokból az eredeti nagy PBF nélkül is újraépíthető:

```sh
python3 data/neighborhoods/expansion-20261114/physical-cells-small/extract.py --saved-sources
```

Az első gyűjtés az akkor már szereplő neveket kihagyta; a `selection.json` ezt a kiválasztást rögzíti, így a későbbi katalógusbővítés nem változtatja meg az újraépített 14 nevet. A forrás időszelete 2026. november 12., licenc ODbL-1.0; © OpenStreetMap contributors. A csomag nem állít hivatalos határpontosságot vagy országos teljességet.
