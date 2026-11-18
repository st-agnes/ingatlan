# A fennmaradó körös becslések teljes munkalistája – negyedik november 15-i kör

Kiinduló mentés: `19caaea641ae90080ab725fd03a68362530199a9`.
3924 kiválasztott terület, 567 település, 372 külön körös tartalék és 15 még
helyhez sem kötött név. Mind a 387 név feladatba került, összesen 199 településről.

A cél minden fennmaradó névhez forrásból indokolható poligon. A durva térképi,
szöveges, történeti, utca- vagy telekcsoportból levezetett becslést is jelöljük;
az átfedés megengedett. Nem cserélünk le pusztán névpont alapján köröket
más kitalált alakzatra, és nem törlünk hiányzó neveket a nulla eléréséért.
Ha a keresés után is hiányzik a támpont, a hiány oka és a keresett forrás
megmarad a munkacsomagban. Az országos névjegyzék teljessége továbbra sem ismert.

A `tasks/` könyvtár hat, egymást nem átfedő, fagyasztott munkalistát tartalmaz.
A közös `contexts/` réteg egyetlen archivált országos OSM-feldolgozás eredménye.
A `viewport.geojson` kizárólag adatkinyerési ablak, **nem városrészpoligon**.
Az eredeti utak és felszínek teljes alakja megmarad; a forrásnév, címkék,
OSM-azonosító, verzió, időpont és az országos bemenet hash-e visszakereshető.

A dolgozók saját `shard-N/` mappájukban 10–20 neves, lezárt csomagokban adnak
át eredményt. A közös jegyzékbe csak SHA-256-tal rögzített, WGS84-ben érvényes
főréteg kerül. A korábbi adatokat és stabil azonosítókat megtartjuk.
A fő munkamenet időszakosan újraépíti az exportot, csomagolja és GitHubra menti.
Az alkalmazást és az élő MySQL-adatbázist ez a gyűjtési kör nem módosítja.

Aktuális számlálók és folytatási információk: [WORK-STATE.json](WORK-STATE.json).

## Lezárt adatállapot

A gyűjtési kör minden kiosztott nevet megvizsgált. A végső kiválasztott főréteg
**4308 területet tartalmaz 617 településről**. Ebben a körben nettó **384 terület**
került hozzá, és **371 körös tartalékot** sikerült forrásból indokolható poligonnal
kiváltani. Az országos névjegyzék teljessége továbbra sem ismert; a sok durva,
történeti és részterületi becslés nem tekinthető pontos hivatalos határnak.

A nulla körös tartalékot célzó feladat **nem teljesült maradéktalanul**:

- **Babosdöbréte / Árkosháza-puszta:** egy külön tartalékkör megmarad. A korábbi
  település eltűnt; az egykori épületcsoport vagy birtok határát nem sikerült
  visszanyerni. A [külön archivált tájjelölt](shard-0/residual-followup/arkoshaza-reviewed-candidate.geojson)
  valós utakból, erdőszegélyből és településhatárból levezetett, nagyon bizonytalan
  történeti tájrészlet. Kifejezetten `usableForAddressAssignment:false` jelölésű,
  ezért **nem kerül a főrétegbe vagy a bemeneti jegyzékbe**. A jelölt és a
  [források, bizonyítékok, újraépítési leírás](shard-0/residual-followup/README.md)
  megmaradnak későbbi kutatáshoz. A körök számának lenullázása önmagában nem
  indokolná a címek besorolására alkalmatlan tájjelölt előléptetését.
- **Dombóvár / Külterületek:** továbbra sincs alátámasztott teljes területi
  lehatárolás, és névpont sem áll rendelkezésre. A puszták részleges felsorolása
  nem bizonyítja, hogy azok egyesítése a teljes statisztikai külterületi egység.
  [A megmaradt hiány indoklása](shard-1/identity-followup/review.json) külön
  rögzítve van; kitalált középpont és poligon nem készült hozzá.

A főrétegben nincs pontból rajzolt kör. A megmaradt egy tartalékkör külön fájlban
szerepel, és nem kap poligonos lefedettségi jóváírást. A két fenti hiány a
4310 ismert helyazonosságból álló munkalistára vonatkozik, nem az ország teljes
városrészállományának ismert nevezőjére.

A felülvizsgált névjavítások és a két érdemi térképi javítás bekerültek a
kiválasztásba; a régi forrásgeometriák alternatívaként megmaradtak.
A 14 kiadási regressziós teszt, az export újraépítési ellenőrzése és a csomag
ellenőrzése sikeres. A [végső integrációs ellenőrzés](global-integration-validation.json)
és a [folytatási állapot](WORK-STATE.json) tartalmazza a pontos adatokat.
Az alkalmazás és az élő MySQL-adatbázis integrációja továbbra is külön feladat.

## Kutatási források visszaállítása klónozás után

A nyers források és bizonyítékok változatlan bájtjai a
[tartalom szerint deduplikált forrásarchívumban](source-archive/README.md)
maradnak meg. A nagy számú kis fájl helyett 12, legfeljebb 8 MiB-os részt
tárolunk; a [manifest](source-archive/manifest.json) minden eredeti becsomagolt
útvonalhoz SHA-256-ot, méretet és fájlmódot rendel. A tároló alapverziójában már
szereplő azonos tartalmat onnan használjuk újra, az azonos új bájtokat egyszer
tároljuk. Egyetlen eredeti forrás sem veszett el.

A 14 regisztrált GeoJSON, minden Python-szkript és Markdown-leírás, a fő
folytatási metaadatok és a külön Árkosháza-jelölt közvetlenül böngészhetők.
A hivatkozott **nyers térképek, közös kontextusok és további bizonyítékfájlok
klónozás után először visszaállítandók**. A tároló gyökerében:

```sh
python3 data/neighborhoods/expansion-20261115-round4/source-archive/materialize.py
python3 data/neighborhoods/expansion-20261115-round4/source-archive/materialize.py --check
```

A visszaállító ellenőrzött bájtokat ír az eredeti útvonalakra, eltérő meglévő
fájlt nem ír felül. A kiadási tesztek és a főréteg exportellenőrzése kibontás
nélkül is működnek. A letölthető poligon-ZIP nem tartalmazza a nagy nyers
kutatási archívumot; az a GitHub-klónból érhető el. Ez a tárolási változás
semmilyen kiválasztott poligont, lefedettségi számlálót vagy helyazonosságot
nem módosít.
