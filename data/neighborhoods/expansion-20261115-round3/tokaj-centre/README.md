# Tokaj – Óváros, külön központi becslés

Egyetlen, 0,469 km²-es WGS84 Polygon: a teljes régi központ lakott településfoltjának alacsony biztonságú becslése. Importálandó fájl: `features.geojson`.

A 2022-es önkormányzati ITS olvasható szövege szerint a Tokaji Óváros a középkori magot, az egykori bányászfalut, halászfalut és az újkori városközponti részt foglalja magában. A központi magterület határaként a 38-as főút szerepel. A szöveg emellett a Rákóczi, Kis Albert tér, Serház, Vasvári Pál, Görög, Bethlen Gábor, Táncsics és Váradi utcákat kapcsolja a történeti részekhez. A bányász-/halászfalusi pontok befoglalása ezért szándékos szülő–gyermek átfedés, nem azonos névként való összevonás.

A külső körvonal döntő része a már megőrzött, tényleges OSM-lakóterület alakját követi a hegy és a folyópart közötti lakott sávban. Délen az Erzsébet királyné híd tényleges vonalának rövid, hegy felőli becsült meghosszabbítása, északon a Váradi/Bethlen történeti bejárat környéki becsült keresztmetszet választja le a központot a továbbnyúló lakott sávról. Mindkét becsült vágás külön forrásfájlban megmarad. Nem készült pont köré generált kör, sugár vagy téglalap. A natív lakóterület nem lett egész Tokajként vagy kis épületként újracímkézve; a központi részét különítettük el.

A szöveget webes kereső-konnektorral olvastuk. Teljes helyi PDF-et vagy abból kiemelt natív önkormányzati határt nem állítunk. A két bejárati elválasztó és a telekfrontok kezelése bizonytalan, a polygon keresési becslés, nem hivatalos/kataszteri lehatárolás. A források és az értelmezés a `source-evidence.json` fájlban szerepelnek.

Újraépítés helyi forrásokból `shapely` és `pyproj` csomagokkal:

```sh
PYTHONPATH=/workspace/ingatlan/.local/geodata python3 data/neighborhoods/expansion-20261115-round3/tokaj-centre/build.py
```

A `summary.json`/`validation.json` a geometria és a települési befoglalás mellett ellenőrzi az Óváros, Bányászfalu, Halászfalu ismert pontjának befoglalását és a déli Kistokaj-pont külön maradását. © OpenStreetMap contributors, ODbL-1.0.
