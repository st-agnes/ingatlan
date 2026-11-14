PÉCS – ÖT PONTPÁROS GEOREFERÁLÁSI KÍSÉRLET, NEM JÓVÁHAGYOTT MODELL
2026-11-14

Ez külön kutatási bizonyítékcsomag. Nem készít vagy cserél városrész-poligont,
nem ad primary minősítést, nem használható címek városrészhez rendelésére.
A municipal-pecs-next korábbi forráscsomagja és az első inferred snapshot
változatlan maradt. Az alacsony illesztési maradék NEM igazolt földrajzi pontosság.

Öt megadott pontpár standard, súlyozatlan affine legkisebb négyzetes illesztése
készült. Három örökölt szürke településhatár-pontjelöltet két, külön leolvasott
valódi útkereszteződés egészít ki. Az illesztésbe sem a többi szürke vonalpont,
sem a két útvonal menti megfigyelések nem kerültek be. A korábban eltorzult,
54 perempontos modell csak byte-azonos összehasonlító forrásként van jelen.

Az önálló audit a szürke pontok megfeleltetését vizsgálja. A gray-corner-1 név
félrevezető: a [160,162] képpont egy szürke függőleges szakaszon van, és a célul
adott 684770958 OSM-node is egy vonalszakasz köztes pontja. A látható L-könyök
pár pixellel délebbre van. Ez nem bizonyítja, hogy a két köztes pont földrajzilag
eltér, de a körvonal mentén nem azonosítható egyértelműen a pontpár. A megadott
±2 pixeles olvasási doboz ezt a megfeleltetési bizonytalanságot nem írja le.
A teljes audit döntését az independent-review.json, a csomag döntését a
decision.json tartalmazza. A jó számtani eredmény nem írhatja felül ezt a gondot.

Nyers forrásazonosság:
  Önkormányzati ITS PDF: https://logoweb.pecs.hu/download/koncepcio/ITS.pdf
  SHA256: 995d0db03e454a34046b248526e0882aee26ffbf40ba916e996afa4c8b49f6b1
  48. PDF-oldal, beágyazott kép xref 616, 585×514 pixel.
  Eredeti JPEG SHA256:
  75758682472a880dee3488068f324d3feb4ba916237de33d36734696ed1d78f8
  Helyi OSM PBF SHA256:
  224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a
  A másolatok byte-azonosságát az input-copy-proof.json rögzíti.

A boundary-source-proof.json a helyi PBF-ből ellenőrzött Pécs relation 575380
32 eredeti határwayét, 535 valódi node-ját, valamint a három jelölt tényleges
node-azonosítóit tartalmazza. Nem névpontból előállított világkoordináták.
A source-road-proof.json és source-road-ways.geojson 121 eredeti teljes útway
882 valódi node-ját őrzi; az eredeti way/node-adatokat külön PBF-olvasás ellenőrizte.

A két déli útkereszteződés: M60/58 [275,505] és M60/578 [400,483], mindkettő
±3 pixeles képi leolvasási tartománnyal. Világpontjuk a tényleges, eredeti két
M60-főpálya és a keresztező közút vonalszakaszainak síkbeli metszéspontjai közötti
átlag. Ezek nem szó szerinti OSM-keresztezőnode-ok és nem bemért alappontok.
A csomag megőrzi az összes szakasz nodeRefs és koordináta bizonyítékát.
A második út a mai 578, nem 5711. A forráson nincs olvasható útszám; az azonosság
az úthálózati topológián és a forrásjel alakján alapul. Ez történeti/kartográfiai
bizonytalanságot is jelent, amit nem old fel a jelenlegi OSM-adat.

Számítás és a jelölt számtani eredménye:
  [forrás_x,forrás_y,1] @ M = [EOV_kelet,EOV_észak], EPSG:23700.
  Az M és minden pontpár maradéka a model.json/calculation-proof.json része.
  Külön középre igazított 2×2 normálegyenletes számítás is egyezik az affine LS-sel.
  Öt illesztési maradék: 42,2 / 17,4 / 37,9 / 33,1 / 33,1 méter.
  RMS: 33,8 méter; a képtéri maradékok normája 0,53–1,30 pixel.
  Ezek belső illesztési diagnosztikák, nem a térkép pontosságának becslései.

Nem illesztett diagnosztikák:
  M60, 16 tényleges forrásvonali pixel: medián kereszteltérés 26,9 m,
  p95 94,5 m, maximum 101,8 m. Ugyanaz az út szerepel a két illesztett
  csomópontban is, ezért ez nem teljesen független pontosságellenőrzés.
  66-os út, 8 tényleges forrásvonali pixel: medián 4,8 m, maximum 19,8 m.
  Ezek vonalhoz vett távolságok, nem egy-egy világpontnak megfeleltetett GCP-k;
  az út menti hosszanti bizonytalanságot nem mérik.
  51 további szürke perempont: medián 21,1 m, RMS 101,2 m, p95 180,2 m,
  maximum 474,7 m. A történeti és mai határ egyezése nem igazolt; az eltéréseket
  nem javítottuk ráillesztéssel, és az okukat sem állapítjuk meg bizonyíték nélkül.

Érzékenység:
  Öt leave-one-out változat és 2000 determinisztikus képi perturbáció készült
  (seed 20261114). Utóbbiban a sarokjelöltek x/y értékét ±2 pixelen, az
  útkereszteződésekét ±3 pixelen belül egymástól független egyenletes mintával
  változtatjuk, miközben a világcélpontokat rögzítjük. Ez feltételezett forgatókönyv,
  nem kalibrált valószínűségi modell, nem konfidenciaintervallum. Nem tartalmazza a
  rossz pontmegfeleltetést, kartográfiai általánosítást, forráskort, OSM- vagy
  geodéziai hibát. Északkeleten/keleten a pontok a kontrollok konvex burkán kívül
  vannak: a forgatókönyv 95. percentilis elmozdulása ~182 m, maximuma ~292 m.
  A kontrollok jó belső illesztése ezért sem terjeszthető automatikusan egész Pécsre.

Megjelenítési bizonyítékok:
  source-control-crops.png: csak eredeti képkivágás és leolvasási doboz;
  candidate-model-overlay.png: ettől elkülönített mai OSM-vonal rávetítése.
  Az overlay nem szolgált a két útkereszteződés kezdeti képpontjának kiválasztására.
  A nagyítás vizsgálati célú, nem javítja az eredeti ~32 m/pixeles forrásfelbontást.

Jogi/korabeliségi korlátok:
  A térkép 2011-es népszámlálási témájú történeti ITS-ábra, az eredeti kontúrok
  felmérési kora és mai jogi/negyednév-státusza nem igazolt. A települési PDF
  nyilvános elérése önmagában nem tisztázza az újrafelhasználási engedélyt.
  Az OSM-adatok OpenStreetMap contributors, ODbL 1.0 alatt állnak.
  Nincs cím-hozzárendelési vagy kataszteri felhasználási engedély/minősítés.

Újrafuttatás a repo gyökeréből, hálózat nélkül:
  PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-pecs-grounded-next/build-model.py --check
  PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-pecs-grounded-next/independent-audit.py --check
  PYTHONPATH=.local/geodata python data/neighborhoods/sources/municipal-pecs-grounded-next/freeze-package.py --check
  A build-model.py hálózati PROJ-elérést kifejezetten tilt. A runtime-proof.json
  rögzíti a használt könyvtárakat és PROJ-műveletet; a művelet 1 m-es metaadata
  nem a forráskép, a modell vagy a poligonok igazolt pontossága.
