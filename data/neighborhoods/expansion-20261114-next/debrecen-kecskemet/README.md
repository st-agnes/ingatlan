# Debrecen és Kecskemét: térképi pótlások

62 település–név szerinti jelölt (Debrecen 30, Kecskemét 32), 69 nyers forrásváltozatból. A központi katalógus még összevonhatja a korábbi nevekkel és névváltozatokkal; ez nem 62 garantáltan új rendszerazonosító. Kör vagy Voronoi-terület nem készült.

## Forrástípusok

- **5 kecskeméti szülőterület:** a meglévő önkormányzati térképcellák uniója. Például Belváros, Széchenyiváros és Petőfiváros a már meglevő kisebb térképi egységek mellett kereshető egész területet is kap.
- **11 natív OSM-változat:** valódi, változatlan lakóparki, ipari és repülőtéri körvonalak. Négy eddig hiányzó debreceni lakópark is szerepel köztük. A kecskeméti ipartelepek egyes/többes számú nevei, illetve a katonai repülőtér és repülőbázis elnevezései névváltozatként megmaradnak. Az eredeti földhasználati körvonal nem feltétlenül egy tágabb történeti városrész határa.
- **53 nyers úthálózati cellajelölt:** tényleges OSM utcák, vasutak, vízfolyások és településhatárok által bezárt területek. Ezekből a közös állományban 47 marad elsődleges változat; ahol rendelkezésre áll önkormányzati szülőterület vagy natív körvonal, az megelőzi a cellabecslést.

A cellák a három különböző részletezettségű úthálózatból választott, egyetlen különböző nevű városrészpontot tartalmazó területek. Ez **közelítő keresési lábnyom**, nem megfigyelt teljes városrészhatár. Lakóparkra legfeljebb 250 000 m², lakótelepre legfeljebb 750 000 m² jelöltet választunk; a kisebb, beépítéshez közelebb álló cella így megelőzi a túl tág keretet. Például Józsaligetnél a 404 000 m²-es tág cella helyett 29 003 m²-es finomabb cella marad. A nyers, kizárt változatok is megmaradnak az `all-road-cell-candidates.geojson` fájlban.

A főutakra, lakóutcákra vagy szervizutakra való bontás, a külön szintű kereszteződések és a helyi névhasználat eltérhet a tényleges városrész kiterjedésétől. A `physical_barrier_cell_estimate`, `semanticFootprint:true` és `qualityScore:15` ezt jelzi. Nincs önálló földrajzi pontosságigazolás. A központi válogatásban a valódi városrésztérképek és natív körvonalak elsőbbsége megmarad.

## Megőrzött adatok és folytatás

- `features.geojson`: település és név szerint egyszer szereplő helyi válogatás.
- `parent-features.geojson`, `native-features.geojson`, `road-cell-features.geojson`: valamennyi nyers változat.
- `context-roads.geojson`: 28 797 tényleges út-, vasút- és vízfolyásvonal teljes OSM-azonosítóval és címkékkel.
- `context-source-areas.geojson`: 6927 eredeti földhasználati/repülőtéri körvonal.
- `context-name-points.geojson`, `context-municipalities.geojson`, `missing-targets.json`: rögzített névpontok, településhatárok és a munkakezdéskor hiányzó nevek. Az újraépítéshez nem kell a pillanatnyi központi hiánylistát használni.
- `kecskemet-parent-inputs.geojson`: a korábbi önkormányzati forráscellák változatlan példányai.

Normál újraépítés a mentett forrásokból, az országos PBF újraolvasása nélkül:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/debrecen-kecskemet/build-parents.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/debrecen-kecskemet/build-native-areas.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/debrecen-kecskemet/build-road-cells.py
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/debrecen-kecskemet/combine.py
```

Az `extract-context.py` csak a kezdeti nyers OSM-forráskivonást ismétli meg az eredeti országos PBF-ből. A normál újraépítéshez minden szükséges geometria és címke megmaradt a csomagban. A forrás OpenStreetMap, ODbL-1.0; a korábbi önkormányzati térképek pontos hivatkozása a komponensekben található.
