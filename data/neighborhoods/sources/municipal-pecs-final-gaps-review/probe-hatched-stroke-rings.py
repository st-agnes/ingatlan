#!/usr/bin/env python3
"""Bounded manual source-stroke route candidates, never geographic outputs."""
from pathlib import Path
import json,heapq,math,hashlib
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
from shapely.geometry import Polygon,Point,mapping
P=Path(__file__).resolve().parent;im=Image.open(P/'pecs-p63-density.jpeg').convert('RGB');rgb=np.array(im).astype(int);mask=((rgb.max(2)<200)&(rgb.max(2)-rgb.min(2)<110))|(rgb[:,:,0]<ndimage.median_filter(rgb[:,:,0],7)-16);labels,n=ndimage.label(~mask)
records=[('Murom',(752,289,810,350),[51,53,54],[(794,298),(790,303),(788,307),(789,310),(791,314),(794,318),(795,322),(795,324),(790,325),(784,325),(778,325),(773,326),(770,324),(765,325),(762,326),(760,330),(756,334),(756,337),(759,340),(762,343),(765,344),(768,342),(771,347),(773,348),(778,346),(785,344),(790,346),(795,345),(799,343),(802,340),(803,333),(802,327),(801,321),(801,316),(800,311),(798,305),(796,300),(794,298)]),('Köztemető',(476,628,527,691),[131,132,134,143,147],[(481,634),(489,633),(497,633),(499,634),(500,640),(501,646),(502,650),(506,652),(512,657),(515,660),(520,662),(519,668),(519,674),(517,680),(518,685),(512,685),(506,685),(500,686),(494,687),(488,687),(484,687),(483,678),(483,670),(482,661),(482,652),(481,644),(481,639),(481,634)])]
def route(start,end,box):
 q=[(0.,start)];cost={start:0.};prev={}
 while q:
  d,v=heapq.heappop(q)
  if d!=cost[v]:continue
  if v==end:
   path=[v]
   while v!=start:v=prev[v];path.append(v)
   return list(reversed(path))
  for dx,dy in [(0,1),(1,0),(0,-1),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]:
   w=(v[0]+dx,v[1]+dy)
   if not(box[0]<=w[0]<box[2]and box[1]<=w[1]<box[3])or not mask[w[1],w[0]]:continue
   nd=d+math.hypot(dx,dy)*(1+float(rgb[w[1],w[0]].mean())/1000)
   if nd<cost.get(w,float('inf')):cost[w]=nd;prev[w]=v;heapq.heappush(q,(nd,w))
 raise ValueError('No continuous original-stroke route')
outputs=[]
for name,box,expected,anchors in records:
 missing=[list(a)for a in anchors if not mask[a[1],a[0]]]
 if missing:print(name,'anchors_not_mask',missing);continue
 path=[];segments=[]
 for a,b in zip(anchors,anchors[1:]):
  seg=route(a,b,box);segments.append({'start':list(a),'end':list(b),'literalOriginalStrokePixels':[list(p)for p in seg]});path.extend(seg[:-1])
 path.append(path[0]);g=Polygon(path);actualids=sorted({int(labels[y,x])for y in range(box[1],box[3])for x in range(box[0],box[2])if labels[y,x]and g.contains(Point(x,y))});outside=[cid for cid in actualids if cid not in expected];cover={str(cid):{'containedPixelCenters':sum(g.contains(Point(x,y))for y,x in np.transpose(np.nonzero(labels==cid)).tolist()),'originalCellPixelCount':int((labels==cid).sum())}for cid in expected}
 r={'sourceName':name,'status':'candidate_manual_source_stroke_route_not_yet_independently_approved','sourceImage':'pecs-p63-density.jpeg','manualAnchors':[list(p)for p in anchors],'sourcePixelPath':[list(p)for p in path],'sourceSegmentProvenance':segments,'allPathPixelsAreOriginalDeclaredStroke':all(mask[y,x]for x,y in path),'allSuccessivePathPixels8Adjacent':all(max(abs(a[0]-b[0]),abs(a[1]-b[1]))==1 for a,b in zip(path,path[1:])),'repeatedNonClosingVertices':len(path[:-1])-len(set(path[:-1])),'shapelyPolygonValid':g.is_valid,'pixelArea':g.area,'expectedFragmentCoverage':cover,'otherFreeCellIdsInside':outside,'pixelGeometry':mapping(g),'claimedAbsoluteAccuracy':None,'geographicOutputCreated':False,'sourceWholeExtentApproved':False}
 crop=im.crop(box).resize(((box[2]-box[0])*10,(box[3]-box[1])*10),Image.Resampling.NEAREST);d=ImageDraw.Draw(crop);d.line([((x-box[0]) *10+5,(y-box[1])*10+5)for x,y in path],fill='#ff0000',width=2);crop.save(P/('manual-'+('murom'if name=='Murom'else'cemetery')+'-stroke-candidate.png'));outputs.append(r);print(name,'valid',g.is_valid,'repeat',r['repeatedNonClosingVertices'],'area',g.area,'other',outside,'coverage',cover)
out={'schemaVersion':1,'sourceImageSha256':hashlib.sha256((P/'pecs-p63-density.jpeg').read_bytes()).hexdigest(),'method':'Manually chosen original-mask outer-stroke landmark candidates linked by shortest adjacent original-mask pixel routes, without bridging unclassified pixels. Search only; whole-boundary semantics require separate visual audit. No geographic export, source mask modification or generic fill/repair.','records':outputs}
(P/'manual-hatched-stroke-candidates.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
