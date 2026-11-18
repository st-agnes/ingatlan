#!/usr/bin/env python3
"""Rebuild selected, explicitly estimated commuter-town footprints offline."""
from pathlib import Path
from collections import Counter
import json,hashlib
from shapely.geometry import shape,mapping,Polygon,Point
from shapely.ops import transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
load=lambda fn:json.loads((HERE/fn).read_text())
forward=Transformer.from_crs(4326,23700,always_xy=True).transform
inverse=Transformer.from_crs(23700,4326,always_xy=True).transform
candidates={f['id']:f for f in load('diagnostic-candidates.geojson')['features']}
parents=load('prior-parent-features.geojson')['features']
target_map={(f['properties']['municipality'],f['properties']['name']):f['properties']['sourcePoint'] for f in load('target-circles-reference.geojson')['features']}
slugs={'Budaörs':'budaors','Tatabánya':'tatabanya','Dunakeszi':'dunakeszi','Szigetszentmiklós':'szigetszentmiklos','Gödöllő':'godollo'}
reports=[]
for city,specs in load('selection.json')['towns'].items():
 slug=slugs[city];reg=load(slug+'-registration.json');x0,y0,x1,y1=reg['extentEov'];width,height=reg['pixelSize'];features=[]
 for spec in specs:
  source_point=target_map[(city,spec['name'])]
  if 'candidate' in spec:
   original=candidates[spec['candidate']];assert original['properties']['municipality']==city and original['properties']['name']==spec['name']
   geom=shape(original['geometry']);method='physical_barrier_cell_estimate';source_details=original['properties'];quality=15
  else:
   coords=[(x0+(x-40)*(x1-x0)/(width-80),y0+(height-40-y)*(y1-y0)/(height-80)) for x,y in spec['points']]
   eov=Polygon(coords)
   if spec.get('clipParent'):
    parent=next(f for f in parents if f['properties']['municipality']==city and f['properties']['name']==spec['clipParent'])
    eov=eov.intersection(transform(forward,shape(parent['geometry'])))
   geom=transform(inverse,eov);method='map_or_text_estimate';source_details={'mapRegistration':slug+'-registration.json','map':slug+'-context.png','trace':spec,'parentSource':parent['properties']['selectedSource'] if spec.get('clipParent') else None};quality=24
  assert not geom.is_empty and geom.is_valid,(city,spec['name'],'invalid')
  assert geom.covers(Point(source_point['coordinates'])),(city,spec['name'],'does not cover source name point')
  props={'municipality':city,'name':spec['name'],'method':method,'estimated':True,'semanticFootprint':True,'qualityScore':quality,'candidateBoundaryKind':'neighbourhood','pointRadiusFallback':False,
   'sourceUrl':spec.get('evidenceUrls',[source_point['sourceUrl']])[0],
   'source':{'provider':'offline-physical-map-and-native-parent-interpretation','path':(HERE/'source-barriers.geojson').relative_to(ROOT).as_posix(),'pbfSha256':load('source-summary.json')['pbfSha256'],'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},
   'nameEvidence':[source_point],'evidenceUrls':spec.get('evidenceUrls',[]),'constructionEvidence':source_details,'approximateAreaSquareMetres':round(transform(forward,geom).area,1),
   'approximationNote':spec['note']+' Low-confidence practical search footprint: this can differ from a complete conventional neighbourhood perimeter. Native broader parent and smaller estate are not treated as equivalent. No circles, radius-derived geometry, Voronoi, nearest-label split or point hull.'}
  features.append({'type':'Feature','id':'commuter-next:'+slug+':'+str(len(features)),'properties':props,'geometry':mapping(geom)})
 payload=(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n').encode()
 filename=slug+'-features.geojson';path=HERE/filename
 if path.exists() and path.read_bytes()!=payload:raise RuntimeError('Frozen per-town output would change: '+filename)
 path.write_bytes(payload)
 reports.append({'municipality':city,'file':filename,'featureCount':len(features),'sha256':hashlib.sha256(payload).hexdigest(),'names':[f['properties']['name'] for f in features],'validGeometryCount':len(features),'sourcePointsInside':len(features),'methods':dict(Counter(f['properties']['method'] for f in features))})
summary={'schemaVersion':1,'featureCount':sum(r['featureCount'] for r in reports),'towns':reports,'circleCount':0,'voronoiCount':0,'allOutputGeometriesEstimated':True,'nationalCompletionPercentage':None}
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False),flush=True)
