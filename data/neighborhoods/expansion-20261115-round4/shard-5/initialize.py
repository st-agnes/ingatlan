from pathlib import Path
import json,gzip,hashlib
P=Path(__file__).resolve().parent;T=json.load(open(P/'targets.json'));C={f['id']:f for f in json.load(open(P/'candidate-cells.geojson'))['features']}
raw=[
('Szarvas','Bikazug','rural','The enclosure follows the oxbow-side rural road network across the Bikazug locality, including cultivated and holiday land; the historical zug boundary is approximate.'),
('Szarvas','Galambos','street','Whole local road-and-water enclosure around Galambos, west of the arboretum; it includes the mixed rural and institutional locality rather than the nearest industrial plot.'),
('Szarvas','Nyúlzug','street','The oxbow bend and external street network provide a broad Nyúlzug outline; small internal farm tracks were omitted.'),
('Szarvas','Pepi-kert','area:24775905','Official university/operator usage identifies the Szarvasi Arborétum as Pepi-kert. The full mapped arboretum is used for the common modern name; the older approximately 40 ha Pepi garden is a historical subset with uncertain limits.'),
('Kazincbarcika','Herbolya','street','Broad external-road enclosure around the former mining settlement and Herbolya lakes; historical Herbolya extends beyond the former colony and its exact limits are uncertain.'),
('Mezőtúr','Felsőrész','major','Whole major-road and river enclosure around the historical upper quarter. This follows actual transport/water features but estimates the historical quarter rather than reproducing a surveyed district boundary.'),
('Mezőtúr','Kétgátközi kert','street','Broad garden-quarter enclosure on the eastern river side, following the actual external road/water network rather than one small garden parcel.'),
('Borsodivánka','Dózsatelep','area:282270939','The separate mapped residential settlement beside the name point is used as an estimated whole settlement footprint; association is inferred from map context.'),
('Túrkeve','Bocskorkert','rural','Actual surrounding rural-road enclosure of the mapped garden locality south of the main settlement; historical garden extent is uncertain.'),
('Karcag','Déli külváros','major','Broad southern housing quarter enclosed by main road and railway features. Internal residential blocks are included together; the exact colloquial southern-suburb boundary is uncertain.'),
('Nádudvar','Dembrovszky-tanya','area:627871963','The mapped farmyard contains the named tanya point and represents the compact farmstead. Outlying historical farmland is not included.'),
('Vésztő','Mágor','rural','Whole rural-road enclosure at Mágor within the mapped Mágor-puszta landscape. This estimates the locality, not the entire nature-reserve boundary.'),
('Szerencs','Ipari park','street','Broad eastern industrial area bounded by main road, railway and connecting streets. Municipal TAK identifies the eastern industrial park between railway and road 37; the outline is a coarse whole-area interpretation.'),
('Kaba','Kis Kaba tanya','rural','Large actual rural-road and waterway enclosure containing the old locality, rather than an isolated farm building. The dispersed historical tanya district has no verified formal boundary.'),
('Gyula','Egykori Ella-major','rural','Road and drainage enclosure at the former major site, including its agricultural surroundings; the vanished estate boundary is uncertain.'),
('Gyula','Sitka','rural','Actual forest-road and drainage enclosure of the locality; broader historical forest/estate usage may overlap beyond this estimated area.'),
('Hajdúdorog','Lókert','rural','Whole rural-road enclosure around the mapped Lókert locality; local toponymic sources place Lókert in the southeastern city fringe.'),
('Derecske','Rózsakert','rural','Broad actual road enclosure covering the orchard/garden locality; includes the mapped orchards and connecting agricultural land.'),
('Nyírtelek','Pallag-puszta','rural','Broad actual rural-road enclosure of the dispersed puszta locality. It includes agricultural surroundings rather than only the nearest small farmyards.'),
('Hajdúhadház','Kunkert','rural','Actual external rural-road enclosure of the historical garden locality east of the main settlement; old garden boundaries are approximate.')]
selections=[]
for city,name,kind,note in raw:
 m=next(m for m in T['municipalities'] if m['municipality']==city);t=next(t for t in m['targets'] if t['name']==name)
 s={'municipality':city,'name':name,'contextKey':m['contextKey'],'kind':'area' if kind.startswith('area:') else 'cell','approximationNote':note,'batch':1,'pointSource':t['pointCandidates'][0],'supportingUrls':[]}
 if kind.startswith('area:'):s['sourceAreaIds']=['osm:way:'+kind.split(':')[1]]
 else:s['cellId']=m['contextKey']+':'+name+':'+kind
 if city=='Szarvas' and name=='Pepi-kert':s['supportingUrls']=['https://pepikert.hu/','https://visitszarvas.com/latnivalok/szarvasi-arboretum/','https://ertektar.bekesmegye.hu/ertektari-ertek/szarvasi-arboretum/']
 if city=='Szerencs':s['supportingUrls']=['https://szerencs.hu/wp-content/uploads/2026/03/Szerencs_TAK.pdf'];s['sourceExcerpt']='A legnagyobb iparterület a vasútvonal és a 37. számú főút között, Sátoraljaújhely irányába elhelyezkedő Keleti Iparterület, Ipari Park címmel.'
 if city=='Kazincbarcika':s['supportingUrls']=['https://kolorcity.hu/uploads/files/Helyi_Kozossegi_Fejlesztesi_Strategia_2.modositas.pdf','https://njt.jog.gov.hu/jogszabaly/2022-20-SP-5Y1008']
 if city=='Mezőtúr':s['supportingUrls']=['https://mezotur.hu/wp-content/uploads/2022/10/Mezotur-Megalapozo_2020-julius.pdf','https://njt.jog.gov.hu/jogszabaly/2004-2-SP-5Y1706']
 if city=='Hajdúdorog':s['supportingUrls']=['https://mdh.unideb.hu/helynev.php?adatlap=26-10-596%2F1&c=26-10-596&v=Hajd%C3%BAdorog']
 selections.append(s)
(P/'selection.json').write_text(json.dumps(selections,ensure_ascii=False,indent=2)+'\n')
