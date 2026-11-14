# Magyar városrészhatárok – kutatási adatállomány

**Az új gyűjtési stratégia aktuális, összevont állománya:** [kereshető területek és poligonok](search-areas.geojson), [településenkénti darabszámok](search-areas-report.csv), [MySQL-import](search-areas.mysql.sql.gz). A név szerint egyesített állomány gépi határokat, térképi becsléseket és átfedő felosztásokat is tartalmaz. A mindenkori pontos darabszám a [gépi jelentésben](search-areas-report.json) található.

**Legutóbbi mentés: 3404 kereshető terület 564 településről**, kör alapú pótlás nélkül. Külön tartalékrétegben 861 pontból becsült kör marad. [Letölthető teljes adatcsomag](../../downloads/neighborhoods/otthonra-keresheto-varosreszek.zip).

- [Új adatmodell, névazonosság, forrásválasztás és importálás](../../docs/NEIGHBORHOOD-SEARCH-DATA.md)
- [Gyűjtési stratégia és folytatható munkafolyamat](expansion-20261114/STRATEGY.md)
- [A legutóbbi mentés és a következő munkák állapota](expansion-20261114/WORK-STATE.json)

## Korábbi, szigorúbb kutatási rétegek

A 2026. november 14-i állapot 506 forrásalapú városrészjelöltet tartalmaz 48 településről. Külön rétegben 191 becsült alakzat szerepel 17 településről: 165 negyedjelölt, 16 tágabb tervezési csoport és 10 helyi terület. A 31 forrásalapú tervezési egység szintén külön állományban marad.

Az országos gyűjtés még nem teljes. Egyetlen alakzat sincs automatikus címbesorolásra jóváhagyva. A történeti forrás, a mai névazonosítás és a földrajzi illesztés bizonyossága külön adat.

- [Kész adatcsomag és térképes nézegető, körülbelül 5 MB](../../downloads/neighborhoods/otthonra-varosreszhatarok-adatok-506-191.zip)
- [Településenkénti statisztika és ismert hiányok, 3155 sor](combined-report.csv)
- [A statisztika értelmezése](combined-report.json)
- [Forrásalapú jelöltek, GeoJSON](neighborhoods.geojson)
- [Becsült alakzatok, GeoJSON](estimated-candidates.geojson)
- [Tervezési egységek, GeoJSON](planning-units.geojson)
- [Részletes forrás- és módszertani dokumentáció](../../docs/NEIGHBORHOOD-DATA.md)
- [Forráskivonatok, ellenőrzések és reprodukciós programok](sources/)
- [A 191 alakzatos állapot ellenőrzése](research/checkpoint-validation-506-191.json)

A kész ZIP kibontása után a `data/neighborhoods/review.html` fájl böngészőben megnyitható. A GeoJSON WGS84 koordinátákat használ. Az üres teljesvárosrész-szám ismeretlent jelent; a becslések nem zárják le az ismert hiánylistát.

Az újraépítés parancsai a részletes dokumentációban szerepelnek. Az adatfeldolgozás nem módosítja az alkalmazás hirdetéseit, párosítását vagy Google Cloud-környezetét.
