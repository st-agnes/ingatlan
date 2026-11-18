#!/usr/bin/env python3
"""Build rough street-context bounds from saved rings; no PBF or network needed."""
from pathlib import Path
import hashlib,json,math,unicodedata
from shapely.geometry import Polygon,Point,LineString,shape,mapping
from shapely.ops import split,unary_union
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
spec=json.loads((HERE/'manual-traces.json').read_text())
pts={f['properties']['name']:f for f in json.loads((HERE/'name-points.geojson').read_text())['features']}
parents=json.loads((HERE/'parent-features.geojson').read_text())['features']
sourcepins={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*-source-roads.geojson.gz')}
fs=[];checks=[]
for a in spec['areas']:
 np=pts[a['name']];point=shape(np['geometry'])
 if a.get('parentSplit'):
  parent=next(f for f in parents if f['properties']['name']==a['parentSplit']['name'])
  pieces=split(shape(parent['geometry']),LineString(a['parentSplit']['cut']))
  own=[part for part in pieces.geoms if part.covers(point)]
  assert len(own)==1,(a['name'],len(own))
  g=own[0]
 else:g=Polygon(a['ring'])
 if a.get('clipToParent'):
  clip=next(f for f in parents if f['properties']['name']==a['clipToParent'])
  g=g.intersection(shape(clip['geometry']))
 assert g.is_valid and g.covers(point),a['name']
 m2=g.area*111320**2*math.cos(math.radians(g.centroid.y))
 cap=a.get('maximumAreaSquareMetres') or (250_000 if 'lakópark' in a['name'].casefold() or 'lakókert' in a['name'].casefold() else 750_000 if 'lakótelep' in a['name'].casefold() else 10_000_000)
 assert m2<=cap,(a['name'],m2,cap)
 contexts=[f for f in parents if shape(f['geometry']).covers(point)]
 contexts=sorted(contexts,key=lambda f:shape(f['geometry']).area)
 sourceurl=a.get('urls',[np['properties']['source']['url']])[0]
 pr={'name':a['name'],'municipality':'Budapest','method':'manual_street_map_text_estimate','estimated':True,'qualityScore':20,'lowConfidence':True,
  'source':{'provider':'manual-street-context-inference','url':sourceurl},'sourceUrl':sourceurl,'supportingUrls':a.get('urls',[]),
  'sourceContextSha256':sourcepins,'namePoint':{'coordinates':np['geometry']['coordinates'],'sourceUrl':np['properties']['source']['url']},
  'parentContext':[{'name':f['properties']['name'],'id':f['id'],'sourceUrl':f['properties'].get('source',{}).get('url')} for f in contexts[:5]],
  'approximationNote':spec['note'],'boundaryAnchors':a['anchors'],'areaSquareMetres':round(m2,1),'absoluteAccuracyEstablished':False}
 if a.get('clipToParent'):
  pr['clippedToNativeParent']=a['clipToParent'];pr['parentSourceUrl']=clip['properties'].get('source',{}).get('url')
 if a.get('maximumAreaSquareMetres'):
  pr['maximumAreaSquareMetres']=a['maximumAreaSquareMetres'];pr['sizeOverrideJustification']=a.get('sizeOverrideJustification')
 if a.get('parentSplit'):
  pr['parentSplit']=a['parentSplit'];pr['parentSourceUrl']=parent['properties'].get('source',{}).get('url')
 fs.append({'type':'Feature','id':'budapest-remaining:'+a['name'],'properties':pr,'geometry':mapping(g)})
 checks.append({'name':a['name'],'valid':True,'ownPointInside':True,'areaSquareMetres':round(m2,1),'maximumAreaSquareMetres':cap})
(HERE/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':fs},ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'summary.json').write_text(json.dumps({'featureCount':len(fs),'circleCount':0,'voronoiCount':0,'checks':checks},ensure_ascii=False,indent=2)+'\n')
print('Budapest additional manual bounds',len(fs))
