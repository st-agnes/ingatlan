#!/usr/bin/env python3
"""Apply the archived, explicitly inferred name-control placement to rough map traces."""
from pathlib import Path
import json,hashlib
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,MultiPolygon,mapping,shape
from shapely.ops import transform
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
spec=json.loads((HERE/'gyula-traces.json').read_text());reg=json.loads((HERE/'gyula-registration.json').read_text())
matrix=np.array(reg['matrixPixelToEov']);to_wgs=Transformer.from_crs(23700,4326,always_xy=True).transform
source=HERE/'gyula-sump.pdf';image=HERE/'gyula-sump-xref477.jpeg'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
url='https://ketegyhaza.hu/wp-content/uploads/2025/09/Gyula_varosterseg_SUMP_vileminyezisre.pdf'
features=[]
for a in spec['areas']:
    points=np.array(a['points'],dtype=float);xy=np.c_[points,np.ones(len(points))]@matrix
    geom=Polygon(xy);repair=not geom.is_valid
    if repair:
        geom=make_valid(geom)
        if geom.geom_type=='GeometryCollection':geom=MultiPolygon([x for x in geom.geoms if x.geom_type=='Polygon'])
    geom=transform(to_wgs,geom);assert geom.is_valid and not geom.is_empty
    p={'name':a['name'],'municipality':'Gyula','method':'rough_street_map_partition_estimate','estimated':True,
       'boundaryKind':'neighbourhood','qualityScore':15,'sourceYear':2025,'sourcePage':41,
       'sourceUrl':url,'source':{'provider':'municipal-regional-mobility-map','url':url,'path':str(source.relative_to(ROOT)),
       'sha256':sha(source),'embeddedImagePath':str(image.relative_to(ROOT)),'embeddedImageSha256':sha(image),'page':41},
       'sourceMapPublisher':'Gyula várostérség SUMP; bus map credited to helyimenetrend.mavcsoport.hu with OpenStreetMap basemap',
       'attribution':'© OpenStreetMap contributors; municipal/regional SUMP and bus map publishers',
       'approximationNote':spec['method']+' Labels and same-name OSM points provide an approximate map placement, not independent control/accuracy validation.',
       'registrationRmsMetres':reg['residualRmsM'],'absoluteAccuracyMetres':None,
       'sourceContextClipped':a.get('clippedSourceContext',False),'sourceEdgeContinuationEstimated':a.get('clippedSourceContext',False),
       'topologyRepairApplied':repair,'pointRadiusFallback':False}
    features.append({'type':'Feature','id':'gyula-next:'+a['name'],'properties':p,'geometry':mapping(geom)})
(HERE/'gyula-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
summary={'municipality':'Gyula','featureCount':len(features),'radiusFallbackCount':0,'sourcePdfSha256':sha(source),
    'sourceImageSha256':sha(image),'sourcePage':41,'registrationResidualRmsMetres':reg['residualRmsM'],
    'independentGeographicAccuracyEstablished':False,'sourceContainsOfficialQuarterContours':False,
    'method':'Rough hand-estimated street/built-up/river context polygons using named municipal mobility-map neighborhoods.'}
(HERE/'gyula-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary))
