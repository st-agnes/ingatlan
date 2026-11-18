#!/usr/bin/env python3
"""Coarse small estate outline following four archived actual residential streets."""
from pathlib import Path
import json,hashlib
from shapely.geometry import Polygon,mapping,shape
from shapely.ops import transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
source=HERE/'feszek-source-roads.geojson'
if not source.exists():
 rows=json.loads((HERE.parent/'debrecen-kecskemet/context-roads.geojson').read_text())['features'];ids=['osm:way:126208879','osm:way:126208874','osm:way:136771899','osm:way:221707681'];source.write_text(json.dumps({'type':'FeatureCollection','features':[f for f in rows if f['id'] in ids]},ensure_ascii=False,indent=2)+'\n')
r={f['id']:f for f in json.loads(source.read_text())['features']}
get=lambda i:r['osm:way:'+str(i)]['geometry']['coordinates']
# Derekassy west->east, Sütő north->south, Balogh east->west, Nádsíp south->north.
# Street dead ends leave short20–65m gaps; these two links are hand-estimated edges.
poly=Polygon(list(reversed(get(126208874)[1:]))+get(136771899)[1:]+list(reversed(get(221707681)[:3]))+get(126208879)[:3])
assert poly.is_valid
point=next(f for f in json.loads((HERE/'target-name-points.geojson').read_text())['features'] if f['properties']['name']=='Fészek lakópark');assert poly.covers(shape(point['geometry']))
area=transform(Transformer.from_crs(4326,23700,always_xy=True).transform,poly).area;assert 5_000<area<250_000
p={'name':'Fészek lakópark','municipality':'Debrecen','method':'rough_street_map_partition_estimate','estimated':True,'qualityScore':15,'boundaryKind':'neighbourhood','semanticFootprint':True,'pointRadiusFallback':False,'nameEvidence':point,'areaSquareMetres':round(area,1),'sourceUrl':point['properties']['source']['sourceUrl'],'source':{'provider':'osm-street-fabric-inference','path':str(source.relative_to(ROOT)),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'boundingSourceWays':[{'id':f['id'],'name':f['properties']['name'],'url':f['properties']['source']['url']} for f in r.values()],'approximationNote':'Rough compact residential-estate footprint inferred from the named point and actual Nádsíp/Derekassy István/Sütő András/Balogh Tamás street fabric. Two short gaps between street ends are connected approximately. The source does not provide an explicit whole-estate boundary; this is not an official contour, circle, hull or Voronoi cell.'}
f={'type':'Feature','id':'small-remaining:feszek','properties':p,'geometry':mapping(poly)};(HERE/'feszek-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[f]},ensure_ascii=False,separators=(',',':'))+'\n');print(area)
