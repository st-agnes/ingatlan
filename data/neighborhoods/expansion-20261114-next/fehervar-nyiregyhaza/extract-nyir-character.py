#!/usr/bin/env python3
"""Trace actual municipal character-map surfaces for rural labelled localities."""
from pathlib import Path
import json,hashlib,collections
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import shape,mapping,box,Point
from shapely.ops import unary_union,transform
from shapely.validation import make_valid
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
URL='https://uj.nyiregyhaza.hu/lib/adattar/hatalyos/180516_2017_hr_31.pdf';PDF=OUT/'nyiregyhaza-tak2017.pdf';IMAGE=OUT/'nyir-character-map.jpeg'
parents=json.loads((OUT/'source-municipalities.geojson').read_text())['features'];parent=next(f for f in parents if f['properties']['name']=='Nyíregyháza')
fwd=Transformer.from_crs(4326,23700,always_xy=True).transform;inv=Transformer.from_crs(23700,4326,always_xy=True).transform
ex0,ey0,ex1,ey1=transform(fwd,shape(parent['geometry'])).bounds
# Entire municipality map frame, excluding the legend. Native image coordinates.
frame=[299,74,1254,1033];left,top,right,bottom=frame

def place(x,y,z=None):return ex0+(x-left)/(right-left)*(ex1-ex0),ey1-(y-top)/(bottom-top)*(ey1-ey0)

pixels=np.asarray(Image.open(IMAGE).convert('RGB')).astype(np.int32)
components=[]
for klass,colour in [('Bokortanyák',[219,233,174]),('Kertvárosias és falusias településrész',[168,202,63])]:
 distance=((pixels-np.asarray(colour))**2).sum(axis=2)
 mask=distance<22**2;mask[:top]=False;mask[bottom:]=False;mask[:,:left]=False;mask[:,right:]=False
 mask=ndimage.binary_fill_holes(ndimage.binary_closing(mask,iterations=2))
 labels,count=ndimage.label(mask)
 for n,sl in enumerate(ndimage.find_objects(labels),1):
  if sl is None:continue
  local=labels[sl]==n
  if local.sum()<12:continue
  rows=[];yoff,xoff=sl[0].start,sl[1].start
  for yy,row in enumerate(local):
   xs=np.flatnonzero(row)
   if not len(xs):continue
   starts=[xs[0]];ends=[]
   for a,b in zip(xs,xs[1:]):
    if b>a+1:ends.append(a);starts.append(b)
   ends.append(xs[-1])
   rows.extend(box(xoff+int(a),yoff+yy,xoff+int(b)+1,yoff+yy+1) for a,b in zip(starts,ends))
  native=unary_union(rows).simplify(1,preserve_topology=True)
  eov=transform(place,native)
  if not eov.is_valid:eov=make_valid(eov)
  if eov.geom_type not in ['Polygon','MultiPolygon']:continue
  components.append({'klass':klass,'native':native,'eov':eov,'id':klass+':'+str(n),'pixels':int(local.sum())})
labels=json.loads((OUT/'source-labels.geojson').read_text())['features']
wanted=['Alispántanya','Vadastanya','Mohosbokor','Nagylapos','Samókabokor','Felsőbadúrbokor','Nyírjes','Jókaitelep','Ókistelekiszőlő','Újkistelekiszőlő','Kerti lak','Cúgosrész I.','Tópart']
output=[];assignments=[]
for label in labels:
 p=label['properties'];name=p['name']
 if p['municipality']!='Nyíregyháza' or name not in wanted:continue
 pt=transform(fwd,shape(label['geometry']));ranked=sorted(components,key=lambda c:(c['eov'].distance(pt),c['eov'].area))
 if not ranked or ranked[0]['eov'].distance(pt)>300:continue
 component=ranked[0]
 # Do not give a whole large residential parent to one small child label.
 if component['eov'].area>2_000_000:continue
 hits=[]
 for other in labels:
  if other['properties']['municipality']=='Nyíregyháza' and component['eov'].covers(transform(fwd,shape(other['geometry']))):hits.append(other['properties']['name'])
 if len(set(hits)-{name})>0:continue
 geo=transform(inv,component['eov']);distance=component['eov'].distance(pt)
 props={'name':name,'municipality':'Nyíregyháza','method':'source_map_footprint_inference','estimated':True,'semanticFootprint':True,'qualityScore':25,'candidateBoundaryKind':'neighbourhood',
 'sourceYear':2017,'sourcePage':28,'sourceMapCharacter':component['klass'],'sourceComponent':component['id'],
 'sourceUrl':URL,'source':{'url':URL,'path':PDF.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),'page':28,'imagePath':IMAGE.relative_to(ROOT).as_posix()},
 'nameEvidence':[{'name':name,'coordinates':label['geometry']['coordinates'],'url':p['source']['url']}],
 'namePointDistanceMetres':round(distance,1),'approximateAreaSquareMetres':round(component['eov'].area,1),
 'approximationNote':'Actual coloured municipal character-map surface traced by colour mask, two-pixel crack closing and one-pixel simplification. The nearby locality point assigns its name; this is not a published quarter-name boundary. Full municipality extent registration in EOV is rough, so point need not be inside. No circles or point-generated hulls.'}
 output.append({'type':'Feature','properties':props,'geometry':mapping(geo)});assignments.append({'name':name,'component':component['id'],'distanceMetres':round(distance,1),'areaSquareMetres':round(component['eov'].area,1)})
# The map explicitly names the discontinuous rural character class as one group.
rural=[c['eov'] for c in components if c['klass']=='Bokortanyák']
if rural:
 geometry=unary_union(rural);geo=transform(inv,geometry)
 props={'name':'Bokortanyák','municipality':'Nyíregyháza','method':'source_map_footprint_inference','estimated':True,'semanticFootprint':True,'qualityScore':25,'candidateBoundaryKind':'planning_unit','sourceYear':2017,'sourcePage':28,'sourceUrl':URL,
 'source':{'url':URL,'path':PDF.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),'page':28},
 'approximationNote':'Union of all mapped surfaces in the official character category Bokortanyák. A discontinuous search group of printed rural surfaces, not the full area of every individual farm quarter. Approximate map placement and raster contour extraction.'}
 output.append({'type':'Feature','properties':props,'geometry':mapping(geo)})
assert all(shape(f['geometry']).is_valid for f in output)
(OUT/'nyir-character-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':output},ensure_ascii=False,separators=(',',':'))+'\n')
(OUT/'nyir-character-components.geojson').write_text(json.dumps({'type':'FeatureCollection','coordinateSpace':'Native image pixels, NOT geographic','features':[{'type':'Feature','properties':{'id':c['id'],'klass':c['klass'],'pixelCount':c['pixels']},'geometry':mapping(c['native'])} for c in components]},ensure_ascii=False,separators=(',',':'))+'\n')
(OUT/'nyir-character-summary.json').write_text(json.dumps({'featureCount':len(output),'sourceComponents':len(components),'assignments':assignments,'sourceFramePixels':frame,'municipalityEovExtent':[ex0,ey0,ex1,ey1],'circleCount':0,'method':'municipal_character_colour_surface_with_inferred_local_name','sourceImageSha256':hashlib.sha256(IMAGE.read_bytes()).hexdigest()},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'count':len(output),'assignments':assignments},ensure_ascii=False))
