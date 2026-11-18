Tatabánya – további tényleges forráskörvonalak
============================================

Eredmény: 3 új önálló városrészjelölt és 4 elkülönített, összevont forrásterület.
A korábban exportált Kertváros, Alsógalla, Óváros és Síkvölgy NINCS újraexportálva.

Önálló forrásnegyedek – additional-quarter-vectors.geojson
--------------------------------------------------------
- Galla ipari övezet: 516 csúcs, kb. 4 558 187 m².
- Észak-Vértes: 746 külső és 471 belső csúcs, kb. 33 661 247 m².
- Nyugat-Gerecse: 1036 csúcs, kb. 26 103 954 m².
Importjelölt: registry-entry.json.

A forrás címe „Tatabánya városrészek településrendezési szempontú lehatárolása”,
a 8/2018. (IV.19.) önkormányzati rendelet 3. melléklete. Az erdős vagy ipari
funkció önmagában nem zár ki egy külön névvel és külön körvonallal szereplő
forrásnegyedet. A jelenlegi névhasználat és a rendelet mai hatálya külön nincs
igazolva. A kimenetek ellenőrzendő történeti forrásjelöltek, nem kataszteri határok.

Összevont forrásterületek – compound-source-groups.geojson
--------------------------------------------------------
- Bánhida – Dózsakert (egy közös forráskörvonal);
- Szőlőhegy – Újváros – Sárberek (zárt közös külső körvonal);
- VI-os telep – Felsőgalla (zárt közös külső körvonal);
- Nyugati ipari park – Erőmű ltp. (egy közös nagy forráskörvonal).
Importjelölt: planning-registry-entry.json, csak a külön csoport/planning réteghez.

A csoportok neve leíró összetétel, nem a forrásra utólag ráírt új városrésznév.
Nem másoljuk át a közös alakzatot több külön név alatt. A 16 forrásfeliratból
így a régi 4 mellett 3 további névhez van önálló körvonal; 9 finom név külön
határa továbbra sincs igazolva. Pontos akadálylista: unresolved-fine-areas.json.
Nincs új, csak címke köré becsült terület ebben a csomagban.

Pontos eredeti vektorok
----------------------
Az eredeti PDF a korábban archivált municipal-west/tatabanya-map.source.pdf.
SHA256: 7a7ca9a8f70f0dcaad90deb3ce27a459a8b70610914c72cc7d9ec98eb2fb76d7.
A dokumentum egy teljesen vektoros, 842×1191 PDF-pontos oldal, 12 864 rajzobjektummal.

A parse_exact_pdf.py az eredeti PDF decimális m/l operátorait és graphics-mátrixait
pontosan számolja. A CAD-koordinátákat a PDF többek között 0,12-es skálával viszi
a lapra. A MuPDF által kiadott float32 koordináták közös csomópontoknál kicsit
eltérhetnek. Nem illesztjük vagy kerekítjük ezeket össze: az eredeti számokból
számított pontazonosságot használjuk. A parser mind a 12 864 rajzobjektum sorrendjét,
színét és befoglalóját ellenőrzi MuPDF-fel; a legnagyobb float-eltérés 0,0001741 pt.

Minden exportált élhez megmarad az eredeti rajzobjektum és vonalelem indexe.
Az ívek itt tényleges, egyenes l operátorok; nincs görbesimítás vagy közelítő
raszterezés. A záró pont csak akkor fogadható el, ha szó szerint azonos a kezdővel.
Nincs automatikus záróél, buffer, make_valid, clipping vagy földrajzi snapping.

Három fontos önálló forrásértelmezés:
- Galla: az 1815-ös eredeti rajzban egy 0,12 pontos oda-vissza kitérő van.
  A két azonos végpont közötti visszajárt szakaszt külön dokumentáljuk; a megmaradó
  határ minden éle tényleges eredeti él. Nem automatikus poligonjavítás történt.
- Észak-Vértes: a zárt 1286-os külső körvonalhoz a szintén tényleges, azonos zöld
  színű és ellenkező körüljárású 6325-ös belső gyűrű tartozik. Ez pontosan a külön
  Síkvölgy 5531-es forráskontúrja. A forrásképen narancssárga sziget látszik a zöldben.
