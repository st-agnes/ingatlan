Sopron: négy eredeti, kék körvonallal jelölt tervezési egység

A csomag a 39/2021. (XII.28.) önkormányzati rendelet 1/B mellékletének négy tényleges földrajzi egységét tartalmazza. A forrás munkaszáma TT08518-M1/24, az áttekintő lap látható, arab számokkal nyomtatott dátuma „2024. 11.”, azaz 2024. november. A városrész-számozás: 1 Észak-nyugati városrész; 4 Bánfalva, Kutyahegy városrész; 5 Lővereki városrész; 13 Dél-keleti gazdasági terület városrész. A lefedettség erre a négy teljes forrásegységre terjed ki; Sopron összes városrészének jegyzéke külön kutatási feladat marad. Mind a négy rekord planning_unit, finom városrészként egyik sincs beszámítva.

Forrásdátum és dokumentumstátusz
A novemberi dátumot az 1. oldal látható rajzpecsétje igazolja; a 2. oldal külön hónapot nem nyomtat. A gépi szövegkinyerésben szereplő „.../2024” rendeletszám-placeholder helye az eredeti PDF renderelt képén fehér, felirata nem látható. Ebből a rejtett vagy eltakart CAD-szövegből nem következtetünk látható tervezetre vagy jóváhagyás hiányára. A dokumentum jelenlegi jogi érvényességét külön nem igazoltuk.

Eredeti geometria
A 2. oldal 38799, 38800, 38801 és 38802 rajzolási útjának 1238 eredeti kék szakasza adja a kontúrt. Az eredeti szakaszok csomópontozása és polygonize_full feldolgozása pontosan négy zárt, érvényes lapot eredményez: nincs maradék vágóél, lógó él vagy hibás gyűrű. A három külön-külön nyitott rajzolási út a már meglevő közös forrásvonalakkal záródik. Egyetlen hiányzó zárószakaszt sem adtunk hozzá. A 38815-ös kék vonal a jelmagyarázat része, ezért kimarad. A szövegként kinyert 1./4./5./13. kék számozás középpontjai egy-egy külön forráspoligonban helyezkednek el, ez igazolja a név-hozzárendelést. A native-source-polygons.json PDF-pontokat, a source-vector.geojson WGS84 koordinátákat tartalmaz.

Földrajzi regisztráció
Az 1. oldali valódi bordó településhatár két eredeti útjának (91995, 91996) változatlan forráscsúcsai az archivált OSM 1491393-as Sopron-határhoz kerültek hozzávetőleges affine illesztéssel EOV rendszerben. A natív CAD-szakaszvégpontok apró eltérései miatt a bordó szakaszgráf sok nyitott végpontot tartalmaz; ezekből nem készítettünk mesterségesen zárt településpoligont. A tényleges eredeti vonalszakaszok kontrollmintái maradtak meg.

A két forráslap összekötését a közös türkiz területi kitöltés eredeti csúcsai inicializálják. A végleges lapközi transzformáció 4888 tényleges, szürke/fekete CAD-szakasz mindkét eredeti végpontpárjára illeszkedik. A drawing/segment indexek és koordináták a cross-page-cad-controls.json.gz fájlban teljesen megmaradtak; a kis JSON 24, a térképen szétszórt példát is tartalmaz. Földrajzi névhelykoordináta nem szerepel kontrollként. A 2. oldali régiókat ezután a fagyasztott transzformáció EOV-ba viszi, majd a helyi PROJ adatbázis WGS84-re vetíti.

Pontosság és határérvényesség
A településhatár-illesztés medián eltérése körülbelül 11 m. A lapközi CAD-végpontok medián eltérése 0,115 PDF-pont, a 95. percentilis 0,183 PDF-pont. Ezek illesztési diagnosztikák; független földrajzi pontosságot nem igazolnak. Nincs felmért vagy függetlenül azonosított belső világkoordinátás kontroll, ezért az abszolút pontosság ismeretlen. A forrás hivatalos önkormányzati kiadvány, de a feldolgozott eredmény jelenlegi jogi/kataszteri hitelessége és a forrástérkép további felhasználási joga külön nincs igazolva.

A Lővereki egység 9515,52 m²-rel túllóg az archivált OSM-településhatáron: az átfedés 99,8479%. A másik három teljesen azon belül van. A túllógást változatlanul megőriztük, nem vágtuk le. Forrásidőbeli, határadatbeli vagy regisztrációs eltérés is okozhatja. Címhozzárendelésre mind a négy rekord le van tiltva.

Ellenőrzés és reprodukálás a repository gyökeréből
PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-sopron-next/extract.py --check
PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-sopron-next/derive.py --check

A kalibráció külön újrafuttatható a fit.py, match-cad.py, fit.py sorrenddel. A fit.py megőrzi a durva, közös forrásterületen alapuló kezdőmátrixot, a match-cad.py mindig ebből a függetlenül újraszámolt kezdőmátrixból indul. A derive.py csak a fagyasztott kontroll-/regisztrációs fájlokat használja. Az extract.py csak hiányzó helyi archívum esetén olvassa az eredeti, már helyben lévő PDF-et; hálózati letöltés egyik szkriptben sincs.

Szükséges Python-könyvtárak: PyMuPDF, numpy, scipy, shapely 2, pyproj, Pillow. A változatlan scripts/neighborhoods/build.mjs validateGeometry mind a négy földrajzi geometriát elfogadja; nincs páronkénti területi átfedés. A strict-validator-review.json a forrás pontos hash-ét rögzíti. A három PNG a natív kontúrokat, az OSM-településhatár illesztését és a lapközi valós CAD-kontrollokat szemlélteti.

Független numerikus audit: independent-review.json. Az independent_audit.py --check és
a review-native-check.py --check az eredeti natív szakaszokat, mindkét PDF-lapot,
a transzformációkat és a változatlan WGS84-csúcsokat külön ellenőrzi. Az audit
nem igazolja a mai jogi státuszt, nyílt újrafelhasználási jogot vagy abszolút
határpontosságot.
