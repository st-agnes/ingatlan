# Pécs és Szeged: finomabb területek közelítő körvonalai

34 új alakzat: Pécs 25, Szeged 9. Szeged további egy korábbi körös neve, Makkosház, a már meglevő Makkosháza névváltozataként javasolt összevonásra. A forrástérkép és a mai névpont ugyanazt a negyedet jelöli; nem készítünk még egy poligont a név végződésének változatához.

Az új finomabb körvonalak **kézi becslések** a ténylegesen tárolt OSM út-, vasút-, vízfolyás- és telekelérési vonalak, a meglevő tágabb történeti/önkormányzati térképi felosztások és a névpontok elhelyezkedése alapján. A finom határvonalak nincsenek így kinyomtatva a régi térképeken. Nem állítunk jogi vagy felmérési pontosságot. A tágabb korábbi városrészek és az új kisebb területek átfedése hasznos és szándékos.

A két nyers úthálózati GeoJSON 17 493 pécsi és 10 723 szegedi szó szerinti OSM-vonalat őriz, változatlan koordinátákkal, way-azonosítóval, way-verzióval és node-hivatkozásokkal. A teljes ország-PBF nélkül is újraépíthetők a végső poligonok: a `*-registration.json` vetületi paraméterei és a `*-traces.json` kézi pixellistái megmaradnak. A mentett diagnosztikai térképek ugyanezekből az úthálózatokból készültek; halvány zölddel a korábban már meglevő nagyobb forrásterületek látszanak háttérként.

Fájlok:

- `pecs-features.geojson`: 25 alakzat.
- `szeged-features.geojson`: 9 alakzat.
- `alias-suggestions.json`: Makkosház/Makkosháza egyértelmű helyi névváltozat.
- `road-extraction.json`: forrás-PBF, dátum és kinyerési mód.
- `packet-summary.json`: ellenőrzések és a kész geometriai állományok SHA-256-a.

Újraépítés `pyproj` és `shapely` csomagokkal:

```sh
python3 data/neighborhoods/expansion-20261114-next/pecs-szeged/build.py
```

Csak a diagnosztikai úttérképek újrarajzolásához kell Pillow; a végső poligonok generálása nem olvassa a PNG-ket. A nyers forrásvonalak újbóli PBF-kivonásához `osmium` és a megjelölt PBF szükséges. A meglevő nyers GeoJSON-ok megtartása ezt a nagy letöltést és újrakinyerést feleslegessé teszi a poligonok későbbi újraépítéséhez.
