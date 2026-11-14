#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
from shapely.geometry import shape,mapping,Polygon,Point,LineString
from shapely.ops import unary_union,transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent
spec=json.loads((HERE/'manual-traces.json').read_text());targets=json.loads((HERE/'target-names.json').read_text())
pts={f['name']:f['pointCandidates'][0] for f in targets if f['pointCandidates']}
areas=json.loads((HERE/'literal-local-areas.geojson').read_text())['features'];areaById={f['properties']['id']:f for f in areas}
lines=json.loads((HERE/'literal-local-lines.geojson').read_text())['features']
SOURCE='https://download.geofabrik.de/europe/hungary-261112.osm.pbf'
to=Transformer.from_crs(4326,23700,always_xy=True)
CITY=shape(json.loads((HERE/'source-municipality.geojson').read_text())['geometry'])
features=[];review=[]
def put(name,g,context,extra={}):
 g=g.intersection(CITY)
 if not g.is_valid:g=g.buffer(0)
 assert g.is_valid and not g.is_empty
 names=[name]+extra.get('aliases',[])
 for own in [pts[n] for n in names if n in pts]:assert g.covers(Point(own['coordinates'])),name
 metric=transform(to.transform,g);assert 1000<metric.area<4e6,(name,metric.area)
 nearby=[]
 for l in lines:
  lg=shape(l['geometry'])
  if lg.intersects(g):nearby.append({'id':l['properties']['id'],'name':l['properties'].get('name'),'highway':l['properties'].get('highway'),'railway':l['properties'].get('railway'),'waterway':l['properties'].get('waterway'),'sourceUrl':l['properties']['sourceUrl']})
 prop={'name':name,'municipality':'Miskolc','method':'manual_local_road_landuse_footprint_estimate','estimated':True,'quality':20,'sourceUrl':SOURCE,'additionalSourceUrls':['https://download.geofabrik.de/europe/hungary-261112.osm.pbf']+[pts[n]['sourceId'].replace('osm:node:','https://www.openstreetmap.org/node/') for n in names if n in pts],'approximationNotes':context+' Coarse manually interpreted search footprint only; inferred internal divisions and closing joins are not official surveyed boundaries. No circle or fixed-radius boundary.','sourceKind':'road_landuse_supported_neighbourhood_estimate','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','sourcePoint':pts.get(name,{}).get('coordinates'),'evidenceFile':'context-evidence.json',**extra}
 features.append({'type':'Feature','properties':prop,'geometry':mapping(g)})
 review.append({'name':name,'areaSquareMetres':round(metric.area),'ownPointInside':True,'actualIntersectingContextWayCount':len(nearby),'intersectingContextWays':nearby})
for t in spec['traces']:
 conf=spec['sourceImages'][t['image']];b=conf['bbox'];w,h=conf['width'],conf['height']
 cs=[(b[0]+x/w*(b[2]-b[0]),b[3]-y/h*(b[3]-b[1])) for x,y in t['vertices']]
 g=Polygon(cs)
 if t.get('clipAllotments'):g=g.intersection(shape(areaById[228357127]['geometry']))
 put(t['name'],g,t['context'],{'sourceContextImage':'context-'+t['image']+'.png','manualPixelTraceFile':'manual-traces.json','actualAllotmentContourWay':228357127 if t.get('clipAllotments')else None})
t=spec['industrialEstimate'];g=unary_union([shape(areaById[t['actualIndustrialWay']]['geometry']),Polygon(t['southernApproximateVerticesWgs84'])]);put(t['name'],g,t['context'],{'aliases':t['aliases'],'actualIndustrialContourWay':t['actualIndustrialWay'],'aliasEvidenceFile':'municipal-name-facts.json','municipalAliasSourceUrl':'https://miskolc.hu/sites/default/files/aktualitas/csatolmanyok/2024-09/megalapozo_vizsgalat_miskolc_mjv_its.pdf','municipalAliasSourcePage':41})
(HERE/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'context-evidence.json').write_text(json.dumps({'scope':'Technical context presence and own-point consistency only, not geographic boundary accuracy proof.','features':review},ensure_ascii=False,indent=2)+'\n')
summary={'featureCount':len(features),'municipality':'Miskolc','pointOnlyNamesRepresented':18,'aliasesAvoidingDuplicateGeometry':['Miskolc Déli Ipari park'],'sourceContextLineCount':len(lines),'sourceContextAreaCount':len(areas),'allValid':True,'allOwnPointsInside':True,'noCircleFallback':True,'officialGeographicAccuracyEstablished':False,'unlocatedNamesNotInvented':[f['name']for f in targets if not f['pointCandidates']],'names':[f['properties']['name']for f in features]}
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
