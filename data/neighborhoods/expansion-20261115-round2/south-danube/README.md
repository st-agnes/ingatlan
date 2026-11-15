# Fonyód, Dunaföldvár és Kalocsa – forrástérképből becsült keresési területek

**21 poligon:** Fonyód6, Dunaföldvár7, Kalocsa8. Ez az itt rögzített21név hiányát pótolja; a három város összes lehetséges városrészének teljességét nem állítja. Nincs kör, pontból szerkesztett doboz vagy Voronoi-felosztás.

Mind a21eredmény **alacsony megbízhatóságú térképi becslés** (`rough_manual_map_partition`, `estimated:true`), nem gépi forrásból átvett hivatalos városrészhatár. A poligonok teljes helyi negyedek vagy külterületi lakott helyek közelítő keresési kiterjedését célozzák, nem egy épület, medence vagy vízfelület helyettesíti a negyedet. A forrásnevek helyzete és az úthálózat változatlan forrásadat; a választott területi lehatárolás saját becslés. Átfedések szándékosan megengedettek.

## Források és módszer

- A 2026-11-12-es országos OSM-pillanatképből5529teljes eredeti út/vízfolyás/vasút vonal és1332zárt területi objektum került mentésre. Ezek a `source-roads.geojson.gz` és `source-surfaces.geojson.gz` fájlok, változatlan WGS84-koordinátákkal és objektumazonosítókkal, címkékkel, verzióval és forráshivatkozással.
- `source-built-contexts.geojson`: három nagyobb, korábban begyűjtött eredeti beépítési terület. Fonyód becsléseit a parti beépítéshez vágjuk, hogy a nagy halastavak és a Balaton ne váljon automatikusan a negyed részévé. E beépítési határ önmagában nem negyedhatár.
- A `*-context.png` térképek a helyben mentett eredeti utakat/területeket és névpontokat mutatják, élő térképcsempe használata nélkül. A `*-context-registration.json` tartalmazza a képi koordináták és WGS84közti transzformációt.
- `pixel-traces.json`: a térképek látható utcái, partjai, vasútja, lejtőoldali/mezőgazdasági tömbjei alapján kézzel becsült zárt körvonalak. A nem látható belső kapcsolatok egyszerű interpolációk. `trace-specifications.json`: ezek WGS84alakja és a körvonal környezetében metszett eredeti útobjektumok listája. A felsorolt utak **nem mind hivatalos határvonalak**.
- `source-facts.json`: Fonyód nyugati negyedeinek önkormányzati utcás helymeghatározása, Kalocsa Csajdakert/Érsekkert/Zrínyi és Homokgyőr elsődleges helyi forrásai, valamint a dunaföldvári ITS forrásnyoma. Az idézett szöveges/térképi források támogatják a helyazonosságot, de nem igazolják az összes saját összekötő szakaszt.
- Fonyódnál a nyugati parti/hill-negyedek és a keleti üdülősáv, Dunaföldvárnál a kis vár-/templom-/kálváriahegyi és alji utcanevek, Kalocsán a parkok, lakótelepi tömbök és külterületi lakott helyek szerkezete vezette a becslést. A Homokgyőr, Vörösszállás, Urbántanya és Árendás-dűlő körüli mezőhatárok különösen hozzávetőlegesek.

## Offline újraépítés

A `build.py` nem használ hálózatot vagy PBF-et, és nem olvassa a később változó országos hiánylistát:

```bash
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round2/south-danube/build.py
```

A térképi nyomvonalak ismételt WGS84-előállítása `prepare-traces.py`, a mentett forrástérképek újrarajzolása `render-context.py`. Az `extract-context.py` opcionális forrásfrissítési eszköz a dokumentált PBF-hez; a már mentett `target-selection.json` névlistát megőrzi.

A `validation.json` csak technikai ellenőrzés: mind a21geometria érvényes, mind tartalmazza a saját ismert névpontját. Ez **nem földrajzi pontossági ellenőrzés**, és valós MySQL-importot sem végez. Az `unresolved.json` a rögzített kiinduló névlistához képest üres.

OSM-adatok: © OpenStreetMap contributors, ODbL1.0. A saját becslések OSM-alapú származtatott téradatok; a forrásattribúció megőrzendő. A gépi állományok tömöríthetők, a forrás- és becslésjelölések nem hagyhatók el.
