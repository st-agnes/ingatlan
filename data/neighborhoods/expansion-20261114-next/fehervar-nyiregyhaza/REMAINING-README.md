# Második részcsomag: további 18 helyi becslés

Új állomány: `remaining-features.geojson`. Az előző 62 alakzat és valamennyi korábban rögzített geometriai forrásfájl változatlan maradt.

- Székesfehérvár: 12 név — Almássytelep, Demkóhegy, Fecskepart, Feketehegy, Kadocsa, Királykút, Oncsatelep, Palotavárosi lakótelep, Papagáj-telep, Szedreskert, Sóstó, Tóváros.
- Nyíregyháza: 6 név — Fáklyás lakópark, Green City lakópark, Ipari park, Jókaitelep, Ókistelekiszőlő, Újkistelekiszőlő.

## Módszer

A már megőrzött tényleges utcák, főutak, vasutak, vízfolyások és településhatárok zárt celláit használjuk. Fehérváron ezeket az önkormányzat 2021-es térképén ténylegesen körülrajzolt városrészen belül vágjuk ki. Az adott cellában pontosan egy, ebben a körben még hiányzó célnevet engedünk meg. A már lefedett, tágabb szülőterület neve nem érvényteleníti a kisebb területet, hiszen a felosztási szintek átfedhetnek.

Elsőbbséget kap az elkülönülő főúti cella; ahol ilyen nincs, a helyi utcák által határolt tömb következik. A `neighbourhood` típusú helyek, kis lakótelepek és lakóparkok cellája legfeljebb 0,8 km², más célterületeké legfeljebb 3 km². Ezek felső szűrési korlátok, nem pontból számított körvonalak. A túl tág, 2,59 km²-es Cúgosrész I. jelöltet nem vettük fel. Almássytelepnél a túl nagy főúti cellát kisebb tényleges utcacella váltotta fel.

A módszer `physical_barrier_cell_estimate`; a pontossági rang alacsony. A cella a városrész csak egy tömbjét vagy egy tágabb környezetet is lefedhet: **nem állítjuk, hogy ezek a teljes városrész megfigyelt határai**. Kör, puffer, Voronoi, konvex burok, legközelebbi névpont szerinti felosztás és kitalált városi határ nem készült.

## Nyitva hagyott helyek

A feldolgozott helyi térképek és vonalak alapján most nem adtunk új geometriát ezekhez:

- Székesfehérvár: Laguna Lakópark, Velinszky László-lakótelep, Ősz utca.
- Nyíregyháza: Báthory-lakópark, Cúgosrész I., Kerti lak, Kun lakópark, Sóstóhegyi lakópark, Tópart, Őzdomb-lakókert.

Ez nem állítja, hogy más forrásból ne lennének felderíthetők. A két, egymáshoz közeli fehérvári névpár — Palotaváros/Palotavárosi lakótelep és Ősz utca/Velinszky-lakótelep — lehetséges névazonosságát külön forrással érdemes majd tisztázni; pusztán a közeli koordináták alapján nem vontuk össze őket.

A nyíregyházi Alispántanya, Vadastanya, Nagylapos, Samókabokor, Felsőbadúrbokor, Salamonbokor, Szabadságbokor és a Belső lakóterület további célzott forrásfeldolgozást igényel. Ebben a városi utcacellás körben nem rajzoltunk hozzájuk általános városhatárt vagy kitalált mezőgazdasági körzetet.

A korábbi, lazább méretkorlátú próbálkozás geometriái diagnosztikai célból a `remaining-initial-candidate-geometries.geojson` fájlban megmaradnak. Ez nem importálandó fő réteg. A kiválasztott 18 a `remaining-features.geojson` fájlban található.

Újraépítés hálózat és az országos PBF nélkül, a már itt tárolt forrásokkal:

```sh
python3 data/neighborhoods/expansion-20261114-next/fehervar-nyiregyhaza/extract-remaining-cells.py
```

Szükséges Python-csomagok: `shapely`, `pyproj`. A forrásvonalak ODbL-1.0 OpenStreetMap-adatok, © OpenStreetMap contributors; a fehérvári PDF forrása és SHA-256-a a rekordokban megmarad.
