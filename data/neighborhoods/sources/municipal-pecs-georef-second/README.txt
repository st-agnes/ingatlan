PÉCS – MÁSODIK KONTROLLAZONOSÍTÁSI AUDIT, 2026-11-14

Eredmény: két új, valóban látható keleti képi metszés és ezek egyedi mai
OSM-jelöltjei megőrizve; igazolt országos regisztráció továbbra sincs.
Új primary rekord: 0. Új poligon: 0. Új illesztési modell: 0.
claimedAbsoluteAccuracy=null; házszintű cím-hozzárendelésre nem használható.
A döntés részletes indoka és a továbblépés feltételei: decision.json.

A független képi olvasó nem nézett modellt vagy földrajzi rávetítést.
Az independent-source-image-review.json és öt nearest-neighbour képkivágás
külön rögzíti a ténylegesen látható jeleket és a világazonosság korlátait.

1. A látható L-könyök valóban ~[160,167]; a korábbi [160,162] egy egyenes
   szár pontja. A mai ring457/node684770966 iránysorozata formailag egyezik.
   A történeti és mai adminisztratív vonal azonosságát ez önmagában nem bizonyítja.
2. Az északi mélyedés tényleges sötét sávja x291–294, y84–85 körül lapos és
   elmosódott. A korábban javasolt [294,86] világosabb alsó perem. A mai
   ring386 és ring389 kettős mélyedését a kép nem választja el biztosan.
3. Keleten a szürke diagonál a fekete szaggatott vasúttal ~[565,151]-nél,
   a sárga úttal ~[572,163]-nál ténylegesen keresztezi egymást. A mai jelöltek:
   - rail64 way208759579 × Pécs575380 határway54309371:
     18.3541173305, 46.1167053168;
   - road6 way312297473 × ugyanazon határway:
     18.3573198267, 46.1133138698.
   Ezek eredeti, szomszédos OSM-szakaszok számított síkbeli metszései,
   nem szó szerinti OSM-csomópontok. A forrás keresztezési sorrendje és
   irányai konzisztensek; a két jelölt ugyanazt a szürke adminvonalat használja.
   A forráson itt nincs olvasható út-/vasútszám vagy adminvonal-azonosító.
   Ez két konkrét megfeleltetési hipotézis, nem két független abszolút kontroll.
4. A valódi mai road6/rail64 híd metszése külön megvan a PBF-ben, de a
   feltételezett forrásbeli találkozást ~[467,180]-nál lila kitöltés és vastag
   kontúr takarja. A látható megközelítő szárakból nem gyártunk metszéspontot.

A source-target-topology-proof.json egy új, közvetlen eredeti PBF-olvasásból
37 teljes way, 715 eredeti node, a Pécs-reláció és négy számított metszés adatait
őrzi. Minden korábban archivált boundary-way/node és a kiválasztott utak,
vasútszakaszok nodeRefs/koordináta/tag adatai pontosan egyeznek. A teljes
regionális vasúti keresés is megmarad: local-rail-original.geojson, 369 way,
2798 node. A kiválasztás nem vágja vagy igazítja a forráswayeket.
A source-current-separate-panels.png egymás melletti source-only és mai
EOV észak-fent paneleket mutat; nincs georeferált rávetítés.

Az eredeti teljes önkormányzati PDF, a 48./63. oldal két JPEG-képe byte-azonos
ellenőrzést kapott. A PDF összes objektumszótárában vizsgált geotérbeli kulcsok
és a két JPEG EXIF-adatai nem tartalmaztak használható regisztrációt.
Ez nem zárja ki külső eredeti GIS/adatszerkesztési fájlok létezését.
Részletes keresési tartomány és eredmény: source-metadata-review.json.

A jelen kör nem futtat új illesztést a bizonytalan célpárokra. A belső RMS,
ugyanazon útvonalon mért kereszteltérés vagy korrelált adminvonal-ellenőrzés
nem pótolja a hiányzó pontazonosságot, és nem ad abszolút hibasugarat.
Nincs névpont-igazítás, tetszőleges összekötés, puffer, snap vagy repair.
A municipal-pecs-first-inferred és a municipal-pecs-grounded-next változatlan.
A 33-as fagyasztott GeoJSON SHA256 továbbra is:
3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95.
A regiszterek és az országos exportok nem változtak.

Hálózatmentes újraellenőrzés a repository gyökeréből:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-georef-second/check-audit.py
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-georef-second/audit-current-controls.py --check
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-georef-second/audit-source-metadata.py --check
A check-audit.py saját számításként Shapely-metszéseket használ a szerzői
szakasz-determinánsok helyett; a forrásképi mintapixeleket és a kivágásokat is
visszaellenőrzi. A PROJ hálózat tiltott. A vetületi művelet pontossági metaadata
nem a térkép vagy a regisztráció pontossága.

Forrás: https://logoweb.pecs.hu/download/koncepcio/ITS.pdf
PDF SHA256: 995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1.
OSM PBF SHA256: 224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a.
OSM: OpenStreetMap contributors, ODbL 1.0. Az önkormányzati térkép nyilvános
elérése nem bizonyít újrafelhasználási engedélyt; a történeti név- és jogi
státusz, felmérési pontosság külön továbbra is nincs igazolva.
