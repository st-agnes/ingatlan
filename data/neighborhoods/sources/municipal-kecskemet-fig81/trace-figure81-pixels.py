"""Trace source pixels; label-overprinted sections are explicit inferred candidates.

Most paths use literal black (maxRGB <= 45) pixels. Two narrowly recorded blue
label windows additionally admit actual dark-blue source pixels following the
visually interpreted boundary continuation. These do not establish a literal
black boundary under the label and MUST remain in the separate estimate layer.
No clipped image-frame corner is reconstructed.
"""
import json,math,heapq
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from shapely.geometry import Polygon
from shapely.validation import explain_validity
P=Path(__file__).resolve().parent
image=Image.open(P/'page175-xref216.jpeg').convert('RGB');rgb=np.asarray(image);value=rgb.max(axis=2);height,width=value.shape
A=(662,194);B=(911,393);C=(979,453);D=(1066,536);E=(1171,624);F=(1092,887);G=(962,798);H=(857,750);I=(743,694);J=(573,622);K=(441,480);L=(1003,600)
SECTIONS={
'AB':[A,(672,206),(690,236),(710,257),(744,289),(779,306),(820,327),(875,365),B],
'BC':[B,(935,414),(958,434),C],
'CD':[C,(1007,480),(1035,508),D],
'DE':[D,(1094,560),(1122,585),(1153,611),E],
'EF':[E,(1170,653),(1161,695),(1149,736),(1132,775),(1128,783),(1115,810),(1105,834),(1100,850),(1096,870),F],
'FG':[F,(1057,859),(1016,831),(985,812),G],
'GH':[G,(926,781),(890,765),H],
'HI':[H,(819,732),(784,715),I],
'IJ':[I,(697,674),(652,655),(607,636),J],
'JK':[J,K],
'KA':[K,(490,444),(516,402),(543,354),(570,311),(593,277),(600,265),(631,239),(648,220),A],
'BJ':[B,(886,418),(860,442),(829,473),(794,458),(764,442),(756,484),(729,502),(704,483),(678,526),(641,557),(609,591),J],
'CI':[C,(946,485),(903,532),(857,580),(820,619),(778,660),I],
'DL':[D,(1045,557),(1024,579),L],
'LH':[L,(976,630),(944,663),(913,694),(885,722),H],
'LG':[L,(1020,618),(1036,639),(1021,657),(1023,716),(1005,747),(984,773),G],
}
LIMIT=45;PAD=14;snaps={}
OVERPRINTS=[{'id':'I-II-label-crossing','box':[887,700,906,716],'visibleBlackAnchors':[[899,704],[890,712]],'maxLuminance':45,'maxExpectedStrokeDistancePixels':1.75},{'id':'I-Villanegyed-label-crossing','box':[1016,698,1030,720],'visibleBlackAnchors':[[1022,700],[1023,719]],'maxLuminance':45,'maxExpectedStrokeDistancePixels':1.75}]
luminance=rgb[:,:,0]*.299+rgb[:,:,1]*.587+rgb[:,:,2]*.114
allowed=value<=LIMIT;cost_value=value.astype(float).copy()
for occlusion in OVERPRINTS:
 x0,y0,x1,y1=occlusion['box'];a,b=occlusion['visibleBlackAnchors'];dx,dy=b[0]-a[0],b[1]-a[1]
 for y in range(y0,y1+1):
  for x in range(x0,x1+1):
   t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)));off=math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)
   if off<=occlusion['maxExpectedStrokeDistancePixels'] and luminance[y,x]<=occlusion['maxLuminance'] and rgb[y,x,2]>max(rgb[y,x,0],rgb[y,x,1])+15:
    allowed[y,x]=True;cost_value[y,x]=luminance[y,x]

def snap(p):
 if p in snaps:return snaps[p]
 x,y=p;cs=[]
 for yy in range(max(0,y-9),min(height,y+10)):
  for xx in range(max(0,x-9),min(width,x+10)):
   if value[yy,xx]<=LIMIT:cs.append(((xx-x)**2+(yy-y)**2+float(value[yy,xx])*.01,(xx,yy)))
 if not cs:raise ValueError('No source black pixel near '+str(p))
 q=min(cs)[1];snaps[p]=q;return q
def dist_segment(p,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
 if not den:return math.hypot(p[0]-a[0],p[1]-a[1])
 t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den));return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
def path(a,b):
 lo=(max(0,min(a[0],b[0])-PAD),max(0,min(a[1],b[1])-PAD));hi=(min(width-1,max(a[0],b[0])+PAD),min(height-1,max(a[1],b[1])+PAD));best={a:0};back={};todo=[(0,a)]
 while todo:
  d,u=heapq.heappop(todo)
  if d!=best[u]:continue
  if u==b:break
  for dx,dy in[(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
   v=(u[0]+dx,u[1]+dy)
   if not(lo[0]<=v[0]<=hi[0]and lo[1]<=v[1]<=hi[1])or not allowed[v[1],v[0]]:continue
   off=dist_segment(v,a,b)
   if off>PAD:continue
   nd=d+math.hypot(dx,dy)*(1+float(cost_value[v[1],v[0]])*.04)+off*off*.001
   if nd<best.get(v,float('inf')):best[v]=nd;back[v]=u;heapq.heappush(todo,(nd,v))
 if b not in best:raise ValueError('Disconnected actual source black stroke '+str((a,b)))
 out=[b]
 while out[-1]!=a:out.append(back[out[-1]])
 return out[::-1]
paths={}
for key,seeds in SECTIONS.items():
 if key in ['DE','EF','FG']:continue
 cs=[]
 for a,b in zip(seeds,seeds[1:]):
  part=path(snap(a),snap(b));cs+=part if not cs else part[1:]
 paths[key]=cs
 if __name__=='__main__':print(key,len(cs))
def joined(parts):
 out=[]
 for key,rev in parts:
  cs=paths[key][::-1]if rev else paths[key]
  if out and out[-1]!=cs[0]:raise ValueError('Disconnected sections')
  out+=cs if not out else cs[1:]
 return out
RINGS={
'Belső-Máriahegy':joined([('AB',False),('BJ',False),('JK',False),('KA',False)]),
'Széchenyiváros III.':joined([('BC',False),('CI',False),('IJ',False),('BJ',True)]),
'Széchenyiváros II.':joined([('CD',False),('DL',False),('LH',False),('HI',False),('CI',True)]),
'Széchenyiváros I.':joined([('LH',False),('GH',True),('LG',True)]),
# Villanegyed omitted: its southeast corner is clipped by the source image.
}
if __name__=='__main__':
 preview=image.copy();draw=ImageDraw.Draw(preview)
 for color,(name,ring)in zip(['red','yellow','blue','orange','magenta'],RINGS.items()):
  g=Polygon(ring);print(name,'valid',g.is_valid,explain_validity(g),'pixels',len(ring),'area',g.area);draw.line(ring,fill=color,width=2)
 preview.save(P/'pixel-trace-preview.png')
 (P/'pixel-trace.json').write_text(json.dumps({'sourceImageSha256':'4d9d33cf34268d28653d0955b8619e515653b29cea59914397246eaa7589f1ec','threshold':LIMIT,'explicitBlueLabelInterpretationWindows':OVERPRINTS,'manualSeeds':SECTIONS,'snappedSeeds':[{'manual':a,'actualPixel':b}for a,b in snaps.items()],'paths':paths,'rings':RINGS},ensure_ascii=False,indent=2)+'\n')
