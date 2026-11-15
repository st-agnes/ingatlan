#!/usr/bin/env python3
"""Coarse old-town extent from native cached urban outline and explicit cut estimates."""
from pathlib import Path
import json,hashlib
from shapely.geometry import shape,Point,LineString,Polygon,mapping
from shapely.ops import split,transform
from pyproj import Transformer
H=Path(__file__).resolve().parent
URL='https://tokaj.hu/images/uploads/2017/03/TOKAJ_ITS_Megalapozo_vegleges_egyeztetes_utan_20220617.pdf'
point=Point(21.409731,48.1243666)
source=json.loads((H/'source-contexts.geojson').read_text())['features'][0];native=shape(source['geometry']);g=next(p for p in native.geoms if p.covers(point))
roads=json.loads((H/'source-roads.geojson').read_text())['features'];bridge=next(f for f in roads if f['properties'].get('name')=='Erzsébet királyné híd');bridgecs=bridge['geometry']['coordinates']
if bridgecs[0][0]>bridgecs[-1][0]:bridgecs=bridgecs[::-1]
# Source-described38/bridge southern limit; only the short landward join is inferred.
south=LineString([[21.403,bridgecs[0][1]],*bridgecs])
# Approximate transition just north of the Váradi/Bethlen historical entry; beyond it the
# raw residential object continues into the long modern Bodrogkeresztúri ribbon.
north=LineString([[21.400,48.1326],[21.4065,48.1318],[21.416,48.1316]])
for cut in [north,south]:
 candidates=[p for p in split(g,cut).geoms if p.geom_type=='Polygon'and p.covers(point)];assert len(candidates)==1;g=candidates[0]
filled=len(g.interiors);g=Polygon(g.exterior);assert g.is_valid and g.covers(point)
municipality=shape(json.loads((H/'source-municipality.geojson').read_text())['features'][0]['geometry']);fraction=g.intersection(municipality).area/g.area;assert fraction>.999
assert g.covers(Point(21.405327,48.1302226))and g.covers(Point(21.4095666,48.1290398))
assert not g.covers(Point(21.4126943,48.1106125))
t=Transformer.from_crs(4326,23700,always_xy=True);area=transform(t.transform,g).area
note='Low-confidence whole Óváros/central-old-town neighbourhood estimate. Tokaj municipal2022ITS text states that Óváros includes the medieval core, former Bányászfalu, Halászfalu and the newer central urban part; the38main-road/bridge setting supplies its southern context. The exterior primarily retains the literal cached OSM residential-area outline along the hill foot and river-side built-up land. A short inferred landward extension of the actual Erzsébet királyné bridge alignment separates the southern corridor; a coarse inferred northern cap near the Váradi/Bethlen entry separates the long newer Bodrogkeresztúri ribbon. Both caps are estimates, not native municipal PDF lines. Parent-child overlap with Bányászfalu/Halászfalu is deliberate; no same-identity alias is asserted. Internal urban gaps are filled for a land-inclusive search area. Not an official/cadastral boundary and no point radius, circle or point-only rectangle.'
p={'name':'Óváros','municipality':'Tokaj','method':'primary_municipal_oldtown_description_native_urban_outline_with_inferred_entry_cuts_estimate','estimated':True,'confidence':'low','qualityScore':20,'priority':30,'sourceUrl':URL,'sourceYear':2022,'sourceSection':'A.) Központi városrész – Tokaj magterület','nativeUrbanSourceUrl':source['properties']['source']['url'],'nativeUrbanSourceObject':'osm:relation:13573620','sourceContextFile':'source-contexts.geojson','sourceRoadFile':'source-roads.geojson','sourceTraceFile':'source-cuts.geojson','sourceNamePoint':{'sourceUrl':'https://www.openstreetmap.org/node/12993740315','coordinates':[21.409731,48.1243666]},'approximationNote':note,'radiusFallback':False,'semanticFootprint':False,'partialBuildingOrWaterFootprint':False,'nativeMunicipalPdfGeometryClaimed':False,'sourceSnapshot':'2026-11-12T21:23:05Z','license':'ODbL-1.0 for OSM geometry; municipal text contextual evidence','attribution':'Tokaj municipal ITS; © OpenStreetMap contributors'}
(H/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':p,'geometry':mapping(g)}]},ensure_ascii=False,separators=(',',':'))+'\n')
(H/'source-cuts.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'role':'south38road/bridge context','actualBridgeWayId':bridge['properties']['source']['osmId'],'landwardExtensionInferred':True},'geometry':mapping(south)},{'type':'Feature','properties':{'role':'northern historical-entry cut','inferred':True},'geometry':mapping(north)}]},ensure_ascii=False,separators=(',',':'))+'\n')
summary={'featureCount':1,'municipality':'Tokaj','name':'Óváros','areaKm2':round(area/1e6,6),'geometryValid':True,'knownOvarosPointInside':True,'knownBanyaszfaluPointInside':True,'knownHalaszfaluPointInside':True,'southernKistokajPointExcluded':True,'fractionWithinMunicipality':round(fraction,7),'outerRingVertexCount':len(g.exterior.coords),'urbanHoleCountFilled':filled,'estimatedEntryCaps':2,'pointRadiusCount':0,'nativeMunicipalPdfGeometryClaimed':False,'independentCadastralAccuracyEstablished':False,'completeCityCoverageEstablished':False,'outputSha256':hashlib.sha256((H/'features.geojson').read_bytes()).hexdigest()}
(H/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(H/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
