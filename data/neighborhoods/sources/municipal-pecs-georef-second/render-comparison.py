#!/usr/bin/env python3
from pathlib import Path
import json,os
os.environ['PROJ_NETWORK']='OFF'
from PIL import Image,ImageDraw,ImageFont
from pyproj import Transformer
P=Path(__file__).resolve().parent;Q=P.parent/'municipal-pecs-grounded-next'
d=json.loads((P/'source-target-topology-proof.json').read_text());im=Image.open(Q/'source-name-map.jpeg').convert('RGB');t=Transformer.from_crs(4326,23700,always_xy=True)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18);small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
out=Image.new('RGB',(1480,1340),'white');dr=ImageDraw.Draw(out)
dr.text((20,12),'Pecs source/current topology candidates - separate panels; NO registration or fit',fill='black',font=font)
def panel(y,title,box,paths,labels):
 dr.text((20,y),title,fill='black',font=font); src=im.crop(box);ratio=min(680/src.width,350/src.height);src=src.resize((round(src.width*ratio),round(src.height*ratio)),Image.Resampling.NEAREST);out.paste(src,(20,y+35))
 dr.text((20,y+391),f'Original JPEG crop {box}; nearest neighbour. No world overlay.',fill='black',font=small)
 pts=[p for _,xy in paths for p in xy];xs=[p[0]for p in pts];ys=[p[1]for p in pts];minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)
 scale=min(630/max(1,maxx-minx),320/max(1,maxy-miny));cx,cy=(minx+maxx)/2,(miny+maxy)/2
 def xy(p):return (1060+(p[0]-cx)*scale,y+205-(p[1]-cy)*scale)
 dr.rectangle((735,y+30,1460,y+385),outline='#888888',width=1)
 for col,coords in paths:
  dr.line([xy(p)for p in coords],fill=col,width=4)
  for p in coords:
   x,z=xy(p);dr.ellipse((x-2,z-2,x+2,z+2),fill=col)
 for p,name in labels:
  x,z=xy(p);dr.ellipse((x-6,z-6,x+6,z+6),outline='red',width=2);labelwidth=dr.textbbox((0,0),name,font=small)[2];tx=x+8 if x+8+labelwidth<1460 else x-8-labelwidth;dr.text((tx,z+3),name,fill='red',font=small)
 dr.text((745,y+391),'Current OSM, EOV north-up. Literal adjacent vertices; marker = candidate.',fill='black',font=small)
for row,i,box,title in [(55,457,(70,120,177,180),'L: visible image turn versus current ring457 (not old intermediate vertex455)'),(475,386,(250,45,355,103),'Trough: broad source blur versus current386 and its neighbouring small389 trough')]:
 c=next(c for c in d['boundaryCandidateContexts']if c['candidateRingVertexIndex']==i)
 labels=[(v['eov'],str(v['ringVertexIndex'])+' / '+str(v['osmNodeId']))for v in c['vertices']if v['ringVertexIndex']in ([455,457]if i==457 else [386,388,389])]
 panel(row,title,box,[('#777777',[v['eov']for v in c['vertices']])],labels)
# Eastern source crossing pair, with complete current road/rail pieces and actual boundary context.
nodes={n['osmNodeId']:n['coordinates']for n in d['rawReferencedNodes']};ways={w['osmWayId']:w for w in d['rawMemberAndCandidateWays']};boundary=json.loads((Q/'source-municipality.geojson').read_text())['geometry']['coordinates'][0][0]
def e(c):return list(t.transform(*c))
# Only display a selected whole vertex run, without manufacturing target endpoints.
coords=[e(c)for c in boundary];idx=[i for i,c in enumerate(coords)if 595900<c[0]<596950 and 85300<c[1]<86400]
run=coords[min(idx):max(idx)+1]
paths=[('#777777',run)]
for wid,col in [(312297473,'#c69d20'),(208759579,'#202020')]:
 paths.append((col,[e(nodes[n])for n in ways[wid]['nodeRefs']if 595900<e(nodes[n])[0]<597050 and 85300<e(nodes[n])[1]<86500]))
labels=[]
for c in d['computedFeatureCrossings']:
 if c['type']=='rail64-current-municipality-boundary':labels.append((c['computedIntersection']['eov'],'rail64 / boundary'))
 if c['type']=='road6-current-municipality-boundary'and c['roadSegment']['osmWayId']==312297473:labels.append((c['computedIntersection']['eov'],'road6 / boundary'))
panel(895,'East: gray/rail [~565,151], gray/yellow [~572,163]; no printed source feature references',(550,130,585,180),paths,labels)
dr.text((20,1320),'Source/current identities remain hypotheses. Claimed absolute accuracy = null; no quarter polygons or primary approval.',fill='black',font=small)
out.save(P/'source-current-separate-panels.png')
