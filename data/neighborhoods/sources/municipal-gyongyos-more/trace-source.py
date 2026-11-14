import json, numpy as np, heapq
from pathlib import Path
from PIL import Image,ImageDraw
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString,Polygon
im=np.array(Image.open('data/neighborhoods/sources/municipal-gyongyos-more/source-map.jpeg')).astype(float)
# Full visible cartographic lines, traced independently of contemporary street geometry.
# Common boundary nodes and paths are reused in opposite orientation.
edges={
 'blue_outer':[[305,322],[317,287],[357,223],[367,204],[393,173],[412,116],[434,75],[441,74]],
 'blue_green':[[441,74],[428,119],[416,165],[404,208],[390,258],[398,261],[406,267],[413,277],[421,299]],
 'blue_core':[[421,299],[404,302],[389,302],[370,300],[365,314],[363,333],[350,329],[335,324],[318,321],[305,322]],
 'purple_outer':[[357,223],[348,228],[329,252],[278,245],[270,274],[272,293],[261,302],[249,315],[242,333],[228,337],[217,375],[207,414],[195,455],[208,462],[201,487],[194,514],[260,518],[256,541],[250,562],[235,595],[244,605]],
 'purple_south':[[244,605],[264,568],[284,533],[296,499],[305,467]],
 'purple_core':[[305,467],[283,463],[287,423],[292,380],[298,345],[305,322]],
 'core_green':[[421,299],[428,318],[440,342]],
 'core_yellow':[[440,342],[451,333],[485,342],[472,353],[462,364],[470,375],[458,396],[453,419],[412,419],[397,420],[385,425],[378,438],[375,454],[355,460],[338,468]],
 'core_south':[[338,468],[320,468],[305,467]],
 'yellow_green':[[440,342],[460,321],[481,296],[500,273],[507,243],[521,219],[540,187]],
 'yellow_outer':[[540,187],[551,192],[538,231],[527,275],[530,295],[535,319],[529,337],[526,348],[529,377],[536,420],[560,446],[589,470],[618,494],[646,516],[666,530],[622,527],[587,525]],
 'yellow_south':[[587,525],[546,520],[515,521],[494,522],[492,557],[488,620],[460,615],[425,607],[385,599],[387,553],[388,523],[401,517],[403,497],[405,478],[379,475],[354,472],[338,468]],
 'south_outer':[[244,605],[221,653],[201,691],[187,715],[205,741],[242,741],[278,741],[302,717],[350,719],[411,721],[480,722],[484,698],[487,678],[511,678],[529,661],[542,637],[535,622],[529,602],[539,602],[546,623],[566,638],[580,669],[591,665],[606,688],[625,719],[646,768],[629,784],[629,824],[628,858],[646,873],[659,905],[684,897],[710,886],[715,856],[709,832],[700,800],[697,773],[700,737],[678,708],[657,683],[636,661],[613,640],[594,635],[576,631],[567,611],[556,584],[555,575],[578,562],[576,548],[581,535],[587,525]]
}
# Pixel center line samples: path search stays at most five pixels from each manually read segment.
# Bright neutral cartographic ink is preferred; no geographic or map-frame connector exists.
gray=im.min(2); neutral=im.max(2)-gray
ink=(gray>110)&(neutral<85)
path_out={}
def snap(pt,r=3):
 x,y=pt; a=[]
 for yy in range(max(0,y-r),min(im.shape[0],y+r+1)):
  for xx in range(max(0,x-r),min(im.shape[1],x+r+1)):
   a.append(((xx-x)**2+(yy-y)**2-(min(im[yy,xx])-neutral[yy,xx]*.3)/38,(xx,yy)))
 return min(a)[1]
# preserve shared endpoint snapping exactly
snaps={tuple(p):snap(p) for v in edges.values() for p in v}
for p in edges['blue_outer'][1:-1]:
 if not any(p in v for k,v in edges.items() if k!='blue_outer'):snaps[tuple(p)]=snap(p,7)
