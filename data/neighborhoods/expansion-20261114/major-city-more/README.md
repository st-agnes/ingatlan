# További nagyvárosi területek – 2026. november 14.

A csomag **26 bemeneti alakzatot** tartalmaz, kör alapú becslés nélkül. Ez a közös deduplikálás előtti darabszám.

- `features.geojson`: **Tatabánya, 9**. A 2018-as önkormányzati térképről megőrzött három nyitott vektoros körvonal egyszerű lezárása, valamint hat névhez becsült belső elválasztó a tényleges közös külső körvonalon belül. Az eredeti rajzokon felirat vagy út takarta részek egyszerű becslése megengedett; a program nem állítja, hogy a becsült elválasztó mért vagy jogi határ.
- `kaposvar-features.geojson`: **Kaposvár, 9**. A meglévő tízrészes térkép hat különálló kontúrjából Toponár, Deseda, Répáspuszta, Fészerlakpuszta, Zselic-kertváros és Töröcske. Kecelhegy és Cser közös körvonalának hozzávetőleges kettéosztása. Rómahegy a közös Donner–Rómahegy alakzatnak a korábban megőrzött Donner-terület levonása után maradó nagyobb része.
- `dunaujvaros-features.geojson`: **Dunaújváros, 8**. Alacsony bizonyosságú, tág keresési területek a tényleges főbb útvonalak és településhatár által képzett körvonalakból. A településfejlesztési koncepció és a korábbi rendelet igazolja a neveket és a közlekedési folyosók szerinti felosztás elvét, de az említett telek-, állomási és partélhatárok nincsenek pontosan meg. Hat belső elválasztó egyszerű, külön rögzített kézi becslés. A névpont az adott oldalt választja ki, nem sugarat vagy kört határoz meg. Ha rendelkezésre áll a városrésztérkép, ezek a tág becslések azzal javítandók.

A programok: `build.py`, `kaposvar.py`, `dunaujvaros.py`. Python, Shapely és pyproj szükséges. A kimenetek és a források SHA256-azonosítói a `summary.json`, valamint az egyes rekordok részei. Az `evidence/` könyvtár megőrzi a becsült elválasztókat és a tényleges dunai útvonalakat.

A csomag nem módosítja az előző, 79 alakzatos nagyvárosi bővítést vagy az alkalmazás működését. A kontúrok földrajzi érvényessége ellenőrizve, hajszálpontos mai/jogi hitelesítés nem történt. Az átfedések és a többféle felosztás szándékosan megmaradnak.
