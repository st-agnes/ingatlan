"""Actual dark source-pixel cycles for two CAD/digit-occluded color silhouettes.

No missing-pixel connection is interpolated. Manual seeds constrain an8-neighbour
path on actual source pixels within3px of each manually identified outer stroke.
This is limited to the two specifically reviewed source components.
"""
import sys,heapq,math
from pathlib import Path
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image
from shapely.geometry import Polygon
OUT=Path(__file__).resolve().parent
RGB=np.asarray(Image.open(OUT/'kaposvar-p18-source.jpeg').convert('RGB'))
VALUES=RGB.max(axis=2)
MAX_RGB=165
PAD=3
SEEDS={
 '8-northeast':[(226,159),(234,153),(241,146),(245,152),(249,164),(249,180),(250,188),(257,193),(243,195),(227,198),(226,185),(223,170),(223,164),(226,159)],
 '9-north-tip':[(384,126),(399,125),(417,125),(415,137),(412,145),(391,154),(388,144),(384,126)],
}
def snap(point):
 x,y=point;choices=[]
 for yy in range(y-3,y+4):
  for xx in range(x-3,x+4):
   if VALUES[yy,xx]<=MAX_RGB:choices.append(((xx-x)**2+(yy-y)**2+float(VALUES[yy,xx])*.01,(xx,yy)))
 if not choices:raise ValueError('No actual dark source pixel near '+str(point))
 return min(choices)[1]
def distance_to_segment(p,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
 if not den:return math.dist(p,a)
 t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den))
 return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
def connected_path(a,b):
 minimum=(min(a[0],b[0])-PAD,min(a[1],b[1])-PAD);maximum=(max(a[0],b[0])+PAD,max(a[1],b[1])+PAD)
 best={a:0};previous={};todo=[(0,a)]
 while todo:
  cost,current=heapq.heappop(todo)
  if cost!=best[current]:continue
  if current==b:break
  for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
   q=(current[0]+dx,current[1]+dy)
   if not(minimum[0]<=q[0]<=maximum[0]and minimum[1]<=q[1]<=maximum[1])or VALUES[q[1],q[0]]>MAX_RGB:continue
   offset=distance_to_segment(q,a,b)
   if offset>PAD:continue
   candidate=cost+math.hypot(dx,dy)*(1+float(VALUES[q[1],q[0]])*.03)+offset*offset*.1
   if candidate<best.get(q,float('inf')):best[q]=candidate;previous[q]=current;heapq.heappush(todo,(candidate,q))
 if b not in best:raise ValueError('Actual source-dark stroke is disconnected '+str((a,b)))
 result=[b]
 while result[-1]!=a:result.append(previous[result[-1]])
 return result[::-1]
def extract():
 results={}
 for component,seeds in SEEDS.items():
  snapped=[snap(point)for point in seeds];ring=[];paths=[]
  for a,b in zip(snapped,snapped[1:]):
   part=connected_path(a,b);paths.append(part);ring+=part if not ring else part[1:]
  if ring[0]!=ring[-1]or not Polygon(ring).is_valid:raise ValueError('Source-dark cycle not explicitly closed and valid '+component)
  results[component]={'manualSeeds':seeds,'actualSourceDarkSeeds':snapped,'denseSourceDarkRing':ring,'sourceDarkPixelPaths':paths,
   'maximumAllowedSourceRgb':MAX_RGB,'searchCorridorPixels':PAD,'allPixelsActuallyWithinDarkThreshold':all(VALUES[y,x]<=MAX_RGB for x,y in ring),
   'allStepsActual8Neighbour':all(max(abs(a[0]-b[0]),abs(a[1]-b[1]))==1 for a,b in zip(ring,ring[1:])),
   'sourcePolygonAreaPixels':Polygon(ring).area,'sourcePixelColourEvidence':[{'pixel':[x,y],'rgb':RGB[y,x].tolist()}for x,y in ring]}
 return results
if __name__=='__main__':
 import json
 print(json.dumps({k:{'points':len(v['denseSourceDarkRing']),'area':v['sourcePolygonAreaPixels']}for k,v in extract().items()}))
