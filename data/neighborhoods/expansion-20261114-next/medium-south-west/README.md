# Szentes, Ajka és Baja – 26 további városrész

2026-11-14-i kutatási csomag a korábbi körös helyettesítések kiváltására.
Minden új terület becslés, valós, mentett OSM út-, vasút-, vízfolyás- és
településszerkezeti támpontokkal. A szentesi nagyobb területeknél megőrzött
önkormányzati szöveges határleírás is rendelkezésre áll.

| Település | Kimenet | Új poligon |
|---|---|---:|
| Szentes | `szentes-features.geojson` | 11 |
| Ajka | `ajka-features.geojson` | 8 |
| Baja | `baja-features.geojson` | 7 |

Nincsenek körök, Voronoi-területek vagy kisebb városrészként átmásolt teljes
városi poligonok. Az átfedés megengedett: például a Kertvárosi lakótelep
szűkebb terület, mint Kertváros. Minden terület külön `boundaryRationale`
mezőben kap rövid leírást a választott fizikai támpontokról.

## Mit gyűjtöttünk össze?

- Szentes: Felsőpárt, Kisér, Kertváros, Hékéd, Kertvárosi lakótelep,
  Sárgapart, Alsórétiújtelep, Szedertelep, Sitér, Lőrinchát, Gógány.
- Ajka: Babucsa, Belváros, Bányásztelep, Hild-park, Kórházdomb,
  Tósokberénd, Tósok, Élmunkástelep.
- Baja: Istvánmegye, Józsefváros, Szentjános, Újvárosi lakótelep,
  Belváros, Rókusváros, Szállásváros.

Ajkán a három további összetett szülőterület neve nem kapott kitalált
finomfelosztást: Bakonygyepes (Ajkarendekkel), Belváros (Lakóteleppel és
Szőlőheggyel), Bódé (Csingerrel, Csikólegelővel és Iparteleppel).
Ezek külön, megfelelő részekből álló forrásalapú összeállítást igényelnek.

## Források és becslések

A `*-roads.geojson` és `*-areas.geojson` fájlok helyi, hálózat nélkül
feldolgozott magyar OSM PBF-ből származó tényleges vonalak és zárt felületek.
Ezekből a `*-road-map.png` képek közvetlen EOV-koordináta-átszámítással
készültek. Nem egy önkormányzati rasztert kellett néhány pontból elhelyezni.
A mentett kivágás nem teljes utcahálózat: az új szűrés az első forráscsomópont
helyét vizsgálja, ezért hosszú, kívül kezdődő utak/vízfolyások kimaradhatnak.

Szentesnél emiatt a korábbról már megőrzött, 315 koordinátás tényleges Kurca
vonalat külön is megtartottuk: `szentes-extra-water-context.geojson`,
OSM way 591675710. A forrásvonal nincs körrel vagy mesterséges vízfolyással
helyettesítve. A végső becsült határokban az összekötések természetesen
közelítőek lehetnek.

A `szentes-municipal-text-context.json` megőrzi a korábbi IVS-ből származó
Felsőpárt-, Kisér- és Kertváros-határleírásokat. Ezek korábban kinyert,
indexelt szöveges tények; az eredeti PDF térképi geometriáját nem szereztük
meg, így a becsléseket nem állítjuk be szó szerint a dokumentumról másolt
kontúrként. A csomópont- és helyrajziszám-értelmezések durva közelítések.

Ajka és Baja esetén mentett OSM háttérfelületeket és a tényleges utcahálózatot
használtuk. A `broader-source-contexts.geojson` rögzíti a korábban gyűjtött
háttérterületeket; ezeket nem neveztük át változtatás nélkül finomabb részekké.
A becsült körvonalak nem hivatalos, mai közigazgatási határok.

## Újraelőállítás és ellenőrzés

A `target-name-points.json`, `*-registration.json` és `*-traces.json` fájlok
minden névpontot, képi transzformációt és kézzel becsült töréspontot megőriznek.
A végső fájlok újraépítése hálózat és újabb PBF-feldolgozás nélkül:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261114-next/medium-south-west/build.py
```

Általános függőségek: Python 3, Shapely, pyproj. A nyers PBF újabb
feldolgozásához pyosmium, a képekhez Pillow szükséges. Az összes levezetési
bemenet mentve van; a PBF újraolvasása nem kell a végső fájlokhoz.

A `sources.json` rögzíti a forrásokat és a bemenetek SHA-256 lenyomatait.
A megőrzött OSM adatok ODbL-1.0 forrásúak, © OpenStreetMap contributors.
A szentesi önkormányzati forrásból határleírási tényeket használtunk;
eredeti térképi képet vagy kontúrt ebben a csomagban nem másoltunk.

A `summary.json` szerint mind a 26 poligon szerkezetileg érvényes, a nevek
településenként egyediek, és az összes saját mentett névpont a megfelelő
felületre esik. Topológiai javításra nem volt szükség. A névpont befoglalása
elhelyezési ellenőrzés, nem a valós határ független pontossági mérése.
Az újraépítés mindhárom kimenetet bájtra azonosan állította elő.

A csomag önálló adatgyűjtési eredmény. A közös katalógusba és az alkalmazás
adatbázisába történő beemelést nem végzi el; GitHub-mentését a fő munkamenet
kezeli.