for key,points in edges.items():
 out=[]
 for pa,pb in zip(points,points[1:]):
  a,b=snaps[tuple(pa)],snaps[tuple(pb)]
  x0=max(0,min(a[0],b[0])-15);x1=min(im.shape[1],max(a[0],b[0])+16)
  y0=max(0,min(a[1],b[1])-15);y1=min(im.shape[0],max(a[1],b[1])+16)
  Y,X=np.mgrid[y0:y1,x0:x1]; dx=b[0]-a[0];dy=b[1]-a[1]
  f=np.clip(((X-a[0])*dx+(Y-a[1])*dy)/(dx*dx+dy*dy),0,1)
  dist=np.hypot(X-a[0]-f*dx,Y-a[1]-f*dy)
  penalty=1+((255-gray[y0:y1,x0:x1])/55)**2+neutral[y0:y1,x0:x1]/40+.03*dist
  costs={a:0};prev={};q=[(0,a)]
  while q:
   c,p=heapq.heappop(q)
   if c!=costs[p]:continue
   if p==b:break
   for ox,oy in [(0,1),(0,-1),(1,0),(-1,0)]:
    n=(p[0]+ox,p[1]+oy)
    if not(x0<=n[0]<x1 and y0<=n[1]<y1) or dist[n[1]-y0,n[0]-x0]>(13 if key=='blue_outer' else 5):continue
    nc=c+penalty[n[1]-y0,n[0]-x0]*(1.414 if ox and oy else 1)
    if nc<costs.get(n,1e100):costs[n]=nc;prev[n]=p;heapq.heappush(q,(nc,n))
  assert b in costs,(key,pa,pb)
  chain=[b]
  while chain[-1]!=a:chain.append(prev[chain[-1]])
  chain.reverse();out+=chain if not out else chain[1:]
 path_out[key]=out
polys={
 'Észak-nyugati városrész':[('blue_outer',1),('blue_green',1),('blue_core',1)],
 'Nyugati városrész':[('purple_outer',1),('purple_south',1),('purple_core',1),('blue_outer',1)],
 'Városközpont':[('blue_core',-1),('core_green',1),('core_yellow',1),('core_south',1),('purple_core',1)],
 'Keleti városrész':[('yellow_green',1),('yellow_outer',1),('yellow_south',1),('core_yellow',-1)],
 'Déli városrész':[('purple_south',-1),('south_outer',1),('yellow_south',1),('core_south',1)]
}
# Fix polygon chains explicitly (joining only the same shared endpoint; no closure connector).
# Purple needs blue outer only from lower sharedpoint to upper purplepoint.
bo=path_out['blue_outer'];stop=min(range(len(bo)),key=lambda i:(bo[i][0]-snaps[(357,223)][0])**2+(bo[i][1]-snaps[(357,223)][1])**2)
path_out['purple_blue']=bo[:stop+1]; path_out['blue_outer']=bo
polys['Nyugati városrész']=[('purple_outer',1),('purple_south',1),('purple_core',1),('purple_blue',1)]
# yellow-south ends at core-south's start338,468; south ring must reverse core-south to get305,467.
polys['Déli városrész']=[('purple_south',-1),('south_outer',1),('yellow_south',1),('core_south',1)]
records=[];preview=Image.fromarray(im.astype('uint8')).convert('RGB');d=ImageDraw.Draw(preview)
for idx,(name,parts) in enumerate(polys.items()):
 ring=[]
 for k,direction in parts:
  chain=path_out[k][::direction]
  if ring:assert ring[-1]==chain[0],(name,k,ring[-1],chain[0])
  ring+=chain if not ring else chain[1:]
 assert ring[0]==ring[-1],name
 p=Polygon(ring)
 print(name,p.is_valid,len(ring),p.area,p.is_simple)
 d.line(ring,fill=['yellow','cyan','white','magenta','lime'][idx],width=1)
 records.append({'name':name,'manualGuideEdges':[{'edgeId':k,'direction':di} for k,di in parts],'pixelRing':ring,'geometryValidInPixels':p.is_valid})
from shapely.ops import unary_union,polygonize
from shapely.geometry import Point
faces=list(polygonize(unary_union([LineString(v) for v in path_out.values()])))
seeds={'Észak-nyugati városrész':[350,280], 'Nyugati városrész':[250,400], 'Városközpont':[350,390], 'Keleti városrész':[460,475], 'Déli városrész':[350,610]}
for r in records:
 selected=[p for p in faces if p.contains(Point(seeds[r['name']]))]
 assert len(selected)==1,(r['name'],len(selected))
 p=selected[0];r['pixelRing']=[list(c) for c in p.exterior.coords];r['geometryValidInPixels']=p.is_valid;r['sourcePixelHoles']=[[list(c) for c in ring.coords] for ring in p.interiors];r['pixelSeed']=seeds[r['name']]
 print(r['name'],'polygonized',p.is_valid,p.area,len(r['pixelRing']))
Path('data/neighborhoods/sources/municipal-gyongyos-more/source-contours.json').write_text(json.dumps({'sourceImageSize':[809,933],'method':'Manual full visible boundary guide, then constrained bright cartographic ink tracing within 5 guide pixels, or 13 for the blue west line; observed ink support is recorded separately; no geographic completion, no frame closure. Coordinates refer to source pixel centers.','manualGuides':edges,'sharedInkPaths':path_out,'regions':records},ensure_ascii=False,indent=2)+'\n')
preview.save('/tmp/gyongyos-trace-preview.png')
