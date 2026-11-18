#!/usr/bin/env python3
"""Build coarse map/text estimates without network access."""
from pathlib import Path
import hashlib,json
from shapely.geometry import Polygon,shape,mapping
HERE=Path(__file__).resolve().parent
spec=json.loads((HERE/'gyor-manual-traces.json').read_text())
points={f['properties']['name']:f for f in json.loads((HERE/'name-points.geojson').read_text())['features'] if f['properties']['municipality']=='Győr'}
fs=[]
for area in spec['areas']:
 g=Polygon(area['ring']);point=points[area['name']]
 assert g.is_valid and g.covers(shape(point['geometry'])),area['name']
 primary=spec['urls'][0] if area['name'] in ['Ménfő','Csanakfalu','Csanakhegy'] else spec['urls'][2]
 fs.append({'type':'Feature','id':'gyor-map-text:'+area['name'],'properties':{
  'name':area['name'],'municipality':'Győr','method':spec['method'],'estimated':True,'qualityScore':20,
  'sourceUrl':primary,'evidenceUrls':spec['urls'],'source':{'provider':'manual-map-text-inference','url':primary},
  'sourcePrintedPages':([298] if area['name']=='Szalmatelep' else [291] if area['name']=='Újtelep' else None),
  'sourcePaths':['data/neighborhoods/expansion-20261114-next/gyor-sopron/gyor-source-roads.geojson','data/neighborhoods/expansion-20261114-next/gyor-sopron/name-points.geojson'],
  'streetContextSha256':hashlib.sha256((HERE/'gyor-source-roads.geojson').read_bytes()).hexdigest(),
  'approximationNote':spec['note'],'boundaryAnchors':area['anchors'],'absoluteAccuracyEstablished':False,
  'namePoint':{'coordinates':point['geometry']['coordinates'],'sourceUrl':point['properties']['source']['url']}},'geometry':mapping(g)})
(HERE/'gyor-manual-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,separators=(',',':'))+'\n')
print('Győr map/text estimates',len(fs))
