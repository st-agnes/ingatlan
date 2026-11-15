#!/usr/bin/env python3
"""Deterministic offline estimated polygons and preserved native surfaces."""
from pathlib import Path
import json,gzip,hashlib,math
from shapely.geometry import Polygon,shape,mapping
HERE=Path(__file__).resolve().parent
targets=json.loads((HERE/'target-selection.json').read_text());pts={(p['municipality'],p['name']):p for p in targets}
spec=json.loads((HERE/'manual-traces.json').read_text())
pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.geojson.gz'))}
fs=[];checks=[]
for a in spec['areas']:
 g=Polygon(a['ring']);key=(a['municipality'],a['name']);p=pts[key]['pointCandidates'][0]
 assert g.is_valid and not g.is_empty and g.geom_type=='Polygon',key
 area=g.area*111320**2*math.cos(math.radians(g.centroid.y));assert 1000<area<20000000,(key,area)
 inside=g.covers(shape({'type':'Point','coordinates':p['coordinates']}))
 props={'name':a['name'],'municipality':a['municipality'],'method':'manual_street_map_text_estimate','estimated':True,'lowConfidence':True,'qualityScore':20,'sourceUrl':a['urls'][0],'source':{'provider':'archived-road-and-public-map-text','url':a['urls'][0]},'supportingUrls':list(dict.fromkeys(a['urls']+[p['sourceUrl']])),'approximationNote':'Rough search-area estimate from preserved actual street/rail/waterway geometry and cited public map/text evidence; not an official or surveyed boundary. '+a['note'],'boundaryAnchors':a['anchors'],'sourceContextSha256':pins,'namePoint':{'coordinates':p['coordinates'],'sourceUrl':p['sourceUrl'],'insideEstimatedPolygon':inside},'areaSquareMetres':round(area,1),'absoluteAccuracyEstablished':False}
 fs.append({'type':'Feature','id':'pest-northwest:'+a['municipality']+':'+a['name'],'properties':props,'geometry':mapping(g)})
 checks.append({'municipality':a['municipality'],'name':a['name'],'valid':True,'pointInside':inside,'areaSquareMetres':round(area,1)})
if (HERE/'native-selections.json').exists():
 surfaces={f['id']:f for f in json.loads(gzip.open(HERE/'source-surfaces.geojson.gz','rt').read())['features']}
 for a in json.loads((HERE/'native-selections.json').read_text()):
  src=surfaces[a['sourceId']];g=shape(src['geometry']);assert g.is_valid
  p=pts[(a['municipality'],a['name'])]['pointCandidates'][0];url=src['properties']['source']['url']
  pr={'name':a['name'],'municipality':a['municipality'],'method':'native_source_surface','estimated':False,'sourceUrl':url,'source':src['properties']['source'],'supportingUrls':a.get('urls',[])+[p['sourceUrl']],'approximationNote':a['note'],'partialSourceFootprint':a.get('partial',False),'sourceGeometryUnmodified':True,'namePoint':p}
  fs.append({'type':'Feature','id':'pest-northwest:'+a['municipality']+':'+a['name'],'properties':pr,'geometry':src['geometry']})
  checks.append({'municipality':a['municipality'],'name':a['name'],'valid':True,'nativeSourceId':a['sourceId']})
names={(f['properties']['municipality'],f['properties']['name']) for f in fs};assert len(names)==len(fs)
(HERE/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,separators=(',',':'))+'\n')
remain=[{'municipality':p['municipality'],'name':p['name']} for p in targets if (p['municipality'],p['name']) not in names]
(HERE/'summary.json').write_text(json.dumps({'date':'2026-11-15','featureCount':len(fs),'estimatedFeatureCount':sum(f['properties']['estimated'] for f in fs),'nativeFeatureCount':sum(not f['properties']['estimated'] for f in fs),'startingMissingNameCount':len(targets),'remainingNames':remain,'circleCount':0,'voronoiCount':0,'completeCityCoverageEstablished':False,'checks':checks},ensure_ascii=False,indent=2)+'\n')
print('Built',len(fs),'polygons;',len(remain),'names remain')
