#!/usr/bin/env python3
"""Major-city source contours with explicit coarse closures and map splits."""
import json,hashlib,collections
from pathlib import Path
from shapely import make_valid
from shapely.geometry import Polygon,LineString,Point,shape,mapping
from shapely.ops import transform,unary_union,split
from shapely.affinity import affine_transform
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
FEATURES=[]

def read(p):return json.loads((ROOT/p).read_text())
def poly(g):
 if g.geom_type in ['Polygon','MultiPolygon']:return g
 return unary_union([x for x in g.geoms if x.geom_type in ['Polygon','MultiPolygon']])
def put(city,name,g,paths,urls,method,**extra):
 repaired=not g.is_valid
 if repaired:g=poly(make_valid(g))
 assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon'],(name,g.geom_type)
 assert 16<g.bounds[0]<23 and 45<g.bounds[1]<49,(name,g.bounds)
 FEATURES.append({'type':'Feature','id':'majorcity-more:'+city+':'+name,'properties':{'name':name,'municipality':city,'method':method,'estimated':True,'sourcePaths':paths,'sourceSha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'evidenceUrls':urls,'geometryRepair':'make_valid' if repaired else None,**extra},'geometry':mapping(g)})

def tatabanya():
 src='data/neighborhoods/sources/municipal-tatabanya-more/'
 old='data/neighborhoods/sources/municipal-west/'
 proof=read(old+'tatabanya-georeference-proof.json')
 affine=proof['affinePdfToEov']
 to_wgs=Transformer.from_crs(23700,4326,always_xy=True).transform
 def world(native):return transform(to_wgs,affine_transform(native,affine))
 D=read(src+'source-vector-trace.json');draws={d['sourceDrawingIndex']:d for d in D['selectedOriginalDrawings']}
 URL='https://njt.jog.gov.hu/document/c5/c56aLL_EJR_13372578-H_SZ_3.mell_klet.pdf'
 def closed(ids):
  points=[]
  for i in ids:
   items=draws[i]['exactPageLineItems']
   if not points:points.append([float(x) for x in items[0][1]])
   for item in items:points.append([float(x) for x in item[2]])
  return Polygon(points)
 for name,ids in [('Szőlőhegy',[3277,3267]),('VI-os telep',[4836]),('Felsőgalla',[4851])]:
  g=closed(ids)
  if not g.is_valid:g=poly(make_valid(g))
  put('Tatabánya',name,world(g),[src+'source-vector-trace.json',old+'tatabanya-georeference-proof.json'],[URL],'source_vector_inferred_closure',sourceDrawingIndices=ids,sourceYear=2018,approximationNotes='Existing source vector trace retained; the open endpoints are joined directly. Small source loops/spurs repaired as needed. This is the explicitly approximate fine subdivision previously deferred because the literal source outline did not close.')
 groups={x['properties']['name']:x for x in read(src+'compound-source-groups.geojson')['features']}
 sources=[src+'compound-source-groups.geojson',src+'source-vector-trace.json',old+'tatabanya-georeference-proof.json']
 specs=[
  ('Bánhida – Dózsakert',['Bánhida','Dózsakert'],[[180,304],[285,331],[335,349],[440,395]]),
  ('Szőlőhegy – Újváros – Sárberek',['Újváros','Sárberek'],[[190,308],[300,313],[365,320],[455,326]]),
  ('Nyugati ipari park – Erőmű ltp.',['Nyugati ipari park','Erőmű lakótelep'],[[10,310],[110,335],[160,348],[245,360]])]
 raw_proof=[]
 for group,names,divider in specs:
  if group.startswith('Szőlőhegy'):
   g=world(poly(make_valid(closed([3696]))))
  else:g=shape(groups[group]['geometry'])
  ln=world(LineString(divider))
  parts=[x for x in split(g,ln).geoms if x.geom_type=='Polygon']
  # A source label anchors the correct side; this does not claim the coarse divider is exact.
  for name in names:
   label='ERŐMŰ LTP.' if name=='Erőmű lakótelep' else name.upper()
   point=world(Point(D['sourceLabels'][label]['centre']))
   selected=[p for p in parts if p.covers(point)]
   assert len(selected)==1,(name,len(parts))
   put('Tatabánya',name,selected[0],sources,[URL],'source_map_inferred_divider',sourceYear=2018,aliases=['Erőmű ltp.'] if name=='Erőmű lakótelep' else [],parentAreaName=group,approximationNotes='Actual outer source contour split by a coarse manual line following the visible map sector/street corridor. Source label selects the named side. Internal divider is an approximation; no point-radius geometry.',estimatedDividerPdfCoordinates=divider)
  raw_proof.append({'group':group,'names':names,'estimatedDividerPdfCoordinates':divider,'parts':len(parts)})
 (HERE/'evidence/tatabanya-dividers.json').write_text(json.dumps(raw_proof,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
 tatabanya()
 (HERE/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':FEATURES},ensure_ascii=False,separators=(',',':'))+'\n')
 (HERE/'summary.json').write_text(json.dumps({'status':'working_checkpoint','featureCount':len(FEATURES),'cities':dict(collections.Counter(f['properties']['municipality'] for f in FEATURES)),'circleFallbackCount':0},ensure_ascii=False,indent=2)+'\n')
 print(collections.Counter(f['properties']['municipality'] for f in FEATURES))
