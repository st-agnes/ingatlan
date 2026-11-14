#!/usr/bin/env python3
"""Quick explicit map-trace estimates; no radius, Voronoi or purported legal borders."""
from pathlib import Path
import collections,hashlib,json
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,MultiPolygon,mapping
from shapely.ops import transform
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
registrations=json.loads((HERE/'registrations.json').read_text())
spec=json.loads((HERE/'trace-specifications.json').read_text())
to_wgs=Transformer.from_crs(23700,4326,always_xy=True).transform
features=[]
for area in spec['areas']:
    city=area['municipality'];registration=registrations[city]
    rows=np.array(registration['pixelToEovRows'])
    pixels=np.array(area['points']);xy=np.c_[pixels,np.ones(len(pixels))]@rows
    polygon=Polygon(xy);repaired=not polygon.is_valid
    if repaired:
        polygon=make_valid(polygon)
        if polygon.geom_type=='GeometryCollection':
            polygon=MultiPolygon([g for g in polygon.geoms if g.geom_type=='Polygon'])
    world=transform(to_wgs,polygon)
    assert world.is_valid and not world.is_empty and world.geom_type in ['Polygon','MultiPolygon']
    source=HERE/registration['sourceMap']
    props={'name':area['name'],'municipality':city,'aliases':area.get('aliases',[]),
           'method':'rough_map_partition_estimate','estimated':True,
           'construction':area['construction'],'sourceYear':registration['sourceYear'],
           'sourcePage':registration['physicalPage'],'sourceUrl':registration['sourceUrl'],
           'source':{'provider':'municipal-map','url':registration['sourceUrl'],
                     'path':source.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()},
           'qualityScore':25,'topologyRepairApplied':repaired,
           'sourceSubdivisionKind':'parent_quarter' if area['construction']=='observed_parent_colour' else 'neighbourhood',
           'approximationNote':'Visible historical municipal map colours/roads and dotted internal separators give coarse hand-read extents. Fine divisions and unclear gaps are estimated, not claimed printed or official quarter boundaries. Named housing estates use visible street-block layout and current name placement, not a circle.',
           'georeferencingNote':registration['placementNote'],'absoluteAccuracyMetres':None}
    features.append({'type':'Feature','id':city+':'+area['name'],'properties':props,'geometry':mapping(world)})
body={'type':'FeatureCollection','features':features}
(HERE/'features.geojson').write_text(json.dumps(body,ensure_ascii=False,separators=(',',':'))+'\n')
for city,slug in [('Vác','vac'),('Kiskunfélegyháza','kiskun')]:
    selected={'type':'FeatureCollection','features':[f for f in features if f['properties']['municipality']==city]}
    (HERE/(slug+'-features.geojson')).write_text(json.dumps(selected,ensure_ascii=False,separators=(',',':'))+'\n')
summary={'featureCount':len(features),'municipalities':dict(collections.Counter(f['properties']['municipality'] for f in features)),
         'radiusFallbackCount':0,'geometriesValid':True,'method':'source-map colour extents and rough internal partitions',
         'featuresSha256':hashlib.sha256((HERE/'features.geojson').read_bytes()).hexdigest(),
         'currentCityCompletenessClaimed':False}
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
