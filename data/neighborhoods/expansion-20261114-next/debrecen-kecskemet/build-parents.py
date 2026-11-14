#!/usr/bin/env python3
"""Retain named whole quarters above their source-map subdivisions."""
from pathlib import Path
import json,hashlib
from shapely.geometry import shape,mapping
from shapely.ops import unary_union
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
source=HERE/'kecskemet-parent-inputs.geojson'
rows={f['properties']['name']:f for f in json.loads(source.read_text())['features']}
groups=[
 ('Belváros',['Bethlenváros','Homoki-domb','Városközpont','Rákócziváros','Erzsébetváros','Árpádváros','Kossuthváros'],'Figure73 is explicitly titled I.Belváros and partitions this whole area into the seven named source cells.'),
 ('Széchenyiváros',['Széchenyiváros I.','Széchenyiváros II.','Széchenyiváros III.'],'Source figure81 splits the named whole residential quarter into I/II/III; retain the parent as their union.'),
 ('Petőfiváros',['Petőfiváros I.','Petőfiváros II.'],'Source figure79 splits the named whole quarter into I/II; retain both the whole and subdivisions.'),
 ('Déli ipartelepek',['Déli iparterület I.','Déli iparterület II.'],'Broader southern industrial search area formed from the two named source-map industrial components.'),
 ('Szent László-város',['Muszáj','Kósafalu','Rendőrfalu','Szent László város — belső forráscella'],'The source SzentLászló-város region contains these residential source components; the industrial source partitions remain separately named. This is the approximate residential parent extent, not a legal border.')]
features=[]
for name,members,note in groups:
    geom=unary_union([shape(rows[x]['geometry']) for x in members]);assert geom.is_valid and not geom.is_empty
    old_source=rows[members[0]]['properties'].get('source',{});source_url=old_source.get('url') or (old_source.get('evidenceUrls') or [None])[0]
    features.append({'type':'Feature','id':'kecskemet-parent:'+name,'properties':{'name':name,'municipality':'Kecskemét',
       'method':'source_map_parent_union_estimate','estimated':True,'boundaryKind':'parent_area','qualityScore':30,
       'sourceSubdivisionKind':'parent_quarter','sourceMembers':members,
       'source':{'provider':'municipal-map-components','path':str(source.relative_to(ROOT)),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()},
       'sourceUrl':source_url,
       'approximationNote':note,'pointRadiusFallback':False},'geometry':mapping(geom)})
(HERE/'parent-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print(json.dumps({'features':len(features),'names':[f['properties']['name'] for f in features]},ensure_ascii=False))
