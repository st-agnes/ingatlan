# Úthálózatból becsült keresési területek – 2026-11-15

Az előző kör nagyobb utakat, vasutakat és vízfolyásokat használó felosztását
kiegészítjük a ténylegesen térképezett lakóutcákkal, lakó-pihenő övezeti és
gyalogos utcákkal. A forrás beépített területén belül zárt úthálózati cellákat
keresünk, amelyekben egy még poligon nélküli városrész névpontja található.

**Ezek alacsony megbízhatóságú, részleges keresési területbecslések.** Egy cella
akár csak a városrész néhány tömbjét fedheti le: nem bizonyítja a városrész teljes
határát vagy területi lefedettségét. A nevek közötti pontazonosítás becslés;
a tényleges utakat és zárt cellákat megőrizzük. Nincsenek pontból számolt körök,
Voronoi-cellák, mesterséges egyenes osztóvonalak vagy teljes településnyi közös
poligonok sok különböző városrészhez.

Forrás: OpenStreetMap, ODbL-1.0, © OpenStreetMap contributors; a helyben archivált
országos kivonat 2026-11-12-i állapotából. A forrásvonalláncok eredeti azonosítói,
címkéi, URL-jei, verziói és időbélyegei a `source-barriers.geojson` állományban
szerepelnek; a beépített területek a `source-contexts.geojson` fájlban.

Az előző kör alapállapotát a `baseline-known-keys.json` őrzi. Budapest,
Nyíregyháza, Szombathely, Ózd és Szekszárd külön gyűjtőcsomagot kapott, ezért
ebből a körből kihagytuk. Egy névhez a megfelelő méretű cellák közül a legnagyobbat
választjuk; a szülőnevek átfedése megengedett, de egy cellához több még hiányzó
név nem rendelhető. A kihagyások és alternatívák külön JSON-fájlokban maradnak.

Hálózat és új országos kivonat nélkül újraépíthető:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115/national-cells/extract.py --saved-sources
```

A `features.geojson` tartalma determinisztikus; a futási idő és a jelentés
időbélyege futásonként változhat. A végső darabszám a `summary.json` fájlban van.
