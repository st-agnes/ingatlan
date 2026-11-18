#!/usr/bin/env python3
"""Offline, evidence-informed ITS quarter traces using frozen OSM physical-map inputs."""
from pathlib import Path
import json,hashlib,unicodedata,re
from shapely.geometry import shape,Polygon,mapping
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;URL='https://www.kisvarda.hu/wp-content/uploads/2025/03/ITS__Kisvarda.pdf';FW=Transformer.from_crs(4326,23700,always_xy=True).transform
HASH='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def read(n):return json.loads((P/n).read_text())
def write(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def norm(n):
 s=''.join(c for c in unicodedata.normalize('NFD',n.lower()) if not unicodedata.combining(c));s=re.sub(r'^(ii\.?\s*)','',s);s=s.replace('liptai','liptay').replace('halassy','halasy').replace('jekei','jeki').replace('móser','mozer').replace('moser','mozer');s=s.replace('csokonai vitez mihaly','csokonai').replace('széchenyi istvan','szechenyi').replace('szechenyi istvan','szechenyi').replace('rakoczi ferenc','rakoczi');s=re.split(r'\butca\b|\butja\b|\but\b|\bter\b|\btere\b|:',s)[0];return ''.join(c for c in s if c.isalnum())
parent=shape(read('source-municipality.geojson')['features'][0]['geometry']);lines=read('source-lines.geojson')['features'];defs=read('source-boundary-definitions.json')['definitions'];definitions={r['name']:r for r in defs};features=[];checks=[]
for r in read('selection.json')['selected']:
 name=r['name'];g=Polygon(r['coordinates']);assert g.is_valid and not g.is_empty,name
 clipped=False
 if not parent.covers(g):g=g.intersection(parent);clipped=True
 assert g.is_valid and not g.is_empty and g.geom_type in {'Polygon','MultiPolygon'},name
 wanted={norm(n) for n in definitions[name]['boundaryElementsInSourceOrder']};matched=[]
 for f in lines:
  p=f['properties'];t=p['tags'];sg=shape(f['geometry'])
  if (norm(p.get('name') or '') in wanted or t.get('railway')=='rail') and transform(FW,sg).distance(transform(FW,g))<150:matched.append(f)
 p={'name':name,'municipality':'Kisvárda','municipalityId':'city:Kisvárda','method':'text_boundary_physical_map_trace_estimate','estimated':True,'lowConfidence':True,'qualityScore':20,'candidateBoundaryKind':'planning_unit','sourceYear':2015,'sourcePdfPages':[20,21,22,44],'sourceUrl':URL,'supportingUrls':[URL]+[f['properties']['sourceUrl'] for f in matched],'approximationNote':r['approximationNote'],'boundaryElementsInSourceOrder':definitions[name]['boundaryElementsInSourceOrder'],'sourceWayIds':[f['id'] for f in matched],'source':{'provider':'municipal-ITS-street-definition-with-OSM-map-trace','municipalSourceUrl':URL,'boundaryDefinitionPath':'data/neighborhoods/expansion-20261115-round3/kisvarda/source-boundary-definitions.json','sourceLinesPath':'data/neighborhoods/expansion-20261115-round3/kisvarda/source-lines.geojson','pbfSha256':HASH,'license':'ODbL-1.0 for OSM physical-map inputs','attribution':'© OpenStreetMap contributors'},'approximateAreaSquareMetres':round(transform(FW,g).area,1),'sourceMunicipalityClipped':clipped,'pointRadiusFallback':False,'legalAdministrativeBoundary':False}
 features.append({'type':'Feature','id':'kisvarda-its2015-estimate:'+name,'properties':p,'geometry':mapping(g)});checks.append({'name':name,'valid':True,'municipalityContained':parent.covers(g),'areaSquareMetres':p['approximateAreaSquareMetres'],'matchedSourceWays':len(matched)})
assert len({f['properties']['name'] for f in features})==len(features)
write('features.geojson',{'type':'FeatureCollection','features':features});write('center-features.geojson',{'type':'FeatureCollection','features':[f for f in features if f['properties']['name']=='Városközpont']})
missing=[r['name'] for r in defs if r['name'] not in {f['properties']['name'] for f in features}]
summary={'featureCount':len(features),'municipality':'Kisvárda','names':[f['properties']['name'] for f in features],'allEstimated':True,'allLowConfidence':True,'sourceReferenceCount':6,'unresolvedNames':missing,'sourceLines':len(lines),'sourceClosedLanduseWays':len(read('source-areas.geojson')['features']),'validPolygonOrMultiPolygonCount':len(features),'municipalityContainedCount':sum(r['municipalityContained'] for r in checks),'circleBufferRectangleVoronoiHullConstructed':0,'completeCityCoverageEstablished':False,'sourceYear':2015,'sourceUploadedYear':2025,'featuresSha256':hashlib.sha256((P/'features.geojson').read_bytes()).hexdigest(),'caveat':'Functional/geographic ITS units, explicitly without legal/administrative status in source. Whole local street-area estimates, not surveyed frontage offsets or native published quarter polygons.'}
write('summary.json',summary);write('validation.json',{'featureCount':len(features),'valid':True,'checks':checks});write('unresolved.json',{'unresolvedNames':missing,'limitations':['Exact outer-side property/frontage offsets in the city-center definition','Changes to roads and development since the 2010 IVS/2015 ITS','No administrative or cadastral boundary status','Source street lists do not form unambiguous closed rings in the current map'],'completeCityCoverageEstablished':False});print(json.dumps(summary,ensure_ascii=False))
