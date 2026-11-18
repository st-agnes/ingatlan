# Ismert városrésznevek és folytatható hiánylista

Az állományok az OSM `suburb`, `neighbourhood` és `quarter` pontjait, a már összegyűjtött városrészi és tervezési névjegyzékeket, valamint a kiválasztott poligonokat egyesítik. A források közötti írásjel- és szóközeltéréseket, továbbá a keresési területkatalógus explicit névváltozatait összevonják. A magyar ékezetek megmaradnak.

Ez az **eddig megismert nevek leltára**, nem Magyarország összes városrészének teljes jegyzéke. A százalék az adott véges névlistán belüli poligonellátottságot méri; országos készültségi százalékot nem állít. A KSH tanyákat és majorokat is tartalmazó teljes településrész-listáját nem használjuk városrészi nevezőként.

- `known-names.json`: a név, a névváltozatok, a meglévő poligonok és a forráshivatkozással megőrzött pontok.
- `priority-cities.json` / `.csv`: negyven nagyobb, fontosabb város munka- és hiánylistája; a sorrend prioritási lista, nem pontos népességi rangsor.
- `municipality-backlog.json`: valamennyi, az ismert nevek leltárában szereplő település.
- `reference-benchmarks.json`: forrásonkénti névlefedettség, forrásidőszak és a teljességre vonatkozó megállapítás külön mezőben. Budapesten az azonos nevű, eltérő kerületi városrészek miatt a névszám nem minden esetben azonos a területi identitások számával.
- `provisional-fallback-features.geojson`: **külön, opcionális körbecslések**, a fő poligonkatalógusba nincsenek regisztrálva, és nem növelik a térképi/poligonos lefedettséget. Csak olyan ismert pontokhoz készülnek, amelyekhez a pillanatnyilag összegyűjtött katalógusbemenetekben nincs poligon. Ez nem jelenti, hogy máshol sem létezik használható térkép.

Új poligoncsomagok beolvasása után a tároló gyökerében:

```sh
python3 data/neighborhoods/expansion-20261114/inventory/build.py --catalog data/neighborhoods/search-areas.geojson
python3 data/neighborhoods/expansion-20261114/inventory/build-provisional-fallback.py
```

A körbecslés 64 csúcsból áll, a gyűrű zárt. A sugár `suburb` pontnál 600 méter, `quarter`/`neighbourhood` pontnál 300 méter, a legközelebbi eltérő ismert név ponttávolságának 45%-ával korlátozva, legalább 75 méterrel. A pontállományban nincs külön `isolated_dwelling` kategória, ezért önkényes falusi kategória vagy kitalált középpont nem készül. A körök a településhatárra nincsenek levágva. Pontosabb térképi vagy leírásból becsült terület megtalálásakor a kört le kell cserélni.

A középpontok OSM-adatok, licencük ODbL 1.0; forrás: © OpenStreetMap contributors. A forrásazonosító, URL és az alternatív pontrekordok minden becslés mellett megmaradnak.
