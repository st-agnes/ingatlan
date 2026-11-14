#!/usr/bin/env python3
"""Rough subareas from actual roads inside observed municipal map quarters."""
import json,collections,hashlib,unicodedata
from pathlib import Path
from shapely.geometry import shape,mapping,Point
from shapely.ops import transform,unary_union,polygonize
from shapely.strtree import STRtree
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
enc=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n'
norm=lambda s:''.join(c for c in unicodedata.normalize('NFC',s).casefold() if c.isalnum())
to_eov=Transformer.from_crs(4326,23700,always_xy=True).transform;to_geo=Transformer.from_crs(23700,4326,always_xy=True).transform
native=load(OUT/'fehervar-native-features.geojson')['features']
core=load(ROOT/'data/neighborhoods/search-areas.geojson')['features']
covered={norm(n) for f in core+native if f['properties']['municipality']=='Székesfehérvár' for n in [f['properties']['name']]+f['properties'].get('aliases',[])}
labels=[f for f in load(OUT/'source-labels.geojson')['features'] if f['properties']['municipality']=='Székesfehérvár']
points=[transform(to_eov,shape(f['geometry'])) for f in labels];point_tree=STRtree(points)
roads=[]
for f in load(OUT/'source-barriers.geojson')['features']:
 p=f['properties'];t=p['source']['tags']
 if 'Székesfehérvár' not in p['municipalities']:continue
 if not(t.get('highway') in ['motorway','trunk','primary','secondary','tertiary'] or t.get('railway') or t.get('waterway')):continue
 roads.append((f,transform(to_eov,shape(f['geometry']))))
line_tree=STRtree([g for f,g in roads]);candidates=[]
for parent in native:
 p=parent['properties']
 if p['sourceDrawingIndices'] not in [[7],[402],[491],[581],[611],[650],[715],[977],[1796],[1241],[1974],[2779]]:continue
 area=transform(to_eov,shape(parent['geometry']));idx=[int(k) for k in line_tree.query(area,predicate='intersects')]
 network=unary_union([area.boundary]+[roads[i][1].intersection(area) for i in idx])
 for cell in polygonize(network):
  if not area.covers(cell.representative_point()) or not 3000<=cell.area<=4_000_000:continue
  hits=[int(k) for k in point_tree.query(cell,predicate='covers')]
  if len({norm(labels[k]['properties']['name']) for k in hits})!=1:continue
  label=labels[hits[0]];name=label['properties']['name']
  if norm(name) in covered:continue
  sourceways=[{'id':roads[i][0]['id'],'url':roads[i][0]['properties']['source']['url']} for i in idx if cell.boundary.intersection(roads[i][1]).length>20]
  if not sourceways:continue
  geometry=transform(to_geo,cell);assert geometry.is_valid
  props={'name':name,'municipality':'Székesfehérvár','method':'physical_barrier_cell_estimate','estimated':True,'semanticFootprint':True,'candidateBoundaryKind':'neighbourhood','qualityScore':20,
   'sourceUrl':p['sourceUrl'],'source':{'provider':'municipal-native-quarter-plus-osm-barriers','url':p['sourceUrl'],'path':p['source']['path'],'page':27,'sha256':p['source']['sha256']},
   'sourceMapParentName':p['name'],'sourceMapParentDrawingIndices':p['sourceDrawingIndices'],'boundingSourceWays':sourceways,
   'nameEvidence':[{'name':name,'coordinates':label['geometry']['coordinates'],'url':label['properties']['source']['url']}],
   'approximateAreaSquareMetres':round(cell.area,1),
   'approximationNote':'Approximate closed major-road/rail/water cell within an actually printed municipal quarter outline. The internal cell is a source-informed estimate, not an observed complete quarter border. Native source map extent registration is rough. No circle/Voronoi or generated nearest-point split.'}
  candidates.append({'type':'Feature','properties':props,'geometry':mapping(geometry)})
selected={}
for f in candidates:
 n=f['properties']['name']
 if n not in selected or selected[n]['properties']['approximateAreaSquareMetres']<f['properties']['approximateAreaSquareMetres']:selected[n]=f
output=list(selected.values());(OUT/'fehervar-subarea-features.geojson').write_text(enc({'type':'FeatureCollection','features':output}))
(OUT/'fehervar-subarea-summary.json').write_text(json.dumps({'featureCount':len(output),'names':list(selected),'candidateCount':len(candidates),'method':'native_quarter_outline_with_osm_major_barrier_subdivision','circleCount':0,'validGeometryCount':len(output)},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'count':len(output),'names':list(selected)},ensure_ascii=False))
