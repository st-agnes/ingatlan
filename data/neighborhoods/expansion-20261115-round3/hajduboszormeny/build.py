#!/usr/bin/env python3
"""Offline municipal-text-defined whole centre from literal archived road circuits."""
from pathlib import Path
import json,hashlib
from shapely.geometry import shape,Point,Polygon,mapping
from shapely.ops import unary_union,polygonize,transform
from pyproj import Transformer
H=Path(__file__).resolve().parent
facts=json.loads((H/'source-definition.json').read_text());fs=json.loads((H/'source-roads.geojson').read_text())['features']
names=set(facts['primarySource']['boundaryRoadsInSourceOrder'])
for variants in facts['osmStreetLabelVariants'].values():names.update(variants)
selected=[]
for f in fs:
 p=f['properties'];name=p.get('name')or'';tags=p['source']['tags']
 if name in names or(not name and tags.get('highway')not in ['footway','path','steps','cycleway']):selected.append(f)
linework=unary_union([shape(f['geometry'])for f in selected]);cells=list(polygonize(linework));point=Point(facts['sourceNamePoint']['coordinates']);matches=[g for g in cells if g.covers(point)]
assert len(matches)==1
raw=matches[0];g=Polygon(raw.exterior)
assert g.is_valid and g.covers(point)and g.area>0
# Interior road/parking loops are neighbourhood land, not geographic exclusions.
assert g.boundary.difference(linework).length<1e-10
boundary_sources=[]
for f in selected:
 line=shape(f['geometry']);overlap=g.boundary.intersection(line).length
 if overlap>1e-10:boundary_sources.append(f)
actual_names={f['properties'].get('name')for f in boundary_sources if f['properties'].get('name')}
for name in facts['primarySource']['boundaryRoadsInSourceOrder']:
 assert name in actual_names or any(v in actual_names for v in facts['osmStreetLabelVariants'].get(name,[])),name
municipality=shape(json.loads((H/'source-municipality.geojson').read_text())['features'][0]['geometry']);inside=g.intersection(municipality).area/g.area;assert inside>.999999
ll_to_eov=Transformer.from_crs(4326,23700,always_xy=True);area=transform(ll_to_eov.transform,g).area
note='Belváros is estimated as the whole central Kiskörút unit. Municipal ordinance25/2025 §4(6) explicitly supplies its nine boundary streets, and townscape ordinance35/2019 §15(2) distinguishes Belváros from the area outside the Kiskörút. The polygon follows the outer closed circuit of the literal archived OSM road centre-lines plus an actual short unnamed roundabout connection; current OSM labels the relevant Újfehértói segment út instead of the ordinance utca. No synthetic closure, snapping, point radius or circle was introduced. Four internal road/parking loops were filled because their enclosed land belongs inside the centre. Street centre-lines are an approximate neighbourhood boundary; whole front parcels and every possible broader historical use of Belváros are not legally certified. Estimated/low-confidence semantics retained despite exact reuse of source road geometry.'
p={'name':'Belváros','municipality':'Hajdúböszörmény','method':'municipal_street_definition_actual_osm_outer_circuit_neighbourhood_estimate','estimated':True,'confidence':'low','qualityScore':30,'priority':30,'sourceUrl':facts['primarySource']['url'],'sourceYear':2025,'sourceSection':facts['primarySource']['section'],'sourceContextUrl':facts['semanticSource']['url'],'sourceContextSection':facts['semanticSource']['section'],'sourceDefinitionFile':'source-definition.json','sourceRoadFile':'source-roads.geojson','boundarySourceFile':'boundary-source-ways.geojson','sourceRoadIds':[f['properties']['source']['osmId']for f in boundary_sources],'sourceRoadNames':sorted(actual_names),'sourceNamePoint':facts['sourceNamePoint'],'approximationNote':note,'radiusFallback':False,'semanticFootprint':False,'partialBuildingOrWaterFootprint':False,'sourceSnapshot':'2026-11-12T21:23:05Z','license':'ODbL-1.0 for OSM geometry; public municipal legal-text evidence','attribution':'Hajdúböszörmény municipal ordinances; © OpenStreetMap contributors'}
(H/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':p,'geometry':mapping(g)}]},ensure_ascii=False,separators=(',',':'))+'\n')
(H/'boundary-source-ways.geojson').write_text(json.dumps({'type':'FeatureCollection','features':boundary_sources},ensure_ascii=False,separators=(',',':'))+'\n')
(H/'boundary-ring.json').write_text(json.dumps({'crs':'EPSG:4326','ring':[list(xy)for xy in g.exterior.coords],'construction':'Actual noded source road circuit; no new outer closing edge.','internalRoadLoopHoleCountFilled':len(raw.interiors)},ensure_ascii=False,indent=2)+'\n')
summary={'featureCount':1,'municipality':'Hajdúböszörmény','name':'Belváros','areaKm2':round(area/1e6,6),'outerRingVertexCount':len(g.exterior.coords),'sourceBoundaryWays':len(boundary_sources),'sourceNamedBoundaryRoadCount':len(actual_names),'all9MunicipalBoundaryRoadsRepresented':True,'internalRoadLoopHolesFilled':len(raw.interiors),'geometryValid':True,'knownNamePointInside':True,'fractionWithinMunicipality':round(inside,8),'allOuterEdgesOnActualSourceRoads':True,'syntheticOuterClosingEdges':0,'circleOrPointRadiusCount':0,'sourceMapGeoreferenceNeeded':False,'independentCadastralAccuracyEstablished':False,'completeCityCoverageEstablished':False,'outputSha256':hashlib.sha256((H/'features.geojson').read_bytes()).hexdigest()}
(H/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(H/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
