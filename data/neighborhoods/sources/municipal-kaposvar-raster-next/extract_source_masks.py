"""Reproducible native-JPEG color-mask contours, explicitly approximate.

Fourteen contours follow classified source-pixel cell edges, not a hull/buffer.
Two reviewed CAD/digit-connected mask notches are replaced by actual connected
dark source-pixel outer cycles; those use integer source-pixel centres.
Only enclosed small label/CAD-ink holes are filled after visual review. White
exterior/rural gaps and separate source components are never bridged. These are
color-mask estimates of the drawn outline, not literal black-stroke tracing.
"""
import sys,importlib.util
from pathlib import Path
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import Polygon,box,mapping
from shapely.ops import unary_union
OUT=Path(__file__).resolve().parent
RANGES={'blue':(140,175),'green':(65,109),'red':(230,256),'lime':(35,65),
        'orange':(2,35),'purple':(175,230),'teal':(109,140)}
SEEDS=[
 ('1-main',1,'blue',(210,500)),('2-main',2,'green',(120,420)),
 ('3-main',3,'red',(205,440)),('4-main',4,'lime',(278,461)),
 ('5-main',5,'orange',(122,554)),('6-main',6,'purple',(250,601)),
 ('7-main',7,'teal',(352,567)),('8-main',8,'teal',(164,245)),
 ('8-northwest',8,'teal',(105,185)),('8-northeast',8,'teal',(238,174)),
 ('9-central',9,'orange',(351,332)),('9-northern',9,'orange',(330,224)),
 ('9-north-tip',9,'orange',(395,145)),('9-east',9,'orange',(490,477)),
 ('10-north',10,'green',(180,615)),('10-south',10,'green',(154,793)),
]

def rle(mask):
 result=[]
 for y,row in enumerate(mask):
  changes=np.diff(np.r_[False,row,False].astype(np.int8))
  runs=[[int(a),int(b)]for a,b in zip(np.flatnonzero(changes==1),np.flatnonzero(changes==-1))]
  if runs:result.append({'y':y,'xRunsHalfOpen':runs})
 return result

def compress(ring):
 pts=list(ring[:-1]);out=[]
 for i,b in enumerate(pts):
  a=pts[i-1];c=pts[(i+1)%len(pts)]
  if (b[0]-a[0])*(c[1]-b[1])==(b[1]-a[1])*(c[0]-b[0]):continue
  out.append(b)
 return out+[out[0]]

def cell_polygon(mask):
 rectangles=[box(x0-.5,row['y']-.5,x1-.5,row['y']+.5)
             for row in rle(mask)for x0,x1 in row['xRunsHalfOpen']]
 geometry=unary_union(rectangles)
 if geometry.geom_type!='Polygon' or not geometry.is_valid or geometry.interiors:
  raise ValueError('Selected filled source component is not one valid no-hole pixel-cell region')
 compressed=Polygon(compress(list(geometry.exterior.coords)))
 if not compressed.is_valid or compressed.symmetric_difference(geometry).area!=0 or compressed.area!=int(mask.sum()):
  raise ValueError('Pixel-cell conversion changed exact source-mask area')
 return compressed

def extract(saturation=35,value=80):
 image=Image.open(OUT/'kaposvar-p18-source.jpeg').convert('RGB')
 spec=importlib.util.spec_from_file_location('kaposvar_actual_dark_override',OUT/'trace_dark_overrides.py')
 dark_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(dark_module)
 dark_overrides=dark_module.extract()
 hsv=np.asarray(image.convert('HSV'));masks={};results=[];selected=set()
 for category,(lo,hi)in RANGES.items():
  mask=(hsv[:,:,0]>=lo)&(hsv[:,:,0]<hi)&(hsv[:,:,1]>=saturation)&(hsv[:,:,2]>=value)
  labels,count=ndimage.label(mask) # Four-neighbour native colored cell components.
  sizes=np.bincount(labels.ravel())
  masks[category]=(labels,sizes)
 for identifier,quarter,category,seed in SEEDS:
  labels,sizes=masks[category];x,y=seed;candidates=[]
  for yy in range(max(0,y-5),min(image.height,y+6)):
   for xx in range(max(0,x-5),min(image.width,x+6)):
    label=int(labels[yy,xx])
    if label and sizes[label]>=100:candidates.append(((xx-x)**2+(yy-y)**2,yy,xx,label))
  if not candidates:raise ValueError('No substantial actual colored source component at '+identifier)
  _,yy,xx,label=min(candidates)
  if(category,label)in selected:raise ValueError('Two component seeds select the same source footprint')
  selected.add((category,label));raw=labels==label;filled=ndimage.binary_fill_holes(raw);holes=filled&~raw
  hole_labels,count=ndimage.label(holes);hole_sizes=[int((hole_labels==i).sum())for i in range(1,count+1)]
  if any(z>130 for z in hole_sizes):raise ValueError('Unreviewed large interior source gap at '+identifier)
  mask_geometry=cell_polygon(filled);geometry=mask_geometry;override=dark_overrides.get(identifier)
  if override:
   original=Polygon(override['denseSourceDarkRing']);geometry=Polygon(compress(override['denseSourceDarkRing']))
   if not geometry.is_valid or original.symmetric_difference(geometry).area!=0:raise ValueError('Dark-source collinear compression changes actual pixel cycle')
  minx,miny,maxx,maxy=geometry.bounds
  if minx<1 or miny<1 or maxx>image.width-2 or maxy>image.height-2:
   raise ValueError('Source component touches image frame; no frame closure permitted')
  results.append({'componentId':identifier,'quarterNumber':quarter,'colorCategory':category,
                  'requestedSourceSeed':list(seed),'actualClassifiedSourceSeed':[xx,yy],
                  'sourceColorPixelCount':int(raw.sum()),'filledGraphicOverlayPixelCount':int(holes.sum()),
                  'graphicOverlayHoleAreasPixels':sorted(hole_sizes,reverse=True),
                  'pixelCellArea':mask_geometry.area,'sourceColorMaskRle':rle(raw),
                  'filledGraphicOverlayPixelsRle':rle(holes),'maskGeometry':mapping(mask_geometry),
                  'contourMethod':'actual_dark_source_pixel_cycle'if override else'color_mask_pixel_cell_boundary_estimate',
                  'outputCoordinateConvention':'integer_JPEG_pixel_centres'if override else'half_integer_classified_pixel_cell_edges',
                  'darkSourceOutlineOverride':override,'outputContourAreaPixels':geometry.area,'geometry':mapping(geometry)})
 return results

if __name__=='__main__':
 import json
 rs=extract();variants={name:extract(*params)for name,params in [('looser',(25,70)),('tighter',(45,95))]}
 for i,result in enumerate(rs):
  from shapely.geometry import shape
  g=shape(result['geometry']);diagnostics={}
  for name,other in variants.items():
   h=shape(other[i]['geometry']);diagnostics[name]={'area':h.area,'boundaryHausdorffPixels':g.boundary.hausdorff_distance(h.boundary),'symmetricDifferencePixelArea':g.symmetric_difference(h).area}
  print(result['componentId'],result['sourceColorPixelCount'],result['filledGraphicOverlayPixelCount'],len(g.exterior.coords),diagnostics)
