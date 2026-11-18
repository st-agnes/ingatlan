"""Offline final pair, keeping the frozen first two proposals unchanged."""
from pathlib import Path
import json,gzip
from shapely.geometry import shape,Polygon
from shapely.ops import unary_union,polygonize,transform
from pyproj import Transformer
HERE=Path(__file__).parent
P=HERE.parent
roads={}
for fn in P.glob('*-source-roads.geojson.gz'):
 for f in json.load(gzip.open(fn,'rt'))['features']:roads[f['id']]=f
to_m=Transformer.from_crs(4326,23700,always_xy=True).transform
names=['Veres Péter út','Sárgarózsa utca','Pesti határút','Lobbanó utca','Hősök fasora']
fs=[f for f in roads.values() if f['properties'].get('name') in names]
polys=list(polygonize(unary_union([shape(f['geometry']) for f in fs])))
assert len(polys)==1
g=polys[0].simplify(.000025,preserve_topology=True)
out=[dict(name='Nagyiccetelep',municipality='Budapest',method='source_map_polygon',estimated=True,lowConfidence=True,ring=list(g.exterior.coords),anchors=names,sourceUrl='https://www.bp16.hu/sites/default/files/hir/2013/dokumentum/2013_09_25_18_pdf_21376.pdf',supportingUrls=[f['properties']['source']['url'] for f in fs],approximationNote='Historical Nagyicce-telep limits explicitly listed by the XVI district official newspaper, page14: Veres Péter, Sárgarózsa, Pesti határút, Lobbanó, Hősök fasora. The frozen named roads form one closed ring. The current point label is farther east and is deliberately not forced into this historical outline; district historian separately warns that Nagyicce labels have been misplaced toward the Mátyásföld airport. Historical subdivision overlap is intentional. Road-centerline convention is estimated, not cadastral precision.',derivation='Polygonize union of actual frozen named-road lines from all four saved sectors; exactly one bounded polygon. Simplify0.000025degree; no use of point for geometry or selection.')]

ring=[
 [19.2949568,47.471498],
 [19.296013,47.4720645],
 [19.2977483,47.4730948],
 [19.2995148,47.4741151],
 [19.3004551,47.4734151],
 [19.301353,47.473996],
 [19.3023214,47.4732693],
 [19.3036011,47.4723763],
 [19.3053153,47.471201],
 [19.3078523,47.4693976],
 [19.3103862,47.4676278],
 [19.3122952,47.4662577],
 [19.3128921,47.4656957],
 [19.31244,47.4654738],
 [19.3119307,47.4652322],
 [19.3112642,47.4645039],
 [19.3101582,47.4647777],
 [19.3091281,47.4651657],
 [19.308813,47.465297],
 [19.297843,47.469007],
 [19.2953136,47.4690329],
 [19.2950524,47.4700975],
 [19.2949568,47.471498]]
ns=['Zrínyi utca','Nagyszentmiklósi út','Szigetcsép utca','Barnabás utca','Szárazhegy út','Ököl utca','Pesti út']
out.append(dict(name='Szárazhegy',municipality='Budapest',method='source_map_polygon',estimated=True,lowConfidence=True,ring=ring,anchors=ns,sourceUrl='https://www.hatvanizoltan.hu/index.php?id=Szarazhegy_LakoteruletBeepitesiTerv',supportingUrls=['https://www.hatvanizoltan.hu/doc/Szarazhegy/3.pdf','https://www.hatvanizoltan.hu/doc/Telepuleskepi-Arculati-Kezikonyv.pdf','https://egy.hu/barangolo/barangolas-a-fovaros-peremen-rakoskerten-es-azon-tul-118607']+[f['properties']['source']['url'] for f in roads.values() if f['properties'].get('name') in ns],approximationNote='Broad, inferred Szárazhegy residential locality envelope from actual street fabric: Nagyszentmiklósi at northwest, a short Szigetcsép/Barnabás step to Szárazhegy út at north, Szárazhegy/Ököl at east, Pesti at south and Zrínyi at west. This is an intentionally approximate search-area convention around the existing hillside streets; the northwest and western limits are inferred transitions with neighboring Rákoscsaba subdivisions. Public planning sources verify Szárazhegy locality/development around these roads but do not define this entire perimeter. Includes the older streets southwest of Szigetcsép as well as the developed northeastern strip; does not equate the whole neighborhood with Panoráma first phase or the proposed expansion parcel. No official whole-quarter boundary is claimed.',derivation='Manual ring following saved named-road vertices and selected road junctions. Long Pesti segment represented with coarse source-road anchors. Scope inferred from locality text and actual street-group fabric; no radius, point dimensions or synthetic rectangle.'))
for f in out:
 g=Polygon(f['ring']);assert g.is_valid and not g.is_empty,f['name']
 f['areaSquareMetres']=round(transform(to_m,g).area)
 f['ring']=[[round(x,8),round(y,8)] for x,y in f['ring']]
(HERE/'proposed-traces-3.json').write_text(json.dumps(dict(schemaVersion=1,date='2026-11-15',features=out),ensure_ascii=False,indent=2)+'\n')
for f in out:print(f['name'],f['areaSquareMetres'],len(f['ring']))
