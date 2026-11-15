#!/usr/bin/env python3
"""Build selected four-municipality source polygons and map-based estimates offline."""
from pathlib import Path
import json,hashlib
from collections import Counter
from shapely.geometry import shape,mapping,Polygon,Point
from shapely.ops import transform
from pyproj import Transformer
P=Path(__file__).resolve().parent;FW=Transformer.from_crs(4326,23700,always_xy=True).transform
HASH='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def read(n):return json.loads((P/n).read_text())
def write(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
areas={f['id']:f for f in read('source-areas.geojson')['features']};lines={f['id']:f for f in read('source-lines.geojson')['features']};parents={f['properties']['name']:shape(f['geometry']) for f in read('source-municipalities.geojson')['features']};cells={f['id']:f for f in read('candidate-cells.geojson')['features']};labels={(f['properties']['municipality'],f['properties']['name']):f for f in read('source-labels.geojson')['features']};rows=read('selection.json')['selected'];features=[];audit=[]
urls={'Hosszúpályi':['https://hosszupalyi.hu/telepulesrendezesi-terv/','https://osm-gimmisn.vmiklos.hu/osm/streets/hosszupalyi/view-result'],'Monostorpályi':['https://monostorpalyi.hu/szabalyzatok-koncepciok','https://utcak-magyarorszag.openalfa.com/monostorpalyi'],'Mátészalka':['https://www.mateszalka.hu/modul/file_browser/upload/hirek/telepulesrend/112-mateszalka-szerkezeti-terv-leiras.pdf','https://helyiingatlanos.hu/mateszalka'],'Orosháza':['https://oroshaza.hu/wp-content/uploads/dokumentumtar/egyeb_informaciok_dokumentumok/2017es_ev/Orosh%C3%A1za%20TAK.pdf']}
for row in rows:
 city,name=row['municipality'],row['name'];label=labels[city,name];support=[label['properties']['source']['url']]+urls[city]+row.get('supportingUrls',[]);sourceids=[];unmodified=False
 if 'candidateId' in row:
  f=cells[row['candidateId']];g=shape(f['geometry']);method='physical_barrier_cell_estimate';sourceids=f['properties']['sourceLineIds'];support += [lines[i]['properties']['sourceUrl'] for i in sourceids];sourceurl=label['properties']['source']['url'];quality=10
 elif 'sourceAreaId' in row:
  f=areas[row['sourceAreaId']];g=shape(f['geometry']);method='source_footprint_locality_association_estimate';sourceids=[f['id']];sourceurl=f['properties']['sourceUrl'];support.append(sourceurl);quality=20;unmodified=True
  if 'sourceComponent' in row:g=list(g.geoms)[row['sourceComponent']]
 else:
  g=Polygon(row['coordinates']);method='manual_physical_map_trace_estimate';sourceurl=(row.get('supportingUrls') or [label['properties']['source']['url']])[0];quality=15
  for i,f in lines.items():
   if city in f['properties']['municipalities'] and f['properties']['name'] in row.get('roadNames',[]) and transform(FW,shape(f['geometry'])).distance(transform(FW,g))<250:sourceids.append(i);support.append(f['properties']['sourceUrl'])
 assert g.is_valid and not g.is_empty,(city,name,'invalid input')
 clipped=False
 if not parents[city].covers(g):
  g=g.intersection(parents[city]);clipped=True;unmodified=False
 assert g.is_valid and not g.is_empty and g.geom_type in {'Polygon','MultiPolygon'},(city,name,'invalid output')
 area=round(transform(FW,g).area,1);assert area>1000,(city,name,area)
 note=row['approximationNote']
 if clipped:note+=' Source municipality boundary clips the outer estimate; this does not establish a surveyed quarter border.'
 p={'name':name,'municipality':city,'municipalityId':'city:'+city,'method':method,'estimated':True,'lowConfidence':True,'qualityScore':quality,'candidateBoundaryKind':'neighbourhood','semanticFootprint':True,'sourceGeometryUnmodified':unmodified,'sourceUrl':sourceurl,'supportingUrls':list(dict.fromkeys(support)),'approximationNote':note,'sourceBoundaryIds':sourceids,'source':{'provider':'openstreetmap-physical-map-with-local-source-review','pbfSha256':HASH,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','sourceAreaPath':'data/neighborhoods/expansion-20261115-round2/east-small/source-areas.geojson','sourceLinePath':'data/neighborhoods/expansion-20261115-round2/east-small/source-lines.geojson'},'nameEvidence':[{'name':name,'coordinates':label['geometry']['coordinates'],'sourceUrl':label['properties']['source']['url']}],'approximateAreaSquareMetres':area,'pointRadiusFallback':False,'municipalityClipped':clipped}
 if 'sourceComponent' in row:p['sourceComponent']=row['sourceComponent']
 if 'sourceAreaId' in row:p['sourceAreaTags']=areas[row['sourceAreaId']]['properties']['tags']
 features.append({'type':'Feature','id':'east-small-round2:'+city+':'+name,'properties':p,'geometry':mapping(g)});audit.append({'municipality':city,'name':name,'valid':True,'areaSquareMetres':area,'sourceMunicipalityContains':parents[city].covers(g),'namePointInside':g.covers(shape(label['geometry'])),'method':method})
features.sort(key=lambda f:(f['properties']['municipality'],f['properties']['name']));assert len({(f['properties']['municipality'],f['properties']['name']) for f in features})==len(features)
write('features.geojson',{'type':'FeatureCollection','features':features})
new={(f['properties']['municipality'],f['properties']['name']) for f in features};missing=[{'municipality':t['municipality'],'name':t['name']} for t in read('targets.json') if (t['municipality'],t['name']) not in new]
summary={'featureCount':len(features),'municipalityCount':len(parents),'municipalities':dict(Counter(f['properties']['municipality'] for f in features)),'methods':dict(Counter(f['properties']['method'] for f in features)),'estimatedCount':len(features),'lowConfidenceCount':len(features),'sourceAreaCount':len(areas),'sourceLineCount':len(lines),'baselineTargetCount':len(read('targets.json')),'unresolvedTargetCount':len(missing),'circleRectangleVoronoiHullGenerated':0,'completeCityCoverageEstablished':False,'featuresSha256':hashlib.sha256((P/'features.geojson').read_bytes()).hexdigest(),'limitation':'Real mapped parcels, road/track cells and rough traced locality areas; name association and local extent remain estimated. Garden cells and estate cores can cover part of a wider historical name.'}
write('summary.json',summary);write('validation.json',{'featureCount':len(features),'validPolygonOrMultiPolygonCount':len(features),'municipalityContainedCount':sum(r['sourceMunicipalityContains'] for r in audit),'duplicateNamePairs':0,'features':audit});write('unresolved.json',{'unresolvedNames':missing,'scopeLimitations':['Historical garden and farmstead extents outside selected physical footprints','Official estate borders where only street/landuse context is available','Cadastral accuracy of manual source-map traces'],'completeCityCoverageEstablished':False});write('alias-proposals.json',{'proposals':[],'note':'No synonymy inferred from proximity, overlap or shared parent polygons.'})
print(json.dumps(summary,ensure_ascii=False))
