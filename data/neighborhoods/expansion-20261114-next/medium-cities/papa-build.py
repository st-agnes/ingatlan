#!/usr/bin/env python3
"""Approximate historic source colours and documented street-block parts in Pápa."""
from pathlib import Path
import hashlib,json,unicodedata
import numpy as np
from PIL import Image,ImageDraw
from pyproj import Transformer
from shapely.geometry import Polygon,MultiPolygon,mapping,shape,Point
from shapely.ops import unary_union,transform
from shapely.validation import make_valid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
spec=json.loads((HERE/'papa-trace-specifications.json').read_text())
registration=json.loads((HERE/'papa-registration.json').read_text());matrix=np.array(registration['pixelToEovRows'])
to_wgs=Transformer.from_crs(23700,4326,always_xy=True).transform
url='https://papa.hu/wp-content/uploads/2024/04/Papa-Varos-Integralt-Telepulesfejlesztesi-Strategiaja-2015.pdf'
source_sha=hashlib.sha256((HERE/'papa-its2015.pdf').read_bytes()).hexdigest()
features=[];known={};pixel_shapes={}
image=Image.open(HERE/'papa-source-map.jpeg').convert('RGB');draw=ImageDraw.Draw(image)
for area in spec['areas']:
    if 'unionOf' in area:
        world=unary_union([known[n] for n in area['unionOf']]);repair=False
    else:
        pixels=np.array(area['points']);xy=np.c_[pixels,np.ones(len(pixels))]@matrix
        polygon=Polygon(xy);repair=not polygon.is_valid
        if repair:
            polygon=make_valid(polygon)
            if polygon.geom_type=='GeometryCollection':polygon=MultiPolygon([g for g in polygon.geoms if g.geom_type=='Polygon'])
        world=transform(to_wgs,polygon)
        draw.line([tuple(p) for p in area['points']]+[tuple(area['points'][0])],fill=(0,80,190),width=1)
    assert world.is_valid and not world.is_empty and world.geom_type in ['Polygon','MultiPolygon']
    known[area['name']]=world
    properties={'name':area['name'],'municipality':'Pápa','aliases':area.get('aliases',[]),
      'method':'rough_map_partition_estimate','construction':area['construction'],'estimated':True,
      'qualityScore':30 if area['construction'].startswith('source_colour') else 20,
      'sourceSubdivisionKind':'parent_quarter' if area['construction'].startswith('source_colour') or 'unionOf' in area else 'neighbourhood',
      'sourceYear':2015,'sourcePage':120,'sourceUrl':url,
      'source':{'provider':'municipal-map','url':url,'path':(HERE/'papa-its2015.pdf').relative_to(ROOT).as_posix(),'sha256':source_sha,'page':120,'nativeImageXref':781},
      'sourceTextBoundaryPages':[121,122,123,124,126,127,128,129,130,131],
      'approximationNote':'Simplified hand trace of observed source map colour/road extents. Housing-estate subparts use visible street-block layout and source/current name placement; those internal cuts are inferred rather than claimed printed quarter borders. Distinct broad and fine areas intentionally overlap.',
      'georeferencingNote':registration['method'],'fitRmsMetresDiagnosticOnly':registration['fitRmsMetresDiagnostic'],
      'absoluteAccuracyMetres':None,'topologyRepairApplied':repair}
    if 'unionOf' in area:properties['sourceParentMembers']=area['unionOf']
    features.append({'type':'Feature','id':'Pápa:'+area['name'],'properties':properties,'geometry':mapping(world)})
out=HERE/'papa-features.geojson';out.write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
image.save(HERE/'papa-trace-overlay.png')
summary={'featureCount':len(features),'municipality':'Pápa','radiusFallbackCount':0,'geometriesValid':True,
         'originalSourcePdfSha256':source_sha,'featuresSha256':hashlib.sha256(out.read_bytes()).hexdigest(),
         'fitRmsMetresDiagnosticOnly':registration['fitRmsMetresDiagnostic'],
         'uncoveredKnownNamesOutsideSourceColourMap':['Kishegy','Öreghegy'],
         'currentCityCompletenessClaimed':False}
(HERE/'papa-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
