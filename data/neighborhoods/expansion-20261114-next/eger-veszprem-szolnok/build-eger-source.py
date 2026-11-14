#!/usr/bin/env python3
"""Small source-shaped Eger batch: park footprint, union, explicit remainder."""
from pathlib import Path
import json,hashlib
from shapely.geometry import shape,mapping
from shapely.ops import unary_union

HERE=Path(__file__).resolve().parent
old={f['properties']['name']:f for f in json.loads((HERE/'eger-existing-source-shapes.geojson').read_text())['features']}
raw=json.loads((HERE/'eger-areas.geojson').read_text())['features']
labels={x['name']:x['sourcePoint'] for x in json.loads((HERE/'eger-registration.json').read_text())['labels']}
park=next(f for f in raw if f['properties']['osmWayId']==120931688)
features=[]
specs=[('Lajosváros',unary_union([shape(old['Lajosváros kelet']['geometry']),shape(old['Lajosváros – nyugat']['geometry'])]),'source_map_part_union','Union of the two actual source-map east/west areas; no new dividing edge.',['Lajosváros kelet','Lajosváros – nyugat']),('Almagyar',shape(old['Almagyar – Merengő']['geometry']).difference(shape(old['Merengő']['geometry'])),'source_map_remainder_inferred_area','Explicitly approximate remainder: the broad Almagyar–Merengő source group minus the retained Merengő source surface. The Merengő surface may not be its entire everyday quarter extent.',['Almagyar – Merengő','Merengő']),('Érsekkert',shape(park['geometry']),'source_polygon','Literal closed OSM park boundary, no invented edges.',[])]
for name,g,method,note,parts in specs:
 assert g.is_valid and not g.is_empty
 source={'provider':'source-map-composition','url':'https://eger.hu/public/uploads/m2-melleklet-2016-0826_57d7ea2877316.pdf','path':str((HERE/'eger-existing-source-shapes.geojson').relative_to(HERE.parents[3]))}
 if name=='Érsekkert':source={'provider':'openstreetmap','url':park['properties']['sourceUrl'],'osmWayId':120931688,'tags':park['properties']['tags'],'path':str((HERE/'eger-areas.geojson').relative_to(HERE.parents[3]))}
 source['sha256']=hashlib.sha256((HERE.parents[3]/source['path']).read_bytes()).hexdigest()
 p={'name':name,'municipality':'Eger','method':method,'estimated':method!='source_polygon','qualityScore':35,'candidateBoundaryKind':'neighbourhood','source':source,'sourceUrl':source['url'],'nameEvidence':labels[name],'sourceParts':parts,'approximationNote':note,'absoluteAccuracyMetres':None}
 features.append({'type':'Feature','id':'next-eger-source:'+name,'properties':p,'geometry':mapping(g)})
(HERE/'eger-source-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print('3 source-shaped Eger areas')
