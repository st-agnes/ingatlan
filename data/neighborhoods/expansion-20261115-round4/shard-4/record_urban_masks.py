from pathlib import Path
import json
from shapely.geometry import shape,Polygon,Point
from shapely.ops import transform,unary_union
from pyproj import Transformer
R=Path(__file__).resolve().parent
T=Transformer.from_crs(4326,23700,always_xy=True).transform
masks=[
('Kecskemét','Hollandfalu',[[696620,174805],[696850,175025],[697050,175035],[697320,174775],[697200,174650],[696970,174535]],'Nyíri út, Károly Róbert körút and the Tömörkény/Károly Róbert row-house road fabric; municipal PDFp175 explicitly contrasts Hollandfalu row-house streets with the housing estate.'),
('Kecskemét','Bogovicsfalu',[[697170,174960],[697390,175090],[697620,174865],[697360,174620],[697180,174720]],'Március15 utca/Nyíri út and adjacent older Máriahegy street fabric; municipal PDFp50 uses Bogovicsfalu as the western endpoint of the missing outer-ring connection.'),
('Kecskemét','Miklovicsfalu',[[698420,176470],[698620,176570],[698900,176420],[698950,176180],[698650,176120],[698430,176250]],'Vacsi köz, Nagy Lajos király körút, Széna/Aranyeső and north-side roads; municipal PDFp178 names Miklovics-telep among the historic small settlements of the Vacsi-köz quarter.'),
('Pásztó','Homok',[[698850,287790],[699140,287745],[699090,287405],[698795,287470],[698790,287625],[698835,287655]],'Homok utca, Mátraszőlősi/Mágnes road and adjoining sports-field/settlement street edges.'),
('Pásztó','Plathi-negyed',[[698155,287350],[698500,287300],[698760,287205],[698690,286990],[698160,286870],[698100,287000],[698120,287150]],'Ifjúság, Május1, Vasvári Pál, Honvéd, Diófa and connecting streets; includes a group of blocks rather than the single label block.'),
('Pásztó','Major',[[698030,286440],[698380,286460],[698510,286200],[698430,285930],[698200,285790],[698030,285900]],'Railway/Vasút and Arany János north, Gárdonyi/Kazinczy/Sport/Múzeum road fabric, Kossuth west-side alignment.'),
('Tiszakécske','Dózsa telep',[[728200,178000],[728900,178030],[729500,177600],[729180,177260],[728380,177300],[728050,177650]],'Szélmalom, Gyár/Dózsa/Homok roads and adjoining northwest housing blocks, with a coarse transition toward Rákóczi estate.'),
('Tiszakécske','Rákóczi telep',[[728500,177180],[729250,177260],[729500,176820],[728800,176500],[728400,176700]],'Kőrösi/Ady Endre, Óbögi/Szarvas/Márton and adjoining southwest residential road fabric.'),
('Tiszakécske','Ókécske',[[730300,177450],[730750,177200],[731050,177250],[731500,177090],[731950,176850],[732000,176400],[731500,176250],[730720,176420],[730400,176600],[730350,176900]],'Eastern historic settlement street cluster around the Reformed church/Templom tér, Tisza sor and river-side streets; parent/child overlaps with central modern quarter remain intentional.'),
('Sándorfalva','Új osztás',[[731350,114930],[732190,114910],[732150,114330],[731650,114330],[731150,114650]],'Erdő sor, Sövényházi út, Alkotmány körút and the Citera/Fácán/Cinke/Fürj/Őz road grid.'),
('Csongrád','Alsóváros',[[733200,152050],[733800,152000],[734050,151700],[733850,151250],[733250,151250],[733000,151550]],'Lower railway crossing, Vasut/Bihari/Erzsébet/Árpád and surrounding southern residential street fabric; broad district interpretation.'),
('Csongrád','Piroskaváros',[[733150,153680],[733500,153680],[733880,153300],[733790,152980],[733250,153100],[733080,153340]],'Northern residential blocks around Piroska János tér/school and Szőlőhegyi/Bercsényi/Bacsó/István street fabric.'),
('Csongrád','Sárkányfarok',[[733650,153560],[733850,153370],[734150,153050],[733650,153020],[733580,153260]],'Northeast tapering residential street fabric near Móra Ferenc rakpart, Fohász/Almás/Zsilip and Tisza-side road.'),
('Csongrád','Válykostelep',[[733000,152450],[733380,152480],[733520,151650],[733000,151400],[732850,151650],[732750,152000]],'Western station/industrial and cemetery fringe between Széchenyi/Fő road, railway and Temető road; adjacent open land included.'),
('Újszentiván','Délnyugat Lakópark',[[736700,94100],[736970,94300],[737250,94190],[737410,93950],[736830,93720],[736550,93900]],'Szerb/Nyugati/Novákító and Sport/Magyar/Fedresházi/Szigeti road fabric, not a single building footprint.'),
('Újszentiván','Major lakópark',[[738100,94730],[738340,94790],[738440,94520],[738220,94470],[738100,94610]],'Whole small housing estate loop at Major/Fürj street and its access from Fő street.'),
('Tiszaföldvár','Homok',[[740750,180155],[740910,180262],[741140,180533],[742330,179886],[742266,179314],[742952,179283],[743095,178819],[742980,178000],[742850,177500],[742000,177750],[740650,178750],[740606,179021]],'Primary2021ITS PDFp48 lists Homok action-area street circuit: Ókincsem Fő/I, Aranykert, Beniczky,442road, built-up limit, Cibakháza municipal limit and Kürti. Approximate search envelope of the northern/southern Homok planning units, not an exact legal action-area trace.'),
('Törökszentmiklós','Fáy-lakótelep',[[753100,205420],[753250,205600],[753550,205650],[753450,205300],[753250,205220],[753100,205350]],'Whole Fáy András lakótelep loop between the Tinóka-side Galamb road and Táncsics approach.'),
('Törökszentmiklós','Kisszőlő',[[751020,204480],[751400,204700],[751950,204850],[752200,204600],[751650,204350],[751180,204150]],'Western Kossuth/Szolnoki/Vörösmarty road belt and surrounding older vineyard-settlement road blocks.'),
('Törökszentmiklós','Partalja',[[752000,205470],[752570,205350],[752420,204820],[751880,204930]],'Szellő/Határ/Pacsirta/Margit/Topart and Vásárhelyi/Alatkai road belt beside Tinóka.'),
('Noszvaj','Alvég',[[756810,288680],[757140,288720],[757250,288580],[757290,288395],[757000,288380],[756825,288460]],'Lower village roads around Mátyás tér, Deák Ferenc, Arany János and Honvéd streets; adjoining residential land included.'),
('Noszvaj','Síkfőkút',[[755650,290700],[756150,290600],[756230,290350],[756400,290100],[756200,289920],[755650,289980],[755250,290100],[755350,290260],[755650,290300]],'Whole holiday/settlement road cluster around Síkfőkúti lake, Gyöngyvirág/Cseres/Várkút, Egri/Diós/Lépcsős/Várhegy and Szoboszlói roads; includes land around the lakes rather than literal water outlines.'),
('Mezőkövesd','Zsóry-fürdő',[[759800,273650],[760320,273920],[760440,273740],[761150,273850],[761210,273420],[760320,273020],[760150,273100],[759970,273410]],'Whole thermal/holiday district: bath complex plus Ciklámen/Napraforgó/Ostoros/Fülemüle street grid, western channel and southern access-road belt. Municipality clip retains only Mezőkövesd side.')]
task=json.loads((R/'source-inputs/task.json').read_text());lookup={(m['municipality'],t['name']):(m,t) for m in task['municipalities'] for t in m['targets']};ss=json.loads((R/'selections.json').read_text());reviews=[]
for city,name,coords,anchors in masks:
 m,t=lookup[(city,name)];mask=Polygon(coords);assert mask.is_valid,(city,name)
 cells=json.loads((R/'inspection'/(m['contextKey']+'-cells.geojson')).read_text())['features'];gs=[transform(T,shape(f['geometry'])) for f in cells]
 selected=[i for i,g in enumerate(gs) if g.intersection(mask).area/g.area>.5]
 pt=transform(T,Point(t['pointCandidates'][0]['coordinates']))
 pointcells=[i for i,g in enumerate(gs) if g.covers(pt)]
 selected=sorted(set(selected+pointcells));g=unary_union([gs[i] for i in selected]);ratio=g.area/mask.area
 note='Low-confidence whole-quarter estimate from a visually reviewed group of real archived road/landscape blocks. '+anchors+' The manual source-map selection groups blocks into an approximate neighborhood; source place point only checks identity and never sets size. Internal/outer transitions are inferred, may overlap adjacent quarters and have no claimed modern boundary accuracy.'
 if ratio>3 or ratio<.25 or not selected:
  kind='manual-eov';spec={'municipality':city,'name':name,'kind':kind,'coordinates':coords,'note':note+' The complete coarse road-map envelope is retained where individual source compartments are too large/open or fragmented.'};g=mask
 else:
  kind='cells';spec={'municipality':city,'name':name,'kind':kind,'cellIndexes':selected,'note':note,'manualGroupSelectionEov':coords,'sourceRoadContext':anchors}
 if city=='Kecskemét':spec['sourceUrl']='https://kecskemet.hu/uploaded_files/files/document/2022-11/69-2021_%28X_21%29_normativ_hatarozat_melleklet_2.pdf'
 if city=='Tiszaföldvár':spec['sourceUrl']='https://tiszafoldvar.hu/doks/tfk/its_tiszafoldvar_2021.pdf'
 ss.append(spec);reviews.append({'municipality':city,'name':name,'manualSourceRoadMaskEov':coords,'sourceRoadContext':anchors,'selectedCellIndexes':selected,'kind':kind,'finalToMaskAreaRatio':ratio,'areaKm2':g.area/1e6,'knownPointInside':g.covers(pt)})
 print(city,name,kind,len(selected),round(g.area/1e6,4),'ratio',round(ratio,2),'point',g.covers(pt))
(R/'manual-quarter-mask-review.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2)+'\n');(R/'selections.json').write_text(json.dumps(ss,ensure_ascii=False,indent=2)+'\n')
