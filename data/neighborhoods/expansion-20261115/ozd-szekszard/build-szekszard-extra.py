#!/usr/bin/env python3
from pathlib import Path
import json,gzip
from shapely.geometry import Polygon,shape,mapping
H=Path(__file__).resolve().parent
roads=json.loads(gzip.open(H/'szekszard-source-roads.geojson.gz','rt').read())['features']
features=[]
f=next(f for f in roads if f['properties'].get('name')=='Csörge-tó'and f['geometry']['type']in ['Polygon','MultiPolygon'])
features.append({'type':'Feature','properties':{'name':'Csörge-tó','municipality':'Szekszárd','method':'named_source_lake_footprint_neighbourhood_estimate','estimated':True,'confidence':'low','qualityScore':10,'sourceUrl':f['properties']['source']['url'],'sourceGeometryFile':'szekszard-source-roads.geojson.gz','sourceObject':f['id'],'sourceRole':'named_natural_water_footprint','semanticFootprint':True,'approximationNote':'Literal named Csörge-tó lake outline retained as a narrow source-based neighbourhood footprint. Covers the actual named lake only; the conventional surrounding quarter/recreation area is larger and its full boundary is not established. Geometry is not a radial fallback and has not been expanded to an invented buffer. Low-confidence area-name extent association, not an official residential-quarter boundary.','radiusFallback':False,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'geometry':f['geometry']})
cs=[[18.6886,46.3764],[18.6880,46.3731],[18.6878,46.3714],[18.6900,46.3696],[18.6952,46.3695],[18.6994,46.3701],[18.7029,46.3707],[18.7056,46.3720],[18.7069,46.3750],[18.7064,46.3773],[18.7041,46.3789],[18.6998,46.3799],[18.6942,46.3795],[18.6897,46.3785],[18.6868,46.3774]]
names=['Borkút utca','Pál utca','Fuksz tető','Fuksz völgy','Faddi völgy','Kislisztesvölgy','Bor utca','Jázmin dűlő','Árnyék dűlő']
features.append({'type':'Feature','properties':{'name':'Palánkihegy','municipality':'Szekszárd','method':'named_hillside_actual_road_fabric_estimate','estimated':True,'confidence':'low','qualityScore':10,'sourceUrl':'https://www.openstreetmap.org/node/5928686276','sourceGeometryFile':'szekszard-source-roads.geojson.gz','sourceRoadNames':names,'sourceRoadIds':[f['properties']['source']['osmId']for f in roads if f['properties'].get('name')in names],'approximationNote':'Broad northern hillside/vineyard street footprint inferred from actual Borkút/Pál/Bor roads, Fuksz and Faddi valley branches and their connecting track fabric. The name point identifies the hill, while the irregular contour follows the visible road-enclosed land pattern; north/east garden-edge joins are manually inferred. Low confidence; not a complete cadastral hill boundary or a point-radius construction.','radiusFallback':False,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'geometry':mapping(Polygon(cs))})
for f in features:assert shape(f['geometry']).is_valid
(H/'szekszard-extra-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print(len(features))
