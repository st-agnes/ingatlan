Dunaújváros – Dózsa városrész: követhető kézi becslés
===================================================

Ez a csomag EGY KÜLÖN BECSÜLT TERÜLETET tartalmaz. Nem igazolt vagy teljes
forráskörvonalként exportált városrészhatár; nem kerülhet az elsődleges,
forrásalapú városrészrétegbe, és nem zárja le Dunaújváros hiánylistáját.

Mi a forrás, és mi a becslés?
----------------------------
A 2020-as önkormányzati Településfejlesztési Koncepció 12. nyomtatott/PDF-
oldalának 11. pontja külön Dózsa városrészt határoz meg az Aranyvölgyi út,
Dózsa György út és Szórád Márton út között. A 69. oldalon háromszögként
írja le. A régi DÉSZ 19/2003.(V.16.) rendeletének 37.§(1) bekezdése ugyan-
ezeket az utakat adja meg; a megnyitott jogszabályváltozat 2015.09.19-i.
Ez városrészleírás, nem választókerületi vagy szolgáltatási körzethatár.

Az eredeti 2026-os OSM/PBF-ben a három mai nevű út nem alkot zárt kört.
Az Aranyvölgyi és Dózsa György út közötti legkisebb vetületi távolság
178,01 méter. Ezt a rést nem zárjuk le egy kitalált egyenessel. Ehelyett
egy külön becslés a tényleges Vasmű úton és a tényleges körforgalom egy
ívén halad: 165,16 m Vasmű úti és 29,87 m körforgalmi szakasz határszerepe
NINCS igazolva a városrész szöveges leírásában. A Vasmű utat nem nevezzük
át hallgatólagosan Aranyvölgyi útnak. Egy 2014-es helyi közlekedési cikk
a kapcsolat tényleges létezését megerősíti, de nem városrészhatár-forrás.

A körvonal a megnevezett utak és az értelmezett kiegészítés egyetlen
belső lapja, amely tartalmazza a tényleges Dózsa névpontot. Minden éle
egymást követő eredeti PBF-csomópontokat követ. Nincs forrás nélküli
összekötő szakasz, interpolált metszéspont, puffer, hull, geometriajavítás,
vágás vagy térképi vonalra igazítás. A névpont a név jelenlétét és a lap
kiválasztását támasztja alá, a teljes körvonal helyességét nem igazolja.

Lehetséges eltérések: a körforgalom másik íve, a csomópont másik sávja,
az utak telekhatár szerinti oldala vagy a még nem ellenőrzött R3 melléklet
városrészvonala. Az eredeti körforgalmi teljes út megmarad a bemeneti
állományban; a kiválasztott és alternatív ív hosszát a conversion-proof.json
külön rögzíti. A távolságok az értelmezett szakaszokat jellemzik, nem a
határ pontosságára vonatkozó hibahatárok.

Állományok
----------
- source-facts.json: pontos önkormányzati/jogszabályi URL-ek, oldalak,
  szöveges határtényezők, a kézi becslés oka, a többi keresett városrész
  konkrét akadályai. A PDF webes olvasóban megnyílt, helyi eredeti bájt-
  archívum nem készült, ezért eredeti PDF-SHA256 nincs állítva.
- dozsa-input-ways.geojson: változatlan teljes eredeti OSM-utak, node-
  azonosítókkal, verzióval, időbélyeggel és minden címkével.
- municipality.geojson és name-control-point.geojson: az országos
  kivágás tényleges településkontúrja és külön névpontja.
- dozsa-inferred.geojson: inferred_area, estimated:true; a becslési
  rétegbe szánt jelölt. canonicalNameIsNeighborhood:false a nem igazolt
  teljes terület miatt; a név forrásbeli létezése ettől külön igazolt.
- unproven-boundary-segments.geojson: az összes nem igazolt szerepű
  eredeti útszakasz, végponti node-azonosítóval és egyedi hosszal.
- conversion-proof.json: élről élre eredet, záródás, névpont, települési
  tartalmazás, szakaszhosszak és a feloldatlan körforgalmi alternatíva.
- pbf-way-verification.json: a bemeneti utak ismételt közvetlen össze-
  hasonlítása az eredeti ország-PBF teljes koordináta- és címkesorával.
- application-validation.json: a meglévő, változatlan JS-geometria-
  ellenőrző eredménye. A geometriai érvényesség nem határhitelesítés.
- dozsa-inference-preview.svg: helyben megnyitható vektoros ellenőrző
  ábra; pirosak a nem igazolt határszerepű Vasmű/körforgalmi szakaszok.
- inferred-registry-entry.json: csak a külön becslési regiszterhez
  készített bejegyzésjelölt; közös regisztert ez a csomag nem módosít.

Mi hiányzik máshol?
------------------
A Római városrészhez helyrajzi szám szerinti telekhatárok és a felső
partél kellenek. A Béke városrészhez az állomás területének keleti határa
és földrészlet-határok hiányoznak; ez nem helyettesíthető egy véletlenül
kiválasztott sínpárral. Kertvárosnál és Technikumnál a leírás telkek hátsó
határát és külön kivett iskolaingatlant is említ. A Ságvárihoz előkerült
történeti udvar- és építkezési leírásokból nem lesz teljes városrész.
Az északi út–vasút körzeteknél az eredeti közös csomópontos kör nem
zárult: a vasúti ág és a külön szintű keresztezések pontosítása hiányzik.
A forrástények felsorolása nem országos vagy teljes helyi hiányjegyzék.

Reprodukció a tároló gyökeréből, hálózat nélkül
--------------------------------------------
PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-dunaujvaros-next.py
PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-dunaujvaros-next.py --check
PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-dunaujvaros-next.py --verify-pbf

Az első két parancshoz shapely/pyproj és az archivált saját bemenetek
kellenek. A --check csak ellenőriz. A --verify-pbf parancshoz osmium és a
.local/neighborhoods/hungary-latest.osm.pbf szükséges; az eredményt a
pbf-way-verification.json fájlba írja. Közös exportot vagy regisztert
egyik parancs sem módosít.

Minden rekord usableForAddressAssignment:false. A tényleges koordináták
ODbL-1.0 szerinti OSM-adatok, az önkormányzati forrásból kézzel átírt
tényszerű utcanevekkel és parafrázisokkal. A teljes kiadói PDF vagy a
helyi újságcikk nincs újraközölve. Aktuális, jogi, kataszteri vagy méter-
pontos határigazolás nem történt.
