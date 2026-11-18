#!/usr/bin/env python3
"""Retain all four source-map outlines in pixel space, without inventing georeferencing."""
from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import box,mapping
from shapely.ops import unary_union
HERE=Path(__file__).resolve().parent
source=HERE/'ozd-2015-p247-0.jpeg'
a=np.asarray(Image.open(source).convert('RGB')).astype(float);r,g,b=a[:,:,0],a[:,:,1],a[:,:,2]
masks={'Központi városrész':(b>r*1.15)&(b>g*1.12)&(b>100)&(r<190),
 'Keleti városrész':(r>190)&(g>100)&(g<205)&(b<145),
 'Északi városrész':(g>r*1.06)&(g>b*1.12)&(g>105)&(r>70),
 'Nyugati városrész':(r>145)&(r>g*1.35)&(r>b*1.1)&(b>g*1.12)&(b>80)}
# Exclude four coloured legends; these are labels rather than mapped territories.
legend_boxes=[(260,145,410,170),(25,390,185,418),(498,350,600,395),(395,445,585,480)]
features=[]
for name,mask in masks.items():
 for x0,y0,x1,y1 in legend_boxes: mask[y0:y1,x0:x1]=False
 mask=ndimage.binary_closing(mask,structure=np.ones((3,3)))
 labels,count=ndimage.label(mask);areas=np.bincount(labels.ravel());mask=np.isin(labels,np.flatnonzero(areas>200));mask[labels==0]=False
 # Small unreadable printed strokes are bridged; larger genuine uncoloured holes remain.
 holes=ndimage.binary_fill_holes(mask)&~mask;hlabels,_=ndimage.label(holes);hs=np.bincount(hlabels.ravel());mask|=np.isin(hlabels,np.flatnonzero((hs>0)&(hs<=40)))&(hlabels!=0)
 pieces=[]
 for y,row in enumerate(mask):
  edges=np.flatnonzero(np.diff(np.r_[False,row,False].astype(int)))
  pieces.extend(box(x0-.5,y-.5,x1-.5,y+.5) for x0,x1 in zip(edges[::2],edges[1::2]))
 geom=unary_union(pieces);assert geom.is_valid
 features.append({'type':'Feature','properties':{'municipality':'Ózd','name':name,'coordinateReferenceSystem':'NOT_GEOGRAPHIC_SOURCE_IMAGE_PIXELS','sourcePage':247,'sourceYear':2015,'nativePixelMaskConstruction':'Colour mask, 1px gap closing, components>200pixels; coloured legends excluded, holes<=40pixels filled. Not georeferenced; do not import into WGS84 application catalogue.','sourceImageSha256':hashlib.sha256(source.read_bytes()).hexdigest()},'geometry':mapping(geom)})
(HERE/'ozd-2015-native-pixel-polygons.geojson').write_text(json.dumps({'type':'FeatureCollection','coordinateReferenceSystem':'NOT_GEOGRAPHIC_PIXELS','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
print('Retained4source outlines in explicitnon-geographicpixelspace;notcandidateWGS84.')
