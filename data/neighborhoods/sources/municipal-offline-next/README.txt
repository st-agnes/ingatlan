Kecskemét – további három, forrásalapú városrészjelölt

Importálandó egységes fájl: kecskemet-next.geojson
Központi regiszterhez előkészített rekord: registry-entry.json

Bethlenváros: 107 eredeti OSM-csúcs, kb. 509 589 m².
Homoki-domb: 136 eredeti OSM-csúcs, kb. 440 868 m².
Rákócziváros: 138 eredeti OSM-csúcs, kb. 358 087 m².

A 2021-es önkormányzati forrás rövid utcanévlistái több jelenlegi tér-/utcanév-
váltást és úttorkolati szakaszt elhagynak. A teljes forrástérkép alapján ezeket
azonosítottuk, majd kizárólag a helyben meglevő 2026-11-12-i OSM-forrás eredeti
útvonalainak egymást követő csomópont-éleiből állítottuk össze a körvonalat.
Nincs következtetett összekötő szakasz, puffer, levágás vagy geometriajavítás.
A nyers útgyűjtés befoglaló téglalapja nem válik városrészhatárrá.

A north-review.json és a három north-visual-*.png a független vizuális
forrásellenőrzést őrzi meg. A hat kézi illesztési pont csak az összehasonlító
képekhez kell: egyik kimeneti földrajzi koordináta sem ebből származik.
A pixelben mért illesztési hiba nem a határ méterben megadott pontossága.

Minden kimeneti él tényleges, egymást követő OSM-csomópontokat köt össze.
Mindhárom alakzat érvényes és lyukmentes, Kecskeméten belül marad, belső
területük nem fedi át egymást vagy a korábban exportált Erzsébetvárost.
Bethlenváros és Rákócziváros saját, megfelelő jelenlegi OSM-névpontot tartalmaz.
Homoki-domb neve a 2021-es önkormányzati forrásban szerepel, de nincs hozzá
azonosított jelenlegi OSM-névpont; a mai név külön ellenőrzése hiányzik.
A pontos közterületi oldal és az úttestválasztás nincs hatóságilag felmérve.
Egyik alakzat sem jelenlegi jogi/kataszteri vagy címhozzárendelési igazolás.

Forrás: Kecskemét MJV, Megalapozó Vizsgálat II. kötet,2021. május;
73. ábra, nyomtatott141. oldal; határleírások146–148. oldal.
A teljes eredeti PDF hash-e és a megőrzött oldalkivonat hivatkozása a bizonyítékban.
A tényleges nyers útadat ODbL-1.0, © OpenStreetMap contributors.
Az önkormányzati dokumentum/térkép újraközlésének jogállása nincs külön igazolva.

Reprodukció, a tároló gyökerében:
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-offline-next.py --check
A --check mód csak összehasonlít, nem ír fájlokat. Előállítás ugyanígy --check nélkül.
A --extract kapcsoló kizárólag a helyi teljes PBF-ből nyeri ki újra az eredeti utak
geometriáját; hálózatot nem használ, és nem része a szokásos katalógusépítésnek.

Az *-candidate.geojson fájlok a független ellenőrzés nyers bemeneti pillanatképei.
Az exploratory-connections.json legrövidebb útvonalai diagnosztikai jelöltek:
a Rákóczivároson belül átvágó Búzaszentelő utcai változatot kifejezetten elvetettük.
Ezek a diagnosztikák nem importálandó határadatok.

Ez nem Kecskemét teljes városrészlefedettsége. A korábbi Erzsébetváros mellett
csak három új alakzat készült; a többi terület külön forrásfeldolgozást igényel.
