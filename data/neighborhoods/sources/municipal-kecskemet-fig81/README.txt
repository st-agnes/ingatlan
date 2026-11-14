Kecskemét – a 81. ábra négy finom városrészjelöltje
=================================================

Forrás: Megalapozó Vizsgálat II., Egyeztetési változat, 2021. május;
175. PDF-oldal / 173. nyomtatott oldal, 81. ábra. Az eredeti beágyazott
1259×893-as JPEG változatlan bájtjai a page175-xref216.jpeg fájlban vannak.
A kiadói PDF 216-os képi objektumával való azonosság a source-extraction.json
és a független ellenőrzés alapján igazolt. Az eredeti légifotó dátuma ismeretlen.

Két külön réteg
---------------
1. szechenyi-source-raster.geojson: két forrásalapú történeti jelölt:
   Belső-Máriahegy – 450 exportált csúcs, kb. 1 157 444 m²;
   Széchenyiváros III. – 317 exportált csúcs, kb. 668 407 m².
   Mindkettő sűrű körvonala kizárólag tényleges fekete forráspixelekből áll
   (maxRGB ≤ 45), és szó szerint zárt. Regiszterjelölt: registry-entry.json.

2. szechenyi-label-inferred.geojson: két KÜLÖN BECSLÉS:
   Széchenyiváros II. – 199 csúcs, kb. 490 083 m²;
   Széchenyiváros I. – 163 csúcs, kb. 222 815 m².
   A kék forrásfeliratok egy rövid határszakaszt takarnak. A sűrű körvonal
   4, illetve 16 pontja tényleges sötétkék feliratpixel; nem állítjuk, hogy
   ott látható fekete határvonal lenne. A folytatás szűk, rögzített képi
   ablakokban, kézi térképolvasással értelmezett. A nem fekete pontokat
   érintő élek hossza kb. 8,07 és 21,07 forráspixel, a georeferálás szerint
   kb. 29,09 és 75,79 m. Ezek NEM pontossági hibahatárok. Az összes érintett
   forráspixel koordinátája és RGB-színe archiválva van.
   estimated:true, canonicalNameIsNeighborhood:false, címhozzárendelés:false.
   Regiszterjelölt: inferred-registry-entry.json, kizárólag a becslési réteghez.

A körvonalak az ábra külön feliratozott kisebb egységei. A teljes
Széchenyiváros–Máriahegy tervezési területet nem adjuk el városrészként.
Az ábrán összesen hat finom felirat szerepel; Külső-Máriahegy és Villanegyed
csúcsa a forráskép szélén le van vágva. A két nyitott forrásszakaszt nem
zártuk le képkerettel vagy kitalált egyenessel, egyik sincs exportálva.

Digitalizálás és georeferálás
----------------------------
A trace-figure81-pixels.py kézzel azonosított határvonali pontok között
tényleges forráspixelek folytonos, 8-szomszédos láncát keresi. A 14 pixeles
keresési folyosó csak a digitalizálást korlátozza; nem válik földrajzi
pufferré vagy területté. A két kék feliratos ablak kivételét külön kezeli.
Nincs automatikus körvonaljavítás, buffer, térképi vonalra igazítás, mai
útvonallal helyettesítés, keretszéli lezárás vagy nem dokumentált résáthidalás.

Csak pontosan kollineáris pontok maradnak ki a sűrű pixelútból, nulla
forráspixel-területkülönbséggel. A közös szakaszok és csomópontok azonosak
a szomszédos alakzatokban. A csomópontok a nemlineáris inverz vetítés után
is megmaradnak, így a szomszédok között nem keletkezik keskeny vetítési rés.

Öt tényleges jelenlegi OSM-útcsomópont szó szerinti földrajzi koordinátája és
a régi képen kézzel becsült csomóponthelye adja az EOV/EPSG:23700-beli affin
illesztést. A 19 teljes, változatlan OSM-forrásút és minden node-azonosító
a control-roads.geojson fájlban van. A forrásutakat a korábban archivált
teljes helyi útkészlettel is összehasonlítjuk. Egy hatodik, az illesztésből
kihagyott csomópont a függetlenül megvizsgált hozzávetőleges képi ablakába
esik. A kontrollpontok, mátrixok és vetítési pipeline a raster-georeference.json
fájlban vannak; a PROJ-hálózati adatletöltés az előállításban ki van kapcsolva.

A kontrollok illesztési maradéka kb. 3,9–11,2 méter. Ez a kézi kontrollhelyek
belső összhangját méri, NEM az abszolút városrészhatár-pontosságot. A kézi
képponthelyek több pixellel bizonytalanok; a légifotó és a mai utak eltérhetnek.
A földrajzi kimenet csúcsai georeferált képpontok, NEM eredeti OSM-csúcsok.

Bizonyítékok és korlátok
-----------------------
- raster-pixel-trace.json: kézi kezdőpontok, tényleges pontláncok, minden
  érintett kék pixel/RGB, értelmezési ablak, sűrű és kollineáris körvonal.
- conversion-proof.json: érvényesség, veszteségmentes kollineáris tömörítés,
  Kecskeméten belüli elhelyezkedés, nulla belső átfedés és kimeneti SHA256.
- raster-independent-review.json: külön ellenőrző által rekonstruált
  geometria, forrásazonosság, besorolás és georeferálás ellenőrzése.
- raster-trace-preview.png: piros a két fekete forráskörvonal, narancs a két
  feliratértelmezést tartalmazó becslés. Az eredeti JPEG külön megmarad.
- diagnostic-crops.json és a négy kis PNG: pontosan dokumentált képkivágások
  a levágott csúcsokról és a kék feliratokkal takart szakaszokról.

A finom nevek a 2021-es feliratokból származnak; mai pontos névhasználatuk
független igazolása hiányzik. Aktuális, hivatalos, jogi vagy kataszteri
határigazolás nincs. Az abszolút pontosság ismeretlen. MINDEN rekordban
usableForAddressAssignment:false; ez az anyag kutatási, ellenőrzendő jelölt.
Az önkormányzati térkép nyílt újrafelhasználási licence nincs külön igazolva.
Az ODbL az OSM-kontrolladatokra vonatkozik, nem automatikusan a teljes térképre.

Helyi reprodukció a tároló gyökeréből
-----------------------------------
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-kecskemet-fig81.py
  PYTHONPATH=.local/geodata python3 scripts/neighborhoods/derive-kecskemet-fig81.py --check

A --check összehasonlít és nem ír ki fájlokat. Függőségek: numpy, Pillow,
Shapely, pyproj; az archivált JPEG, kontrollutak és Kecskemét kanonikus
településhatára szükséges. Nincs hálózati letöltés vagy távoli írás.
Az előállító kód nem módosítja a közös regisztereket vagy országos exportokat.
