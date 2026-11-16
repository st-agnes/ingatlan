# Shard 3 – első befagyasztott csomag

16 terület kilenc településről. Beemelendő: `features.geojson`. Az itt szereplő területek a 64-es részfeladat egy része; a többi név gyűjtése folytatódik.

Hét tényleges, teljes forráskontúrhoz kapcsolt névbecslés és kilenc fizikai térkép alapján felvett körvonal készült. A teljes telephelyet választottuk a belső épület vagy park helyett: például Varga tanyánál a teljes névvel ellátott szabadidő-/szálláskomplexum szerepel, nem csak a kisebb belső park. A fülöpházi név magát a körülkerített oktatóközpontot jelenti. Göci esetén a tényleges, névvel ellátott park/BMX-terület szerepel; ez nem bizonyít nagyobb, ugyanilyen nevű lakónegyedet.

A kézi körvonalak Fót két lakóterületét, Vecsés vasúttól délre/nyugatra eső teljes Halmitelep utcahálózatát, két új lakóparkját és a Fő út melletti lakótelepi sávot, valamint Nagytarcsa három lakóterületét fedik. A nagytarcsai Petőfi lakótelep négy háztömbjét és közös udvarát önkormányzati névazonosítás is alátámasztja. Halmitelep áttekintő ablakát a felvétel előtt kiszélesítettük, így a térképkép széle nem vágja el a városrészt.

Minden rekord `estimated=true`, `lowConfidence=true`. Nem hivatalos, jelenlegi telekhatárok. A bizonytalan szélső átmenetek és az intézményi/parknevek jelentésbeli korlátai rekordonként szerepelnek. Nem készült kör, névpontból számított doboz, Voronoi-felosztás vagy pontburok.

A `specifications.json` a forráskontúr-azonosítókat, a regisztrált fizikai térképen felvett töréspontokat és az adott névre vonatkozó forráshivatkozásokat tartalmazza. A tényleges térképi források a szomszédos `../../contexts/` változatlan archívumában vannak. A saját `../maps/` állományok csak értelmezési térképek; a megjelenítési keret nem kimeneti geometria. A `summary.json` rögzíti minden szükséges forrás SHA256 értékét.

Újraépítés és ellenőrzés a tároló gyökeréből:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round4/shard-3/verify.py batch-01
```

A geometriák technikailag érvényesek, a nevek egyediek, a névpontok fedettek, az offline újraépítés bájtra azonos. Az OSM-forrás ODbL-1.0, © OpenStreetMap contributors; az eredeti tagek, objektumazonosítók és URL-ek megmaradnak. Az alkalmazás és adatbázisa nem módosult.
