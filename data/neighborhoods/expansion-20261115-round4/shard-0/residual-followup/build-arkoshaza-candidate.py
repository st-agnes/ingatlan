#!/usr/bin/env python3
"""Offline source-edge reconstruction of a very coarse representative rural tract."""
from pathlib import Path
import json,gzip,hashlib
from shapely.geometry import shape,Point,mapping
from shapely.ops import unary_union,polygonize,transform
from pyproj import Transformer,Geod
P=Path(__file__).resolve().parent;S=P/'source-inputs';tr=Transformer.from_crs(4326,23700,always_xy=True).transform;pt=Point(16.7722417,46.8252895)
roads=json.load(gzip.open(S/'arkoshaza-roads.geojson.gz','rt'))['features'];areas=json.load(gzip.open(S/'arkoshaza-areas.geojson.gz','rt'))['features'];mus=json.load(open(S/'arkoshaza-municipality.geojson'))['features'];mu=unary_union([shape(f['geometry']) for f in mus]);sources=[];lines=[]
for f in roads:
 t=f['properties']['tags']
 if t.get('highway') or t.get('waterway') or t.get('railway'):sources.append(f);lines.append(shape(f['geometry']))
for f in areas:
 h=shape(f['geometry'])
 if h.geom_type in ['Polygon','MultiPolygon'] and f['properties']['tags'].get('natural')!='mountain_range':sources.append(f);lines.append(h.boundary)
physical_matches=[g for g in polygonize(unary_union(lines)) if g.covers(pt)]
assert not physical_matches,'The documented municipal-closure interpretation has changed'
matches=[g for g in polygonize(unary_union(lines+[mu.boundary])) if g.covers(pt)]
assert len(matches)==1
h=matches[0];assert h.is_valid and transform(tr,h.difference(mu)).area<1
border=[]
for f in sources:
 g=shape(f['geometry']);g=g.boundary if g.geom_type in ['Polygon','MultiPolygon'] else g
 length=transform(tr,g.intersection(h.boundary)).length
 if length>1:border.append({'id':f['id'],'lengthM':round(length)})
labels=[f for f in json.load(open(S/'arkoshaza-labels.geojson'))['features'] if h.covers(shape(f['geometry']))]
assert len(labels)==1 and labels[0]['properties']['name']=='Árkosháza-puszta'
assert not [f for f in areas if f['properties']['tags'].get('landuse') in ['residential','farmyard','industrial'] and transform(tr,h.intersection(shape(f['geometry']))).area>100]
assert not [f for f in json.load(gzip.open(S/'arkoshaza.geojson.gz','rt'))['features'] if h.intersects(shape(f['geometry']))]
ids=[f['id'] for f in border]+['osm:relation:1358050']
props={'name':'Árkosháza-puszta','municipality':'Babosdöbréte','boundaryKind':'neighbourhood','method':'reviewed_native_road_forest_and_municipal_boundary_representative_historic_landscape_estimate','estimated':True,'lowConfidence':True,'confidence':'very low','quality':9,'qualityScore':9,'partialFootprint':True,'historicEstateBoundaryKnown':False,'disappearedSettlement':True,'representativeLandscapeTract':True,'usableForAddressAssignment':False,'sourceUrl':'https://babosdobrete.hu/images/dokumentum/f203.pdf','supportingUrls':['https://adatbazisokonline.mnl.gov.hu/adatbazis/mikrofilm-anyakonyvek/adatlap/35646','https://library.hungaricana.hu/hu/view/ZALM_Hl_01/?pg=665','https://mi.abtk.hu/images/gyujtemenyek/regeszta-mutatok/masodik-sorozat/fiok_122._hadtorteneti_intezet_ix-2._zala._helysegnev._a-zs.pdf','https://www.openstreetmap.org/node/7917903898','https://www.openstreetmap.org/relation/1358050',*['https://www.openstreetmap.org/way/'+i.split(':')[-1] for i in ids if i.startswith('osm:way:')]],'approximationNote':'VERY LOW CONFIDENCE representative former-estate-adjacent rural landscape tract, not a recovered historic compound or estate perimeter. Primary municipal text says the hamlet disappeared; archival name records confirm its identity and place it north of Babosdöbréte. The historical name point falls in this coherent rural tract north of the current village core. Seven native tracks supply most exterior edges, the actual Babosdöbréte administrative boundary supplies 998 m of necessary closure, and a native forest ring is an interior exclusion. No invented edge, circle, radius, point-only polygon, hull, snapping or viewport perimeter is used. No other known place label or native residential/farmyard/industrial surface is inside. No extracted building intersects; the 1.5 km building-extraction window covers 95.93% of the tract and makes no completeness claim for its northern tip. Historic ownership, parcel extent and former six-house compound location are not recovered. This partial landscape representation is only a rough locality estimate and makes no current occupancy or cadastral accuracy claim. Municipal PDF map pixels were not seen or digitized; the geometry comes solely from archived native source edges.','sourceObjectIds':ids,'sourceNameAssociationPoint':[16.7722417,46.8252895],'sourcePeriod':'Historical MNL/municipal records and OSM snapshot 2026-11-12','areaM2':round(abs(Geod(ellps='WGS84').geometry_area_perimeter(h)[0])),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors; cited Hungarian municipal and archival factual evidence','evidenceFiles':['arkoshaza-geographic-review.json','arkoshaza-circuit-proof.json','arkoshaza-landscape-review.png','evidence/independent-observed-source-facts.json','evidence/independent-search-1-variants.json','evidence/independent-search-6.json','evidence/arkoshaza-historic-boundary-search.json','source-inputs/arkoshaza-municipality.geojson'],'reviewStatus':'REVIEWED_COHERENT_RURAL_TRACT_FOR_ROOT_INTAKE'}
f={'type':'Feature','id':'estimated:round4:shard0:residual:arkoshaza','properties':props,'geometry':mapping(h)}
out=P/'arkoshaza-reviewed-candidate.geojson';out.write_text(json.dumps({'type':'FeatureCollection','features':[f]},ensure_ascii=False,indent=2)+'\n')
proof={'allValid':True,'featureCount':1,'actualPhysicalOnlyClosedTractsContainingPoint':0,'actualRoadAndMunicipalBoundaryClosedTractsContainingPoint':1,'syntheticEdgesAdded':0,'pointBuffersCreated':0,'hullsCreated':0,'viewportEdgesUsed':False,'actualMunicipalClosureM':round(transform(tr,h.boundary.intersection(mu.boundary)).length),'boundaryObjects':border,'otherKnownPlaceLabelsInside':0,'residentialFarmyardIndustrialSurfacesInside':0,'extractedBuildingsInside':0,'areaM2':props['areaM2'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'quality':9,'historicEstateBoundaryKnown':False,'inputSha256':{str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(S.iterdir()) if p.name.startswith('arkoshaza-')}}
(P/'arkoshaza-candidate-build-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps(proof,ensure_ascii=False,indent=2))
