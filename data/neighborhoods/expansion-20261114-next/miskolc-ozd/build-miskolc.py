#!/usr/bin/env python3
"""Quick, explicitly rough sector estimates from the preserved municipal map."""
from pathlib import Path
import json,hashlib
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,shape,mapping,box
from shapely.ops import transform,unary_union
from shapely.validation import make_valid
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
S=ROOT/'data/neighborhoods/sources/municipal-local-map-next'
URL='https://www.miskolc.hu/sites/default/files/dokumentumtar/mellekletek/2024-11/197_melleklet.pdf'
reg=json.loads((S/'miskolc-registration.json').read_text());m=np.array(reg['matrixPixelToEov']);inverse=np.linalg.inv(m[:2].T)
fwd=Transformer.from_crs(23700,4326,always_xy=True);back=Transformer.from_crs(4326,23700,always_xy=True)
def world(x,y,z=None):
 a=np.array([x,y]);v=m[:2].T@a+(m[2][:,None] if a.ndim==2 else m[2]);return fwd.transform(v[0],v[1])
def pixel(x,y,z=None):
 a=np.array(back.transform(x,y));v=inverse@(a-(m[2][:,None] if a.ndim==2 else m[2]));return v[0],v[1]
source=json.loads((S/'miskolc-source-raster.geojson').read_text());parents={f['properties']['sourceUnitNumber']:transform(pixel,shape(f['geometry'])) for f in source['features']}
spec=json.loads((HERE/'miskolc-traces.json').read_text());areas=[]
for a in spec['areas']:areas.append((a['name'],a.get('aliases',[]),Polygon(a['points']),a['note'],'rough_manual_map_partition'))
# Broad named alternatives retain actual source contours, while the explicit fine
# parent splits below are rough and never claimed to be original KSH linework.
areas += [
 ('Avas Dél városrész',['Avas Dél'],parents[8],'The source table names the entire mapped8 area Avas Dél városrész; this is a label alias, not a newly invented internal border.','source_map_polygon'),
 ('Avas',[],unary_union([parents[8],Polygon([(659,177),(703,178),(713,197),(714,219),(697,244),(683,268),(654,262),(646,239),(651,211)])]),'Broad Avas hill/estate parent formed from source8 and a rough northern historic-hillside continuation; overlaps smaller estates intentionally.','rough_manual_map_partition'),
 ('Lillafüred',[],parents[17].intersection(box(225,-100,900,600)),'Eastern Lillafüred/Alsóhámor valley portion of mapped17. The internal split toward Ómassa-Jávorkút is approximate, not an original KSH contour.','rough_manual_map_partition'),
 ('Ómassa – Jávorkút',[],parents[17].intersection(box(-100,-100,225,600)),'Western deep-valley/forest constituent of mapped17; simple separator between the two source-listed constituents is an explicit estimate.','rough_manual_map_partition'),
 ('Diósgyőr – Berekalja – Majláth',['Diósgyőr- Nyugati városrész'],parents[15],'Alternative full source-group15 name lists its three KSH constituents; does not give the same outline separately to each child.','source_map_polygon'),
 ('Bedegvölgy-Bodótető',[],parents[6].intersection(box(-100,-100,644,600)),'Western source6 slope region, using the source constituent listing; the eastern separator toward Tetemvár is approximate.','rough_manual_map_partition'),
 ('Szentpéteri kapu Kelet',[],parents[1].intersection(Polygon([(703,108),(760,108),(760,190),(712,190),(707,155),(702,135)])),'Eastern industrial/work-zone part of the southern Szentpéteri corridor described by source table59; internal dividing corridor is estimated.','rough_manual_map_partition'),
 ('Szentpéteri kapu Nyugat',[],parents[1].intersection(Polygon([(650,108),(703,108),(702,135),(707,155),(712,190),(650,190)])),'Western residential/institutional part of Szentpéteri corridor; source explicitly distinguishes eastern industrial uses.','rough_manual_map_partition'),
 ('Zsarnai telep – Repülőtér',[],parents[1].intersection(box(640,-100,900,113)),'Whole northern source1 constituent listed as Zsarnai telep-Repülőtér; southern separator is approximate.','rough_manual_map_partition'),
]
by_name={a[0]:a[2] for a in areas}
areas += [
 ('Békeszálló telep – Muszkás telep',[],unary_union([by_name['Békeszálló-telep'],by_name['Muszkástelep']]),'Parent name from source KSH constituent list; union of the two explicit rough fine estimates.','rough_manual_map_partition')]
features=[]
for name,aliases,g,note,method in areas:
 if not g.is_valid:g=make_valid(g)
 if g.geom_type=='GeometryCollection':g=unary_union([x for x in g.geoms if x.geom_type in ['Polygon','MultiPolygon']])
 g=transform(world,g)
 assert g.is_valid and not g.is_empty and g.geom_type in ['Polygon','MultiPolygon'],name
 p={'municipality':'Miskolc','name':name,'aliases':aliases,'method':method,'estimated':method!='source_map_polygon','qualityScore':20,
 'source':{'provider':'municipal-map','url':URL,'path':(S/'miskolc-source-raster.geojson').relative_to(ROOT).as_posix(),'sha256':hashlib.sha256((S/'miskolc-source-raster.geojson').read_bytes()).hexdigest(),'page':228},
 'sourceUrl':URL,'sourceYear':2014,'sourceReproducedYear':2024,'boundaryKind':'rough_neighborhood_or_parent_area','approximationNote':note,
 'precision':'rough sector interpretation; no independently measured absolute accuracy','radiusFallback':False,
 'construction':'Visible municipal source map and constituent descriptions, manual pixel sectors; internal separators are inferred, not recovered official lines.'}
 features.append({'type':'Feature','id':'miskolc-next:'+name,'properties':p,'geometry':mapping(g)})
(HERE/'miskolc-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(HERE/'miskolc-summary.json').write_text(json.dumps({'features':len(features),'sourceYear':2014,'sourceTablePages':[228,229,230,231],'manualPartitionCount':sum(f['properties']['estimated'] for f in features),'circleCount':0,'names':[f['properties']['name'] for f in features]},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'features':len(features),'valid':len(features),'circleCount':0}))
