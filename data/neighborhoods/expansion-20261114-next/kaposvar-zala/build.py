#!/usr/bin/env python3
"""Quick registered municipal-map outlines and explicitly inferred fine grid areas."""
from pathlib import Path
import json,hashlib
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,box,shape,mapping,MultiPolygon
from shapely.ops import transform
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
SOURCE=ROOT/'data/neighborhoods/sources/municipal-local-map-next'
doc=json.loads((HERE/'zala-traces.json').read_text());matrix=np.array(json.loads((SOURCE/'zalaegerszeg-registration.json').read_text())['matrixPixelToEov'])
projection=Transformer.from_crs(23700,4326,always_xy=True)
def geographic(x,y,z=None):
 return projection.transform(x*matrix[0,0]+y*matrix[1,0]+matrix[2,0],x*matrix[0,1]+y*matrix[1,1]+matrix[2,1])
def polygon_only(g):
 if g.geom_type in ['Polygon','MultiPolygon']:return g
 parts=[]
 for p in g.geoms:
  if p.geom_type=='Polygon':parts.append(p)
  elif p.geom_type=='MultiPolygon':parts+=list(p.geoms)
 return MultiPolygon(parts)
pixels={};features=[]
for spec in doc['areas']:
 if 'points' in spec:pixels[spec['name']]=Polygon(spec['points'])
 else:
  parent=pixels[spec['parent']];name=spec['name']
  limits={'Apátfa':box(-1,-1,290,3000),'Andráshida':box(290,-1,390,3000),'Gébárt':box(390,-1,3000,3000),'Kaszaháza':box(-1,755,3000,3000),'Pózva':box(1030,-1,3000,700)}
  pixels[name]=parent.intersection(limits[name])
 g=pixels[spec['name']];repaired=not g.is_valid
 if repaired:g=polygon_only(make_valid(g));pixels[spec['name']]=g
 g=transform(geographic,g)
 if not g.is_valid:g=polygon_only(make_valid(g));repaired=True
 assert g.is_valid and not g.is_empty
 note=doc['note']
 if spec['role']=='child':note+=' Fine child cut: '+spec['cut']+'.'
 elif spec['role']=='fine':note+=' Fine named part manually inferred from visible street/parcel-block edges and saved OSM label location; source does not print this fine boundary.'
 p={'name':spec['name'],'municipality':'Zalaegerszeg','method':'municipal_map_trace_estimate' if spec['role']=='parent' else 'map_parcel_grid_inferred_area','estimated':True,'sourceSubdivisionKind':spec['role'],'candidateBoundaryKind':'planning_unit' if spec['role']=='parent' else 'neighbourhood','sourceUrl':doc['sourceUrl'],'sourcePeriod':doc['sourcePeriod'],'sourcePage':12,'source':{'provider':'municipal-map-inference','url':doc['sourceUrl'],'path':doc['source'],'sha256':hashlib.sha256((ROOT/doc['source']).read_bytes()).hexdigest(),'registrationPath':str((SOURCE/'zalaegerszeg-registration.json').relative_to(ROOT))},'qualityScore':30 if spec['role']=='parent' else 20,'approximationNote':note,'absoluteAccuracyMetres':None,'topologyRepairApplied':repaired}
 features.append({'type':'Feature','id':'next-zala:'+spec['name'],'properties':p,'geometry':mapping(g)})
# Two actual source regions were formerly excluded solely by an overly strict JS hole check.
for f in json.loads((SOURCE/'zalaegerszeg-quarantine.geojson').read_text())['features']:
 g=shape(f['geometry']); repaired=not g.is_valid
 if repaired:g=polygon_only(make_valid(g))
 p={**f['properties'],'method':'municipal_source_map_polygon','estimated':True,'source':{'provider':'municipal-raster','url':doc['sourceUrl'],'path':str((SOURCE/'zalaegerszeg-quarantine.geojson').relative_to(ROOT))},'qualityScore':45,'approximationNote':'Existing registered source-area footprint adopted under relaxed policy; only structural geometry repair if required.','topologyRepairApplied':repaired}
 features.append({'type':'Feature','id':'next-zala:'+p['name'],'properties':p,'geometry':mapping(g)})
output={'type':'FeatureCollection','features':features};(HERE/'features.geojson').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'summary.json').write_text(json.dumps({'featureCount':len(features),'municipalities':{'Zalaegerszeg':len(features)},'radiusFallbackCount':0,'sourceReferencePeriod':doc['sourcePeriod'],'allStructurallyValid':True,'fineBoundaryStatus':'Explicit rough inference from visible map fabric and known label locations, not printed official fine borders.'},ensure_ascii=False,indent=2)+'\n')
print(len(features),'valid areas')
