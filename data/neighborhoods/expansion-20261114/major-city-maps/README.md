# Nagyvárosi bővítés – 2026. november 14.

Három külön, rögzített adatcsomag, összesen **79 bemeneti alakzat**. Ezek még a közös név szerinti deduplikálás előtti darabszámok.

- `features.geojson`: **Győr, 50 alakzat**. A 2006-os felosztás 46 városrendezési körzetének megőrzött PDF-vektorai közül 42 elnevezett terület, továbbá nyolc, több körzetből álló városrész. Az egyedi körzetek és a tágabb városrészek átfedése szándékos. A 2014-es ITS táblázata rendeli hozzá a körzetszámokhoz a neveket. Három önmetsző forráskontúr javítása `make_valid` művelettel történt; az eredeti PDF változatlanul megmarad.
- `additional-features.geojson`: **Nyíregyháza, 24 alakzat**. A 2008-as IVS-ben közölt régi KSH-térkép látható körvonalai alapján készült durva kézi becslések. A név hozzárendelése a dokumentum szövege, a névvel ellátott tágabb térkép és a városon belüli elhelyezkedés alapján becsült. Az eredeti pixelkoordináták külön JSON-fájlban megvannak. A korábbi önkormányzati körvonal-illesztés helyezi el őket WGS84-ben. A kísérő megjegyzésben szereplő „25 manual rings” elírás: az adatban 24 van.
- `budapest-features.geojson`: **Budapest, öt alakzat**. Hets-telep, Sólyom-telep, Történeti központ, Vargatelep és Wesselényi-telep. A fővárosi rendeletben szereplő határleírások és a megőrzött OSM-utca-, vasút- és folyóvonalak durva értelmezése. A nem ismert telek-, erdő- és rézsűhatár egyszerű becsült szakaszokkal van helyettesítve. Wesselényi-telepnél a korábban félretett, valódi vonalakból képzett lakóterületi közelítés szerepel.

Egyetlen alakzat sem pont köré rajzolt kör. A becslések keresési célú közelítések; nem kataszteri vagy hiteles jogi határok. A Pécsről már meglévő 67 alakzat változatlanul a korábbi adatállományban található.

Újraépítés: a csomagkönyvtárban `build.py`, `extend.py`, illetve `budapest.py`, Python és PyMuPDF, NumPy, Shapely, pyproj függőségekkel. A `extract-budapest-streets.py` kizárólag a már letöltött országos OSM-kivonatból emeli ki a megnevezett soroksári utcákat; a kivonat SHA256-azonosítója a kimenetben szerepel. A használatkor az OSM-források ODbL-jelölése és forráshivatkozásai megtartandók.
