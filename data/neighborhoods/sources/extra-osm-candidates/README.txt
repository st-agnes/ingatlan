Alternatív OSM-felületek – kutatási leltár, nem városrészhatár-kiadás

A helyi, ellenőrzött 2026-11-12-i teljes magyarországi PBF-ben megvizsgáltuk az
elsődleges gyűjtésből kimaradt megnevezett területcímkéket: boundary=place,
admin_level=12–15, place=borough/city_block/subdivision/locality/hamlet/village,
valamint a megnevezett lakó- és kiskertes területeket. Az elsődleges selector
által már kezelt suburb/quarter/neighbourhood és admin9–11 elemek kimaradnak.

Eredmény: 418 forrásobjektum, 409 érvényes eredeti felület. Az alternatív
címkék között nem találtunk új, kellően igazolt magyar városrészhatárt.
A 9 össze nem állítható objektumhoz nem rajzoltunk záróélt, nem javítottunk
geometriát. A területi hozzárendelés egész felületre követelt önkormányzati
lefedést használ; szomszédos települést érintő felületek feloldatlanok maradnak.

Külön kutatási réteg: landuse-proxies.geojson
  19 tényleges lakó-/kiskertes körvonal, 14 településről.
  18-hoz névvel vagy megadott névváltozattal egyező OSM-városrészpont tartozik;
  Péterpusztához a pécsi önkormányzati névjegyzék biztosít névi alátámasztást.
  A névegyeztetés kis-/nagybetűt, ékezetet, írásjelet és szóközt normalizál.
  Ez a név helyét támaszthatja alá, a városrész kiterjedését nem.
  A lakóterület csak egy része lehet a városrésznek, vagy túlterjedhet azon.
  Minden elem boundaryKind=landuse_proxy, estimated=true,
  canonicalNameIsNeighborhood=false, usableForAddressAssignment=false.
  Az elsődleges városrész- és a külön becsültvárosrész-regiszterhez nem adtuk.
  Városrész- vagy települési lefedettségi jóváírás: nulla.

Külön nem városrészi felület: settlement-surfaces.geojson
  Gödörállás (Ladánybene) eredeti, hamlet+residential címkéjű felülete.
  A KSH Gödörállásidűlőt külterületként sorolja. Az OSM-városrésznévpont
  önmagában nem bizonyítja, hogy az eredeti felület városrészhatár lenne.

Kifejezetten kizárt példa: Varga Tanya Hotel, Konferencia és Szabadidő Központ
(osm:way:525574316) tourism=hotel címkéjű, még ha egy közeli OSM quarter-pont
névváltozata hozzá is kapcsolható. Nem kerül a 19 elemű proxy-rétegbe.
Fagyöngy lakópark csak egy city_block; a 7 boundary=place objektum külföldi
régiót jelöl. Ezek sem jelentenek magyar városrészhatár-bővítést.

A source-areas.geojson mind a 409 eredeti, változatlan felületet megőrzi a
forráscímkékkel, azonosítókkal és az összes vizsgálati döntéssel. Az audit.json
külön indokolja a besorolásokat. A tag-inventory.json csak az első címkeolvasás
pillanatképe, ott a geometria összeállítása még nem történt meg; az inventory.json
már a teljes összeállítást tartalmazza. A manifest.json minden fájlt SHA256-tal köt.

Az eredeti OSM-csúcsokból libosmium állítja össze a meglévő gyűrűket. Nincs
puffer, pontból generált terület, levágás, egyszerűsítés, illesztés, utólagos
zárás, becsült összekötő szakasz vagy geometriát javító művelet. A proxy-réteg
koordinátái strukturálisan azonosak az eredeti felület-leltár koordinátáival.

Offline előállítás a tároló gyökerében:
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/extract-extra-areas.py
Csak címkeleltár:
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/extract-extra-areas.py --scan-only
A teljes PBF és a már megőrzött országos település-/névpontforrás szükséges.
A program nem végez hálózati kérést, és nem módosít központi regisztert.

Forrás: OpenStreetMap, 2026-11-12T21:23:05Z magyarországi pillanatkép.
Licenc: ODbL-1.0. Forrásmegjelölés: © OpenStreetMap contributors.
https://www.openstreetmap.org/copyright
