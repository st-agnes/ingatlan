#!/usr/bin/env python3
"""Rough source-map tracings, reusing the archived overview-to-EOV placement."""
from pathlib import Path
import json,hashlib
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon,MultiPolygon,shape,mapping
from shapely.ops import transform,unary_union
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
OLD=ROOT/'data/neighborhoods/sources/municipal-salgotarjan-next'
spec=json.loads((HERE/'salgotarjan-traces.json').read_text())
reg=OLD/'exploratory-frame-registration.json';matrix=np.array(json.loads(reg.read_text())['matrixPixelToEov'])
to_wgs=Transformer.from_crs(23700,4326,always_xy=True).transform
to_eov=Transformer.from_crs(4326,23700,always_xy=True).transform
source=ROOT/spec['source'];url='https://www.salgotarjan.hu/wp-content/uploads/fejlesztesidokumentumok_20220629_its.pdf'
def hashfile(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def polygon_parts(g):
    if g.geom_type=='Polygon':return [g]
    if g.geom_type=='MultiPolygon':return list(g.geoms)
    return [x for part in g.geoms for x in polygon_parts(part)]
def clean(g):
    if not g.is_valid:g=make_valid(g)
    parts=polygon_parts(g)
    return parts[0] if len(parts)==1 else MultiPolygon(parts)
features=[];eov_shapes={}
for area in spec['areas']:
    xy=np.c_[np.array(area['points'],dtype=float),np.ones(len(area['points']))]@matrix
    geom=clean(Polygon(xy));eov_shapes[area['name']]=geom
    p={'municipality':'Salgótarján','name':area['name'],'aliases':area.get('aliases',[]),
       'method':'rough_source_map_context_partition_estimate','estimated':True,
       'boundaryKind':area.get('kind','neighbourhood'),'qualityScore':15,
       'sourceYear':2022,'sourcePage':125,'sourceUrl':url,
       'source':{'provider':'municipal-map','url':url,'path':spec['source'],'sha256':hashfile(source),'registrationPath':str(reg.relative_to(ROOT)),'registrationSha256':hashfile(reg)},
       'approximationNote':'Visible cadastral/urban map context and coloured parent extents traced coarsely; internal separators and covered parts estimated manually. Name points support place assignment. Not a printed KSH fine-quarter contour; no independent absolute accuracy established.',
       'pointRadiusFallback':False,'absoluteAccuracyMetres':None}
    features.append({'type':'Feature','id':'salgotarjan-next:'+area['name'],'properties':p,'geometry':mapping(transform(to_wgs,geom))})
existing=json.loads((OLD/'salgotarjan-inferred.geojson').read_text())['features']
old_byname={f['properties']['name']:transform(to_eov,shape(f['geometry'])) for f in existing}
def add_union(name,geometries,description):
    g=clean(unary_union(geometries));features.append({'type':'Feature','id':'salgotarjan-next:'+name,'properties':{
        'municipality':'Salgótarján','name':name,'method':'source_map_parent_union_estimate','estimated':True,
        'boundaryKind':'parent_area','qualityScore':20,'sourceUrl':url,'sourceYear':2022,'sourcePage':125,
        'source':{'provider':'municipal-map','url':url,'path':spec['source'],'sha256':hashfile(source)},
        'approximationNote':description,'pointRadiusFallback':False},'geometry':mapping(transform(to_wgs,g))})
add_union('Somoskő, Eresztvény, Salgóbánya, Rónafalu és Rónabánya',
          [old_byname[n] for n in ['Somoskő','Rónafalu','Rónabánya']]+[eov_shapes['Eresztvény']],
          'Historic parent scheme with separately placed source components; Salgóbánya source component appended from an already collected named source surface when available. Parent overlap is intentional.')
# Include the existing Salgóbánya source surface in this same parent, not an invented radius.
catalog=json.loads((HERE/'salgotarjan-parent-inputs.geojson').read_text())['features']
salgo=next((f for f in catalog if f['properties']['municipality']=='Salgótarján' and f['properties']['name']=='Salgóbánya'),None)
if salgo:
    last=features[-1];last['geometry']=mapping(clean(unary_union([shape(last['geometry']),shape(salgo['geometry'])])))
add_union('Forgách-telep és Somlyóbányatelep',[old_byname['Forgáchtelep'],old_byname['Somlyóbánya']],
          'Source parent union of the two explicitly named source profile contours; finer components remain separate names.')
add_union('Acélgyár, Zagyvaróna, Ferenctelep, Művésztelep és Pintértelep',
          [old_byname['Zagyvaróna']]+[transform(to_eov,shape(f['geometry'])) for f in catalog if f['properties']['municipality']=='Salgótarján' and f['properties']['name'] in ['Művésztelep','Pintértelep','Szabadságtelep']],
          'Historical text/legend parent scheme. The Acélgyár/Ferenctelep versus Szabadságtelep wording differs between heading and legend; retained as approximate parent footprint, not asserted fine boundaries.')
for f in features:assert shape(f['geometry']).is_valid and not shape(f['geometry']).is_empty
(HERE/'salgotarjan-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
summary={'municipality':'Salgótarján','featureCount':len(features),'radiusFallbackCount':0,'sourceImage':spec['source'],'sourceImageSha256':hashfile(source),'registrationSha256':hashfile(reg),'method':'Explicit rough manual map-context partitions and source-parent component unions.','geographicAccuracyEstablished':False}
(HERE/'salgotarjan-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
