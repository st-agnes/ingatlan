import json,math,heapq
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from shapely.geometry import Polygon,mapping
from shapely.validation import explain_validity
P=Path(__file__).resolve().parent
image=Image.open(P/'figure79-source.jpeg').convert('RGB');rgb=np.asarray(image);value=rgb.max(axis=2);height,width=value.shape
A=(1002,485);B=(1253,676);C=(1390,501);N=(1185,249);D=(1663,790);E=(849,1090)
SECTIONS={
'AB':[A,(1027,499),(1056,516),(1094,543),(1132,574),(1180,613),(1227,650),B],
'BC':[B,(1273,653),(1292,630),(1311,601),(1329,568),(1351,536),(1363,519),C],
'CD':[C,(1422,542),(1460,591),(1495,632),(1531,675),(1575,718),(1613,754),D],
'DE':[D,(1630,811),(1594,841),(1558,871),(1522,900),(1486,922),(1455,940),(1422,952),(1388,961),(1330,969),(1269,976),(1195,986),(1130,1009),(1081,1029),(1033,1052),(988,1070),(951,1080),(918,1085),(885,1089),E],
'EA':[E,(847,1045),(848,1000),(849,955),(853,909),(857,864),(864,819),(870,776),(879,730),(891,682),(905,638),(923,593),(947,549),(973,510),A],
'NC':[N,(1204,264),(1223,289),(1243,314),(1261,337),(1282,363),(1301,387),(1324,416),(1353,451),C],
'AN':[A,(1032,439),(1065,395),(1093,357),(1122,319),(1155,276),N]}
LIMIT=45;PAD=14
snaps={}
def snap(p):
 if p in snaps:return snaps[p]
 x,y=p;candidates=[]
 for yy in range(max(0,y-9),min(height,y+10)):
  for xx in range(max(0,x-9),min(width,x+10)):
   if value[yy,xx]<=LIMIT:candidates.append(((xx-x)**2+(yy-y)**2+float(value[yy,xx])*.01,(xx,yy)))
 if not candidates:raise ValueError('No sourceblackpixelnear '+str(p))
 q=min(candidates)[1];snaps[p]=q;return q
def dist_segment(p,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)));return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
def path(a,b):
 lo=(max(0,min(a[0],b[0])-PAD),max(0,min(a[1],b[1])-PAD));hi=(min(width-1,max(a[0],b[0])+PAD),min(height-1,max(a[1],b[1])+PAD));best={a:0};back={};todo=[(0,a)]
 while todo:
  d,u=heapq.heappop(todo)
  if d!=best[u]:continue
  if u==b:break
  for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
   v=(u[0]+dx,u[1]+dy)
   if not(lo[0]<=v[0]<=hi[0]and lo[1]<=v[1]<=hi[1])or value[v[1],v[0]]>LIMIT:continue
   offset=dist_segment(v,a,b)
   if offset>PAD:continue
   nd=d+math.hypot(dx,dy)*(1+float(value[v[1],v[0]])*.04)+offset*offset*.001
   if nd<best.get(v,float('inf')):best[v]=nd;back[v]=u;heapq.heappush(todo,(nd,v))
 if b not in best:raise ValueError('Sourceblackstrokeisdisconnected '+str((a,b)))
 out=[b]
 while out[-1]!=a:out.append(back[out[-1]])
 return out[::-1]
paths={}
for k,seeds in SECTIONS.items():
 cs=[]
 for a,b in zip(seeds,seeds[1:]):
  part=path(snap(a),snap(b));cs+=part if not cs else part[1:]
 paths[k]=cs;print(k,len(cs),'maxsourceRGB',max(int(value[y,x])for x,y in cs))
def joined(parts):
 out=[]
 for k,reverse in parts:
  cs=paths[k][::-1]if reverse else paths[k]
  if out and out[-1]!=cs[0]:raise ValueError('Disconnectedsections')
  out+=cs if not out else cs[1:]
 return out
I=joined([('AB',False),('BC',False),('CD',False),('DE',False),('EA',False)])
II=joined([('AN',False),('NC',False),('BC',True),('AB',True)])
R=json.load(open(P/'fine-map-review.json'));M=np.array(R['comparisonMethod']['matrixOriginalJpegColumnToWgs84'])
features=[]
for name,cs in [('Petőfiváros I.',I),('Petőfiváros II.',II)]:
 pg=Polygon(cs);print(name,pg.is_valid,explain_validity(pg),'areaPx',pg.area,'closed',cs[0]==cs[-1]);world=(np.c_[np.array(cs),np.ones(len(cs))]@M.T)[:,:2];g=Polygon(world)
 features.append({'type':'Feature','properties':{'name':name,'diagnosticOnly':True},'geometry':mapping(g)})
 draw=ImageDraw.Draw(image);draw.line(cs,fill='red' if name=='Petőfiváros I.' else 'yellow',width=2)
image.save(P/'raster-trace-preview.png')
(P/'raster-trace-diagnostic.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,indent=2)+'\n')
(P/'raw-pixel-trace.json').write_text(json.dumps({'thresholdMaxRgb':LIMIT,'manualSeeds':SECTIONS,'snappedManualSeeds':[{'manual':a,'sourcePixel':b}for a,b in snaps.items()],'sourceBlackPixelPaths':paths,'closedRings':{'Petőfiváros I.':I,'Petőfiváros II.':II}},ensure_ascii=False,indent=2)+'\n')
