#!/usr/bin/env python3
"""Offline, frozen Nyíregyháza physical-map traces and source-footprint associations."""
from pathlib import Path
import hashlib,json
from collections import Counter
from shapely.geometry import shape,mapping,Polygon
from shapely.ops import unary_union,transform
from pyproj import Transformer
OUT=Path(__file__).resolve().parent
FWD=Transformer.from_crs(4326,23700,always_xy=True).transform
URL='https://uj.nyiregyhaza.hu/lib/adattar/hatalyos/180516_2017_hr_31.pdf'
PBF_HASH='224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a'
def read(n):return json.loads((OUT/n).read_text())
def write(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
selection=read('selection.json');sources=read('source-landuse.geojson')['features'];byid={f['id']:f for f in sources};labels={f['properties']['name']:f for f in read('source-labels.geojson')['features']};roads=read('source-roads.geojson')['features'];parent=shape(read('source-municipality.geojson')['features'][0]['geometry'])
features=[]
for group,rows in selection.items():
 for row in rows:
  name=row['name'];label=labels.get(name);sourcefeatures=[byid['osm:way:'+str(i)] for i in row.get('ways',[])];supporting=list(row.get('supportingUrls',[]));sourceways=[]
  if group=='traces':
   geom=Polygon(row['coordinates']);method='manual_physical_map_trace_estimate';unmodified=False
  else:
   geom=unary_union([shape(f['geometry']) for f in sourcefeatures]);method='source_footprint_locality_association_estimate';unmodified=True
  for f in roads:
   if f['properties'].get('name') in row.get('roadNames',[]):sourceways.append(f['id']);supporting.append(f['properties']['source']['url'])
  supporting.extend(f['properties']['sourceUrl'] for f in sourcefeatures)
  if label:supporting.append(label['properties']['source']['url'])
  supporting.append(URL)
  sourceurl=sourcefeatures[0]['properties']['sourceUrl'] if sourcefeatures else label['properties']['source']['url']
  props={'name':name,'municipality':'Nyíregyháza','municipalityId':'city:Nyíregyháza','method':method,'estimated':True,'lowConfidence':True,'qualityScore':15,'semanticFootprint':True,'candidateBoundaryKind':'neighbourhood','pointRadiusFallback':False,'sourceGeometryUnmodified':unmodified,'partialSettlementFootprint':group=='ruralFootprints','sourceUrl':sourceurl,'supportingUrls':list(dict.fromkeys(supporting)),'approximationNote':row['note'],'sourceFootprintIds':[f['id'] for f in sourcefeatures],'sourceRoadIds':sourceways,'source':{'provider':'osm-physical-map-and-local-evidence','pbfSha256':PBF_HASH,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','sourceLandusePath':'data/neighborhoods/expansion-20261115/nyiregyhaza/source-landuse.geojson','selectionPath':'data/neighborhoods/expansion-20261115/nyiregyhaza/selection.json'},'approximateAreaSquareMetres':round(transform(FWD,geom).area,1)}
  if label:props['nameEvidence']=[{'name':name,'coordinates':label['geometry']['coordinates'],'sourceUrl':label['properties']['source']['url']}]
  if group=='ruralFootprints':props['approximationNote']+=' Source farmyard rings are unchanged; their union preserves separate islands. No circle, point buffer, Voronoi region or convex hull is used.'
  assert geom.is_valid and not geom.is_empty and geom.geom_type in {'Polygon','MultiPolygon'},name
  assert parent.covers(geom),name+' outside municipality'
  features.append({'type':'Feature','id':'nyiregyhaza-20261115:'+name,'properties':props,'geometry':mapping(geom)})
features.sort(key=lambda f:f['properties']['name'])
write('features.geojson',{'type':'FeatureCollection','features':features})
summary={'municipality':'Nyíregyháza','featureCount':len(features),'newPolygonNames':[f['properties']['name'] for f in features],'estimatedCount':len(features),'lowConfidenceCount':len(features),'methods':dict(Counter(f['properties']['method'] for f in features)),'unchangedSourceFootprintAssociations':7,'roughPhysicalMapTraces':6,'partialRuralSettlementFootprints':5,'missingNamesBaseline':14,'sourceVerifiedAliasCount':1,'remainingUnresolvedNames':[],'circleBufferVoronoiHullCount':0,'completeCityCoverageEstablished':False,'sourcePbfSha256':PBF_HASH,'validation':{'validPolygonOrMultiPolygonCount':len(features),'containedInSourceMunicipalityCount':len(features),'nonEmptyCount':len(features),'duplicateMunicipalityNameCount':0},'caveat':'The14 baseline name gaps are covered by13 low-confidence polygon associations/traces and1 verified alias. This is name-list completion, not complete spatial or authoritative neighbourhood coverage.'}
write('summary.json',summary)
write('validation.json',summary['validation'])
write('unresolved.json',{'unresolvedNames':[],'coverageNotEstablished':['Full conventional extent of dispersed rural districts','Cadastral/official borders of inferred estates','Whether close Kerti lak and Tópart labels are nested or historical alternatives'],'excludedApproaches':['Whole combined Kertváros/Salamonbokor/Szabadságbokor copied under child names','Whole22.46km² city residential footprint assigned to a small estate','Circles, point buffers, Voronoi and convex hulls']})
print(json.dumps(summary,ensure_ascii=False))