- Nyugat-Gerecse: a 4557+4558 forrásszakaszokat a Felsőgalla 4851-es rajzának
  tényleges 95-ös vonaleleme zárja, fordított irányban. Nincs kitalált összekötés.

Az összevont csoportoknál is tényleges zárt forrás-alárészletek maradnak meg.
A nyugati apró háromszög és a déli közös kezdőszár parányi hurka teljes egészében
a kiválasztott nagy körvonalon BELÜL található. Kihagyásukkal nem veszünk el külső
területet. A szakaszok és az ellenőrzésük a source-vector-trace.json fájlban vannak.

Mi maradt hiányos?
-----------------
A Szőlőhegy és Újváros/Sárberek közötti M1-es szakasz és a VI-os telep/Felsőgalla
közötti 1-es úti szakasz nem ad teljes, szó szerinti finom forráskörvonalat.
A közeli útrajzi szürke/fekete foltok nem jogosítanak fel önkényes középvonalra
vagy egyenes lezárásra. Bánhida és Dózsakert, illetve a nyugati ipari park és az
Erőmű lakótelep között nincs egyértelmű külön forráskontúr. A közeli türkiz 6326-os
zárt alakzat az Erőmű-tó vize, nem lakótelepi körvonal; azt nem exportáljuk.

Georeferálás és megőrzött forráshibák
-----------------------------------
A korábban fagyasztott tatabanya-georeference-proof.json affin PDF→EOV mátrixát
változatlanul használjuk, majd WGS84-be vetítünk. A forrásalakzatokat nem mozgattuk
újra, hogy jobban illeszkedjenek. A korábbi 779 kalibrációs pontból rögzített
17 mintapontot és legközelebbi jelenlegi OSM-határpontját újraellenőrizzük.
A régi illesztési RMS kb. 11,21 m; ez NEM abszolút városrészhatár-pontosság.

FONTOS: a forrás eleve tartalmaz kicsi határátfedéseket. Például az Észak-Vértes
és Galla ipari övezet körvonala között kb. 326 m² átfedés van. Ezeket teljesen
megőriztük és kimértük, nem vágjuk le egyik oldalról sem. Az összes érintett
pár a conversion-proof.json és source-vector-trace.json fájlban szerepel.

A történeti térkép és a közelítő illesztés miatt a jelenlegi kanonikus OSM-
településhatáron kissé túlnyúlik az Észak-Vértes (0,3067%) és Nyugat-Gerecse
(0,1458%), valamint két csoport (kb. 0,12%). Az exportált külső csúcsok legnagyobb
túlnyúlása kb. 30,1 m. A forrást nem csonkítottuk a mai referenciához.
Ezek a pontosan rögzített eltérések kizárják az automatikus címhozzárendelést.
Minden rekordnál usableForAddressAssignment:false és ismeretlen abszolút pontosság.

A földrajzi csúcsok georeferált eredeti PDF-pontok, nem eredeti OSM-csomópontok.
Az önkormányzati térkép nyílt újrafelhasználási licence nincs külön igazolva;
az ODbL az OSM-georeferálási referenciára vonatkozik, nem automatikusan a térképre.

Ellenőrzés és reprodukció
------------------------
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-tatabanya-more.py
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-tatabanya-more.py --check

A --check csak összehasonlít, nem ír fájlokat. Függőségek: PyMuPDF, numpy,
Shapely, pyproj, Pillow; a fagyasztott eredeti PDF, korábbi georeferálási bizonyíték
és kanonikus településhatár-archívum kell. Nincs hálózati művelet.

Bizonyítékok: source-vector-trace.json, georeference-proof.json, conversion-proof.json;
független eredeti forrás- és geometriai ellenőrzés: independent-review.json.
Az independent_audit.py külön pypdf-feldolgozóval és Fraction-mátrixszámítással
4469 eredeti forrásélt, az összes koordinátát, kontrollt és dokumentált eltérést
ellenőriz; alapértelmezetten és --check mellett csak olvas. Futtatása:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-tatabanya-more/independent_audit.py --check
Ehhez a pypdf csomag is szükséges. A --write-review külön, kifejezett generálási opció.
Az eredeti képből készült diagnosztikai kivágásokat a diagnostic-crops.json írja le.
A source-cycle-preview.png fájlban piros a három önálló körvonal, kék a négy csoport.
A forrás-előállító nem módosít közös regisztert vagy országos kimenetet.
