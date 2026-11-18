#!/usr/bin/env python3
from pathlib import Path
import json,gzip,hashlib
from shapely.geometry import Polygon,Point,mapping,shape
H=Path(__file__).resolve().parent
URL='https://gyongyos.hu/wp-content/uploads/2021/01/integralt-telepulesfejlesztesi-strategia-2016-its-gyongyos.pdf'
points={f['properties']['name']:f for f in json.loads(gzip.open(H/'source-points.geojson.gz','rt').read())['features']if f['properties'].get('municipality')=='Gyöngyös'}
muni=next(shape(f['geometry'])for f in json.loads(gzip.open(H/'source-municipalities.geojson.gz','rt').read())['features']if f['properties']['name']=='Gyöngyös')
roads=json.loads(gzip.open(H/'gyongyos-source-roads.geojson.gz','rt').read())['features'];features=[]
for row in json.loads((H/'gyongyos-manual-traces.json').read_text())['areas']:
 g=Polygon(row['ring']);assert g.is_valid and g.area>0
 fractionBeforeClip=g.intersection(muni).area/g.area
 clipped=fractionBeforeClip<.999999
 if clipped:g=g.intersection(muni)
 assert g.is_valid and g.geom_type in ['Polygon','MultiPolygon']
 if row['name']in points:assert g.covers(Point(points[row['name']]['geometry']['coordinates'])),row['name']
 p={'name':row['name'],'municipality':'Gyöngyös','method':'manual_actual_street_building_landscape_neighbourhood_envelope_estimate','estimated':True,'confidence':'low','qualityScore':15,'sourceUrl':URL,'sourceYear':2016,'sourceRoadFile':'gyongyos-source-roads.geojson.gz','sourceBuildingAndLandFile':'gyongyos-source-areas.geojson.gz','sourceTraceFile':'gyongyos-manual-traces.json','sourceRoadNames':row['sourceRoadNames'],'sourceRoadIds':[f['properties']['osmWayId']for f in roads if f['properties'].get('name')in row['sourceRoadNames']],'approximationNote':row['note']+' Low-confidence whole-neighbourhood/populated-area estimate from actual physical street/building/landscape context. Not an official or parcel boundary; manual outer joins and overlaps with neighbouring or parent units are intentional. No point-radius, circle or point-only rectangle.','radiusFallback':False,'semanticFootprint':False,'municipalityClipApplied':clipped,'fractionInsideMunicipalityBeforeClip':round(fractionBeforeClip,6),'sourceMunicipalityFile':'source-municipalities.geojson.gz','sourceSnapshot':'2026-11-12T21:23:05Z','license':'ODbL-1.0 for OSM geometry; municipal document contextual evidence','attribution':'Gyöngyös municipal ITS; © OpenStreetMap contributors'}
 features.append({'type':'Feature','properties':p,'geometry':mapping(g)})
(H/'gyongyos-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n');print(len(features))
