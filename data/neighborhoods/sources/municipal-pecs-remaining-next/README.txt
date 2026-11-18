PÉCS – TOVÁBBI 27 FORRÁSNEGYED, KÜLÖN BECSÜLT CSOMAG
2026-11-14

A source-inferred.geojson 27 új, tényleges forráskontúrt tartalmaz.
Mind a 27 önálló, önkormányzati forrásban meghatározott városrészjelölt;
primary jóváhagyás: 0. Földrajzi elhelyezésük továbbra is becsült,
claimedAbsoluteAccuracy=null, automatikus címhozzárendelésük kikapcsolt.
A regiszterek és az országos exportok nem változtak. A registry-entry.json
helyi, még be nem alkalmazott bejegyzésjavaslat.

Ez az első, fagyasztott 33-as pécsi csomagtól külön időállapot. Az annak
geometriáit tartalmazó referencia byte-azonos; SHA256:
3de4d89461e243563c5bd99d2bc33914f6ca059bdc97548e8f7ee0b41c968a95.
Az első csomag mind a 33 cellaazonosítója és forrásneve kizárt az új exportból.
Az aktuális forrás-exportok pécsi neveit is külön, olvasási snapshot alapján
kizártuk; a már publikált 33 néven túl más pécsi találat nem volt bennük.

A 67 forrásnév elszámolása: 33 korábbi + 27 új teljes forráskontúr + 7 nyitott.
A source-table-name-inventory.json minden nevet pontosan egyszer számol el.
A 27 új név:
Hird; Újmecsekalja; Kovácstelep; Piricsizma; Szentkút; Szentmiklós;
Zsebedomb; Gyükés; Pécsbánya; Rigóder; Szabolcs; Szabolcsi zártkert;
Meszes; Diós; Budai külváros; Budaiváros; Észak-Megyer; Szigeti tanya;
Fogadó; Bolgárkert; Nyugati ipari út; Üszögi tározó-major; Péterpuszta;
Józsefháza; Rücker-akna; István-akna; Flóriántelep.

Budaiváros és Budai külváros két külön forrásnév, két külön cella (80,76).
Újmecsekalja94 és a korábban publikált Uránváros99 szintén külön egység.
A táblázat V–IX számozása több helyen eltér a térképtől; nem azonosítjuk a
finom körzeteket automatikusan a római számmal. A név–cella-azonosságot az
önálló képi olvasás, alak és szomszédság, majd a tényleges seedpixel ellenőrzi.

A Nyugati ipari út122 és az Üszögi tározó-major95 funkcionális nevéből nem
következik kizárás. A 8. táblázat „Pécs városrészei” cím alatt külön finom
alkotóként sorolja őket, utóbbinál a gazdasági csoport további tagolását
kifejezetten indokolja. A korábbi pusztán név/funkció szerinti planning/local
kategóriákat az új csomagban visszavontuk: semantic-source-review.json.
A fagyasztott első csomag Déli gazdasági terület rekordjára külön, még be
nem alkalmazott szemantikai javítási ajánlás készült, pontos feature-ID,
forrásfájl- és geometrialenyomattal. Ez nem írja át a régi snapshotot:
first-cohort-semantic-recommendation.json.

A 7 továbbra is nyitott név:
Murom; Köztemető; Kisbalokány; Siklósi külváros; Árpádtető; Petőfi-akna; M utca.
Az unresolved-name-review.json mindegyikhez eredeti natív képkivágásokat ad.
Murom, Köztemető, Árpádtető és Petőfi-akna külső alakja a képen belül van,
de a no-data sraffozás több eredeti maszkfragmentre osztja. Egy-egy részlet
nem helyettesíti a teljes megnevezett területet. Kisbalokány és Siklósi
külváros a 12. ábrán ugyanabba a 92 cellába folyik; a 9. ábra finom elválasztója
felirat alatt takart, így nem klónozzuk a közös cellát két névre. M utca
apró, teljes képi alakja az alkalmazott eredeti maszkban teljesen vonalnak
minősül, külön szabad seedcella nincs. Ezekhez nem készült kitalált záróél
vagy sraffozáson átívelő pótlás. A nyitottság oka nem általános képszéli vágás.

