#!/usr/bin/env python3
"""Use other actual colored municipal PDF extents with explicit coarse fine splits."""
import json,collections
from pathlib import Path
import fitz
from shapely.geometry import Polygon,shape,box,mapping
from shapely import make_valid
from shapely.ops import unary_union,transform
from shapely.affinity import affine_transform
from pyproj import Transformer
import build
HERE=Path(__file__).resolve().parent
SRC='data/neighborhoods/sources/municipal-sopron-next/'
TRACE='data/neighborhoods/expansion-20261114/major-city-more/evidence/sopron-rough-core-traces.json'
URL=build.read(SRC+'source-extraction-proof.json')['originalUrl']
if __name__=='__main__':
 page=fitz.open(build.ROOT/(SRC+'source-pages1-2.pdf'))[0];ds=page.get_drawings()
 beta=build.read(SRC+'registration.json')['page1PdfPointsToEovMatrix']
 affine=[beta[0][0],beta[1][0],beta[0][1],beta[1][1],beta[2][0],beta[2][1]]
 unwgs=Transformer.from_crs(23700,4326,always_xy=True).transform
 def world(g):return transform(unwgs,affine_transform(g,affine))
 colors={'Virágvölgy':(0,0,.867),'orange':(1,.498,0),'green':(0,1,.247)}
 surfaces={};proof={}
 for name,col in colors.items():
  polys=[];indices=[]
  for i,d in enumerate(ds):
   if d['fill']is None or max(abs(a-b)for a,b in zip(d['fill'],col))>.005 or d['rect'].x0<100 or d['rect'].y0<125:continue
   indices.append(i);coords=[]
   for item in d['items']:
    if item[0]!='l':continue
    a,b=tuple(item[1]),tuple(item[2])
    if coords and coords[-1]!=a:
     if len(coords)>=3:polys.append(make_valid(Polygon(coords)))
     coords=[]
    if not coords:coords=[a]
    coords.append(b)
   if len(coords)>=3:polys.append(make_valid(Polygon(coords)))
  # Native CAD fill fragments have float endpoint cracks. Closing by quarter-point
  # is explicitly approximate, about6.3metres in the existing georeference.
  g=unary_union(polys).buffer(.25).buffer(-.25)
  surfaces[name]=g;proof[name]={'sourceDrawingIndices':indices,'fillFragments':len(polys),'nativeClosureRadiusPdfPoints':.25,'nativeBounds':g.bounds}
 traces=build.read(TRACE)
 paths=[SRC+'source-pages1-2.pdf',SRC+'registration.json',TRACE]
 def put(name,g,method,**extra):
  build.put('Sopron',name,world(g),paths,[URL],method,sourceSubdivisionKind='approximate_named_source_map_area',license='Municipal map reuse status see source collection; originalsource preserved',approximationNotes='Approximate geographic registration reused. Actual colored PDF fill surfaces are joined with a0.25PDFpoint closure to remove float cracks. Named fine splits and road tracing are coarse estimates; no legal/current-boundary verification. '+extra.pop('note',''),**extra)
 put('Virágvölgy',surfaces['Virágvölgy'],'source_vector_fill_union',aliases=['Virágvölgy és környéke'],note='The native darkblue planning surface is explicitly Virágvölgy és környéke in the source legend; retain the broad named search footprint.')
 for name,ys in traces['orangeCorridorDividersPdfY'].items():
  g=surfaces['orange'].intersection(box(0,ys[0],1200,ys[1]))
  put(name,g,'source_map_inferred_divider',estimatedNativeYRange=ys,note=traces['orangeDivisionNote'])
 central={x['name']:x for x in traces['units']}
 for name,x in central.items():
  native=Polygon(x['ring'])
  if name!='Belváros':native=native.intersection(surfaces['green'])
  put(name,native,'map_trace_rough',aliases=x.get('aliases',[]),note=traces['notes'])
 outside=surfaces['green'].difference(Polygon(central['Belváros']['ring']))
 put('Belváros külső',outside,'source_map_parent_minus_historic_core',note='Outer central planning-scope footprint with the visible Várkerület historic core removed. The term is also retained in current OSM place names; exact whole-quarter interpretation is approximate.')
 (HERE/'sopron-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':build.FEATURES},ensure_ascii=False,separators=(',',':'))+'\n')
 (HERE/'evidence/sopron-native-surfaces.geojson').write_text(json.dumps({'type':'FeatureCollection','coordinateSpace':'NATIVE_PDF_PAGE1_POINTS_NOT_GEOGRAPHIC','features':[{'type':'Feature','properties':{'name':n,'coordinateSpace':'NATIVE_PDF_PAGE1_POINTS_NOT_GEOGRAPHIC'},'geometry':mapping(g)}for n,g in surfaces.items()]},ensure_ascii=False,separators=(',',':'))+'\n')
 (HERE/'evidence/sopron-source-proof.json').write_text(json.dumps({'sourcePdfPage':1,'colors':proof,'featureCount':len(build.FEATURES),'circleFallbackCount':0,'approximateClosuresAndSplits':True},ensure_ascii=False,indent=2)+'\n')
 print(collections.Counter(f['properties']['municipality']for f in build.FEATURES))
