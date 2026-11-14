#!/usr/bin/env python3
"""Rough quarter sectors derived from municipal street/satellite maps."""
from pathlib import Path
import json,hashlib
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,mapping
from shapely.ops import transform
from shapely.validation import make_valid
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
URL='https://www.ozd.hu/adat/Ozd_varos_honlapja_fajlok/Varoshaza/Tajekoztatok_es_felhivasok/Integralt_Telepulesfejlesztesi_Strategia/%C3%93zd%20V%C3%A1ros%20Integr%C3%A1lt%20Telep%C3%BCl%C3%A9sfejleszt%C3%A9si%20Strat%C3%A9gi%C3%A1ja_2024_v%C3%A9gleges.pdf'
reg=json.loads((HERE/'ozd-rough-registration.json').read_text());m=np.array(reg['matrixMasterPixelToEov']);t=Transformer.from_crs(23700,4326,always_xy=True)
def world(x,y,z=None):
 a=np.array([x,y]);v=m[:2].T@a+(m[2][:,None] if a.ndim==2 else m[2]);return t.transform(v[0],v[1])
points={p['name']:p for p in json.loads((HERE/'ozd-name-map-points.json').read_text())}
source=HERE/'ozd-2024.pdf';sha=hashlib.sha256(source.read_bytes()).hexdigest();features=[]
for a in json.loads((HERE/'ozd-traces.json').read_text())['areas']:
 g=Polygon(a['points']);repaired=not g.is_valid
 if repaired:g=make_valid(g)
 g=transform(world,g);assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon']
 point=points.get(a['name'])
 p={'municipality':'Ózd','name':a['name'],'aliases':a.get('aliases',[]),'method':'rough_manual_map_partition','estimated':True,'qualityScore':15,
 'source':{'provider':'municipal-map','url':URL,'path':source.relative_to(ROOT).as_posix(),'sha256':sha,'pages':[49,54]},'sourceUrl':URL,'sourceYear':2024,
 'boundaryKind':'rough_neighborhood','sourceNamePoint':point,'approximationNote':a['note'],'radiusFallback':False,
 'registration':'Approximate printed place-label controls on satellite page49 and three shared outline corners on street page54; unmeasured absolute accuracy.',
 'construction':'Hand-inferred sectors on actual municipal road/satellite background. Action-area fills are NOT claimed to equal full conventional quarter borders.',
 'topologyRepairApplied':repaired}
 features.append({'type':'Feature','id':'ozd-next:'+a['name'],'properties':p,'geometry':mapping(g)})
(HERE/'ozd-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'ozd-summary.json').write_text(json.dumps({'features':len(features),'circleCount':0,'sourceYear':2024,'sourcePages':[43,44,45,46,47,48,49,50,51,52,53,54],'sourceSha256':sha,'absoluteAccuracyEstablished':False,'note':'Only named quarters with physical map context were estimated; not all Ózd quarters, and no independently measured accuracy.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'features':len(features),'valid':len(features),'circleCount':0}))
