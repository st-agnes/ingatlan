#!/usr/bin/env python3
"""Rebuild the Sandipuszta occupied-locality estimate from archived source polygons."""
from pathlib import Path
import json,gzip,hashlib
from shapely.geometry import shape,mapping,Point
from shapely.ops import unary_union,transform
from pyproj import Transformer,Geod
P=Path(__file__).resolve().parent
r=json.load(open(P/'recipe.json'))
with gzip.open(P/'source-inputs/selected-source-objects.geojson.gz','rt') as h:objects={f['id']:f for f in json.load(h)['features']}
to=Transformer.from_crs(4326,23700,always_xy=True).transform;back=Transformer.from_crs(23700,4326,always_xy=True).transform
parts=[shape(objects[i]['geometry']) for i in r['buildingIds']]
assert len(parts)==30 and all(g.geom_type=='Polygon' for g in parts)
g=transform(back,transform(to,unary_union(parts)).convex_hull.buffer(r['yardAllowanceM'],join_style=2))
municipality=unary_union([shape(f['geometry']) for f in json.load(open(P/'source-inputs/gyugy-municipality.geojson'))['features']])
g=g.intersection(municipality)
assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon']
assert g.covers(Point(r['sourceNameAssociationPoint']))
props={k:r[k] for k in ['municipality','name','sourceUrl','supportingUrls','approximationNote','partialFootprint']}
props.update(method='source_building_cluster_occupied_locality_envelope_estimate',estimated=True,lowConfidence=True,confidence='low',boundaryKind='neighbourhood',usableForAddressAssignment=False,sourceObjectIds=r['buildingIds'],sourcePeriod='OSM snapshot 2026-11-12; historical academic name records 1862–1974',license='ODbL-1.0',attribution='© OpenStreetMap contributors; Hungarian Digital Place-name Register',areaM2=round(abs(Geod(ellps='WGS84').geometry_area_perimeter(g)[0])),evidenceFiles=['evidence/sandipuszta-academic-place-definitions.json','evidence/current-address-location-search.json','source-inputs/selected-source-objects.geojson.gz'])
f={'type':'Feature','id':'estimated:round4:shard0:residual:sandipuszta','properties':props,'geometry':mapping(g)}
(P/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[f]},ensure_ascii=False,indent=2)+'\n')
proof={'featureCount':1,'allValid':True,'sourceBuildingCount':len(parts),'sourcePointUsedOnlyForNameAssociation':True,'pointBuffersCreated':0,'trackOnlyHullsCreated':0,'municipalityClipped':True,'areaM2':props['areaM2'],'featureSha256':hashlib.sha256((P/'features.geojson').read_bytes()).hexdigest(),'inputSha256':{str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [P/'recipe.json',*sorted((P/'source-inputs').iterdir())]}}
(P/'build-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(proof,ensure_ascii=False,indent=2))
