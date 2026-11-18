# Meglévő gépi poligonok gyors átvétele

A 2026. november 14-én megadott gyűjtési stratégia alapján **424 további, településen belül egyedi nevű terület** került ebbe a csomagba, **220 településről**. Debrecen külön munkacsomagban szerepel. A korábban már kiválasztott 506 elsődleges, 191 becsült és 31 tervezési alakzatot ez a csomag nem ismétli meg.

- `features.geojson`: az eredeti WGS84 koordinátákkal átvett alakzatok, forrásokkal és település-hozzárendeléssel.
- `summary.json`: bemeneti fájlok ellenőrzőösszege, kihagyott duplikátumok és külföldi/nem hozzárendelhető rekordok.
- `validation.json`: mind a 424 geometria szerkezeti ellenőrzése és koordinátáinak visszaolvasása az eredeti forrásból.
- `collect.py`: újraépítés: `python3 data/neighborhoods/expansion-20261114/machine/collect.py` a tároló gyökeréből. Csak a Python standard könyvtárát használja.

Az új nevekből 383 az országos OSM-kivonatban már meglévő, megnevezett lakóterület, kiskert, lakópark vagy helyi terület eredeti felülete; 35 a korábbi katalógusból szemantikai megfontolások miatt kihagyott név (például budapesti kerület vagy tágabb városrész); 6 korábban településhez nem rendelt, de gépi poligonnal rendelkező név.

Az OSM lakóterületi/kiskertes felületek `semanticFootprint: true` jelölést kapnak. Ezek a forrásban megrajzolt, keresésre használható területek; kiterjedésük nem feltétlenül egyezik az azonos nevű, hétköznapi értelemben vett teljes városrészével. A történeti, tágabb vagy átfedő felosztások is megmaradnak. A `sourceRole`, `method`, `estimated`, `provenance` és `coordinateAccuracyNote` mezők megkülönböztetik a forrás típusát és bizonytalanságát.

A korábban település nélkül tárolt alakzatoknál egy, a poligon belsejében számított pontot rendeltünk az országos településhatárokhoz. Ez csak település-hozzárendelés: a poligonokat nem vágtuk, illesztettük vagy javítottuk. A határon átnyúló területek eredeti alakja megmarad. A 16 hozzárendelés nélkül maradt forrásrekord külföldi vagy magyar településhez egyértelműen nem rendelhető terület.

Az összes bemeneti alakzat már a tárolóban volt. Új névellenőrzést vagy határvonal-felülvizsgálatot nem végeztünk. A csomag önmagában nem állít országos teljességet, és az alkalmazás adatbázisát nem módosítja. Az OSM eredetű adatok ODbL-1.0 licencűek, forrásmegjelölésük: © OpenStreetMap contributors. A többi rekord saját forrásmegjelölése megmarad a `provenance.source` mezőben.
