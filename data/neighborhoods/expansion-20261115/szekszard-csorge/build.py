#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
from shapely.geometry import Polygon,shape,mapping
from shapely.ops import transform
from pyproj import Transformer
H=Path(__file__).resolve().parent
# Literal road/canal vertices plus openly inferred adjoining-land joins.
ring=[[18.7326056,46.34882],[18.7319642,46.3489039],[18.7317418,46.3489411],[18.7315667,46.3489865],[18.7311427,46.3492056],[18.7301254,46.3497984],[18.7317,46.3512],[18.7340,46.3522],[18.7373741,46.3535548],[18.7402,46.3537],[18.7437,46.3533],[18.7452024,46.3517339],[18.7439392,46.3518719],[18.7436474,46.35192],[18.7435588,46.3519217],[18.7434462,46.351891],[18.7432405,46.3503647],[18.7427277,46.3501637],[18.7419252,46.349157],[18.7415,46.3487],[18.7379,46.3483],[18.7344,46.3484]]
g=Polygon(ring);assert g.is_valid and g.area>0
fs=json.loads((H/'source-context.geojson').read_text())['features'];lake=shape(next(f['geometry']for f in fs if f['properties']['source']['osmId']==119046364 and f['geometry']['type']!='LineString'))
assert g.covers(lake)
to_eov=Transformer.from_crs(4326,23700,always_xy=True);area=transform(to_eov.transform,g).area;water=transform(to_eov.transform,lake).area
note='Coarse low-confidence Csörge-tó neighbourhood envelope including the literal lake, adjoining Nyámándpuszta-side land and the eastern Bogyiszlói út approach, so address matching is not restricted to water. The western edge retains actual Bogyiszlói út vertices near the Galamb utca junction; the eastern approach retains literal Bogyiszlói út road vertices, while Sárközi-összekötőcsatorna turns constrain the north/east/south setting. Joins across adjoining garden/field land are manually inferred. The boundary is not official, parcel-accurate or independently validated; overlaps with neighbouring industrial/rural areas are intentional. No circle, distance buffer or point-only rectangle was used. The earlier literal-lake polygon remains a source alternative.'
p={'name':'Csörge-tó','municipality':'Szekszárd','method':'manual_actual_road_canal_lake_adjoining_land_neighbourhood_estimate','estimated':True,'confidence':'low','qualityScore':20,'priority':30,'sourcePriority':30,'sourceKind':'manual_neighbourhood_estimate','semanticFootprint':False,'sourceUrl':'https://www.openstreetmap.org/way/119046364','sourceRoadAndWaterFile':'source-context.geojson','sourceAnchorFile':'source-anchors.json','sourceRoadIds':[206680745,228597416,161657556],'sourceWaterwayIds':[119046388,289551183,760119123],'approximationNote':note,'radiusFallback':False,'sourceSnapshot':'2026-11-12T21:23:05Z','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}
(H/'features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':p,'geometry':mapping(g)}]},ensure_ascii=False,separators=(',',':'))+'\n')
anchors=[]
for i,xy in enumerate(ring):
 if i<=5:kind='literal western Bogyiszlói út vertex';oid=206680745
 elif 11<=i<=15:kind='literal eastern Bogyiszlói út vertex';oid=228597416
 elif i in [8,16,17,18]:kind='literal canal bend/junction vertex';oid={8:119046388,16:119046388,17:760119123,18:760119123}[i]
 else:kind='manually inferred adjoining-land join';oid=None
 anchors.append({'ringIndex':i,'coordinates':xy,'anchorKind':kind,'osmWayId':oid})
(H/'source-anchors.json').write_text(json.dumps({'ring':anchors,'notAnOfficialQuarterBoundary':True,'noPointRadiusConstruction':True},ensure_ascii=False,indent=2)+'\n')
summary={'featureCount':1,'validWgs84':True,'estimated':True,'priority':30,'areaKm2':round(area/1e6,6),'lakeAreaKm2':round(water/1e6,6),'adjoiningLandAreaKm2':round((area-water)/1e6,6),'lakeFullyContained':True,'landFraction':round(1-water/area,5),'modernAccuracyEstablished':False,'outputSha256':hashlib.sha256((H/'features.geojson').read_bytes()).hexdigest()}
(H/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
