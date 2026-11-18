#!/usr/bin/env python3
from pathlib import Path
import json,gzip
from shapely.geometry import Polygon,Point,mapping,shape
H=Path(__file__).resolve().parent
URL='https://www.satoraljaujhely.hu/files/letoltesek/telepulesiarculat/tortenelmi%20varosreszek/Tortenelmi%20varosreszek%20terkepi%20lehatarolasa.pdf'
points={f['properties']['name']:f for f in json.loads(gzip.open(H/'source-points.geojson.gz','rt').read())['features']if f['properties'].get('municipality')=='Sátoraljaújhely'};muni=next(shape(f['geometry'])for f in json.loads(gzip.open(H/'source-municipalities.geojson.gz','rt').read())['features']if f['properties']['name']=='Sátoraljaújhely');roads=json.loads(gzip.open(H/'satoraljaujhely-source-roads.geojson.gz','rt').read())['features'];features=[]
for row in json.loads((H/'satoralja-manual-traces.json').read_text())['areas']:
 g=Polygon(row['ring']);assert g.is_valid and g.area>0
 ratio=g.intersection(muni).area/g.area;clipped=ratio<.999999
 if clipped:g=g.intersection(muni)
 assert g.is_valid and g.geom_type in ['Polygon','MultiPolygon']and g.covers(Point(points[row['name']]['geometry']['coordinates'])),row['name']
 p={'name':row['name'],'municipality':'Sátoraljaújhely','method':'manual_actual_street_building_landscape_neighbourhood_envelope_estimate','estimated':True,'confidence':'low','qualityScore':15,'sourceUrl':points[row['name']]['properties']['source']['url'],'municipalNameContextUrl':URL,'sourceRoadFile':'satoraljaujhely-source-roads.geojson.gz','sourceBuildingAndLandFile':'satoraljaujhely-source-areas.geojson.gz','sourceTraceFile':'satoralja-manual-traces.json','sourceRoadNames':row['sourceRoadNames'],'sourceRoadIds':[f['properties']['osmWayId']for f in roads if f['properties'].get('name')in row['sourceRoadNames']],'approximationNote':row['note']+' Low-confidence broad neighbourhood/populated-area estimate from actual road, building, garden and landscape context. The municipal historical-map source is retained as contextual research; these coordinates are manual physical-fabric estimates, not falsely claimed native PDF boundaries. Not an official/cadastral boundary. Manual joins, parent-child/adjacent overlaps and source-point placement uncertainty remain. No circle, point-radius or point-only rectangle.','radiusFallback':False,'semanticFootprint':False,'municipalityClipApplied':clipped,'fractionInsideMunicipalityBeforeClip':round(ratio,6),'sourceSnapshot':'2026-11-12T21:23:05Z','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'}
 features.append({'type':'Feature','properties':p,'geometry':mapping(g)})
(H/'satoralja-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n');print(len(features))