A geometria eredete és ellenőrzése

A 48. PDF-oldal 9. ábrájának eredeti JPEG-je a finom neveket, a 63. oldal 12.
ábrája a kontúrokat adja. Mindkettő az archivált PDF-kivonat képobjektumával
byte-azonos. A nyers alakok az eredeti négy oldalszomszédos szabad pixelcellák
sorfutás-uniói, nem utca- vagy névpontpufferek. A raw-pixel-cells.json őrzi
az eredeti 27 pixelgeometriát. Minden külső él mellett tényleges eredeti
maszkpixel van; egyik cella sem érinti a raszter szélét.

37 konkrét belső maszklyuk 422 eredeti képpontja külön, tételes független
kartografikus döntést kapott: 30 egypixeles és 2 kétpixeles lokális/JPEG folt,
valamint 5 római feliratgrafika-rész. A cartographic-hole-decisions.json
pontosan ezek hash-azonosított pixelhalmazainak visszaállítását engedi.
Egyik sem tartalmaz vagy érint másik szabad cellát; általános lyukkitöltés
nincs. A szomszédos, külső maszkhoz kapcsolódó feliratstroke nem kapott
helyreállítási engedélyt. Külső élváltozás: 0.

A független névaudit 27 párosának pixelhalmaz-hashai és natív kivágásai
ellenőrizve. A független pixel-audit producerkód importálása nélkül 7738 nyers
és 7264 értelmezett egységélt ellenőriz; a sorfutás-unió és a külön kitettél-
számlálás egyezik. Mind a 27 geometria a változatlan szigorú JS-validátoron is
átmegy. Új–új és új–korábbi 33 pixel-/világgeometriai átfedés: 0. Az új 422 és a
korábbi 1076 visszaállított képpont halmaza is diszjunkt. A 221 eredeti szabad
forráscella egymásnak megfeleltetése a helyreállítás után is egy-egy értelmű.
Részletes QA: independent-name-review.json, independent-pixel-review.json;
a combined independent-review.json ezek különálló bizonyítékainak jegyzéke.

A földrajzi elhelyezés nem új kontrollazonosítás vagy új modell. Kizárólag az
első fagyasztott csomag változatlan Figure12→Figure9 és ÉNy-peremes EOV-keretét
alkalmazzuk, majd EPSG:4326-ba vetítünk. A külön georeferencia-audit nem
igazolta ezt országosan; a kis belső maradék és korrelált vonalellenőrzés nem
abszolút határpontosság. Nincs új georeferencia, névpontra igazítás, puffer,
snap, repair, képszéli lezárás vagy automatikus cím-hozzárendelési jóváhagyás.

Hálózatmentes reprodukció a repository gyökeréből:
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-remaining-next/derive-remaining.py --check
  PYTHONPATH=.local/geodata python3 data/neighborhoods/sources/municipal-pecs-remaining-next/independent-audit.py --check
  python3 data/neighborhoods/sources/municipal-pecs-remaining-next/review-first-cohort-semantics.py --check
  python3 data/neighborhoods/sources/municipal-pecs-remaining-next/summarize-review.py --check
  python3 data/neighborhoods/sources/municipal-pecs-remaining-next/freeze-package.py --check
A reprodukció és a végső auditor érdemi inputjai mind e csomag helyi snapshotjai.
A recovered/preflight/név-review fájlok korábbi munkamappa-útvonalakat is
megőriznek forrástörténeti hivatkozásként; a konverter nem olvassa e változó
mappákat. A prepare-inputs.py a kezdeti snapshot-átvétel történeti segédkódja.

Forrás: https://logoweb.pecs.hu/download/koncepcio/ITS.pdf
Eredeti teljes PDF SHA256:
995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1.
Forrásállapot: 2021-es ITS-közzététel, 2011-es népszámlálási témájú térkép,
2014-es készítői jelölés; a kontúrok tényleges felmérési ideje ismeretlen.
Mai névhasználat és jogi/kataszteri kiterjedés nincs igazolva. A nyilvános
önkormányzati PDF nem bizonyít szabad újrafelhasználási engedélyt. ODbL csak
a megőrzött OSM-kalibrációs bizonyítékra vonatkozik; nem automatikusan a térképre.
