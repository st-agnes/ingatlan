#!/usr/bin/env python3
"""Transform the explicitly rough map traces using the depicted municipality extent."""
from pathlib import Path
import collections,gzip,hashlib,json
from pyproj import Transformer
from shapely.geometry import shape,mapping,Polygon,MultiPolygon
from shapely.ops import transform
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
spec=json.loads((HERE/'trace-specifications.json').read_text())
raw=ROOT/'data/neighborhoods/sources/country-osm/municipalities.geojson.gz'
municipalities={f['properties']['name']:f for f in json.loads(gzip.decompress(raw.read_bytes()))['features']}
to_eov=Transformer.from_crs(4326,23700,always_xy=True).transform
to_wgs=Transformer.from_crs(23700,4326,always_xy=True).transform
features=[];towns=[]
for town in spec['towns']:
    city=town['municipality'];municipality=municipalities[city]
    x0,y0,x1,y1=transform(to_eov,shape(municipality['geometry'])).bounds
    left,top,right,bottom=town['municipalityExtentPixels']
    source=HERE/town['pdf'];source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    for area in town['areas']:
        xy=[(x0+(px-left)/(right-left)*(x1-x0),y1-(py-top)/(bottom-top)*(y1-y0)) for px,py in area['points']]
        geometry=Polygon(xy);repaired=not geometry.is_valid
        if repaired:
            geometry=make_valid(geometry)
            if geometry.geom_type=='GeometryCollection':
                parts=[g for g in geometry.geoms if g.geom_type=='Polygon'];geometry=MultiPolygon(parts)
        geometry=transform(to_wgs,geometry)
        assert geometry.is_valid and not geometry.is_empty
        p={'name':area['name'],'municipality':city,'aliases':area.get('aliases',[]),
           'method':'rough_manual_map_trace','estimated':True,'sourceYear':town['sourceYear'],
           'boundaryKind':'mapped_neighborhood_or_parent_area','sourceMembers':area.get('sourceMembers',[]),
           'sourceUrl':town['sourceUrl'],'sourcePath':source.relative_to(ROOT).as_posix(),'sourceSha256':source_sha,
           'sourcePage':town['page'],'source':{'url':town['sourceUrl'],'path':source.relative_to(ROOT).as_posix(),
            'sha256':source_sha,'page':town['page'],'provider':'municipal-map'},
           'registration':'Map municipality extent fitted to OSM municipality extent in EOV; north-up assumption, no independent control points.',
           'precision':'rough; no absolute accuracy established','qualityScore':20,
           'approximationNotes':[spec['note'],'Administrative background frame supplies placement, not a new quarter-boundary claim.',
            'Source parent members are NOT aliases for the whole parent area.'],
           'topologyRepairApplied':repaired}
        features.append({'type':'Feature','id':city+':'+area['name'],'properties':p,'geometry':mapping(geometry)})
    towns.append({'municipality':city,'sourceYear':town['sourceYear'],'count':len(town['areas']),
                  'municipalityReferenceEovBounds':[x0,y0,x1,y1],'sourcePdfSha256':source_sha})
output={'type':'FeatureCollection','features':features}
(HERE/'features.geojson').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'summary.json').write_text(json.dumps({'featureCount':len(features),'municipalities':towns,'radiusFallbackCount':0,
    'method':spec['method'],'completeCurrentCityCoverageClaimed':False,'originalMunicipalitiesSha256':hashlib.sha256(raw.read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'features':len(features),'towns':dict(collections.Counter(f['properties']['municipality'] for f in features))},ensure_ascii=False))
