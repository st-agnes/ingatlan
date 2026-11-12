# OpenStreetMap-források

Ezek a fájlok a `scripts/neighborhoods/fetch-osm.mjs` korlátozott, városonként futó lekérdezéseinek eredeti válaszai. A `.source.json` fájl rögzíti a települést, végpontot, lekérdezést, adatállapotot és az eredeti válasz SHA-256 ellenőrzőösszegét. A `summary.json` a sikeres, üres és hibás lekérdezéseket is megkülönbözteti.

Forrás: © OpenStreetMap contributors. Az adatbázis az Open Data Commons Open Database License (ODbL) feltételeivel használható újra:

- https://www.openstreetmap.org/copyright
- https://opendatacommons.org/licenses/odbl/1-0/

A nyers válaszokat nem javítjuk vagy egyszerűsítjük. A külön előállított GeoJSON a tényleges OSM-szakaszok csúcsaiból, közös végpontok összekapcsolásával készül; nyitott vagy hiányos határt nem zárunk le kitalált vonallal. A geometriai ellenőrzés nem jelent hivatalos vagy házszintű pontossági minősítést.
