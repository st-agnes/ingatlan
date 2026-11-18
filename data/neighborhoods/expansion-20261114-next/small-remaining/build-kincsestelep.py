#!/usr/bin/env python3
"""A coarse finer urban part from street/stream context and actual built-up edge."""
from pathlib import Path
import json,gzip,hashlib
from shapely.geometry import shape,Polygon,mapping
from shapely.ops import transform
from pyproj import Transformer
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];forward=Transformer.from_crs(4326,23700,always_xy=True).transform;inverse=Transformer.from_crs(23700,4326,always_xy=True).transform
raw=json.loads(gzip.decompress((HERE/'source-areas.geojson.gz').read_bytes()))['features'];source=next(f for f in raw if f['id']=='osm:relation:2409555')
# The mask follows the compact northern residential tongue and the Puskin-street
# side. Its southern separators use the old Kenyere-channel/local street band.
# Long road gaps are explicitly only a rough local partition, not official borders.
coords=[[745700,122300],[747350,122300],[747281,121774],[747227,121630],[747100,121350],[746421,121361],[746312,121323],[746290,121299],[746272,121275],[746230,121182],[746222,121172],[746009,121067],[745700,121500]]
mask=Polygon(coords);geom=transform(forward,shape(source['geometry'])).intersection(mask);assert geom.is_valid and not geom.is_empty
point=next(f for f in json.loads((HERE/'target-name-points.geojson').read_text())['features']if f['properties']['name']=='Kincsestelep');assert geom.covers(transform(forward,shape(point['geometry'])))
assert 100_000<geom.area<1_500_000
spec={'name':'Kincsestelep','coordinateSystem':'EPSG:23700','handEstimatedPartitionMask':coords,'sourceResidentialFootprintId':source['id'],'contextImagePath':str((HERE/'kincsestelep-context.png').relative_to(ROOT)),'contextImageExtentPath':str((HERE/'kincsestelep-context-extent.json').relative_to(ROOT)),'sourceContainsExplicitNamedQuarterBoundary':False,'note':'The large10.1km² core residential source surface is reduced to a plausible finer northern part. Its northern/western outer built-up edge is literal; the Puskin-side and old-channel/local-street southern separation are approximate. No radius, convex hull or Voronoi cell.'}
(HERE/'kincsestelep-trace.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
p={'name':'Kincsestelep','municipality':'Hódmezővásárhely','method':'rough_street_map_partition_estimate','estimated':True,'qualityScore':15,'semanticFootprint':True,'boundaryKind':'neighbourhood','pointRadiusFallback':False,'sourceUrl':point['properties']['source']['sourceUrl'],'source':{'provider':'osm-built-up-and-street-context-inference','path':str((HERE/'source-areas.geojson.gz').relative_to(ROOT)),'sha256':hashlib.sha256((HERE/'source-areas.geojson.gz').read_bytes()).hexdigest(),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'sourceResidentialFootprint':source['properties']['source'],'nameEvidence':point,'areaSquareMetres':round(geom.area,1),'traceSpecificationPath':str((HERE/'kincsestelep-trace.json').relative_to(ROOT)),'approximationNote':spec['note']+' This is a deliberately coarse finer urban search footprint supported by actual street/stream/built-up geometry, not a historically verified Kincsestelep boundary; nearby broader Tabán/Béketelep divisions may overlap.'}
f={'type':'Feature','id':'small-remaining:kincsestelep','properties':p,'geometry':mapping(transform(inverse,geom))};(HERE/'kincsestelep-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[f]},ensure_ascii=False,separators=(',',':'))+'\n');print(geom.area)
