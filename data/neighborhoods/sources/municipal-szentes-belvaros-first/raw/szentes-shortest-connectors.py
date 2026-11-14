import json,heapq,math
from pathlib import Path
from pyproj import Transformer
OUT=Path(__file__).resolve().parent
F=json.loads((OUT/'szentes-local-lines.geojson').read_text())['features']
T=Transformer.from_crs(4326,23700,always_xy=True).transform
D={};G={};XY={};S={}
for f in F:
 p=f['properties'];s=p['source'];t=s['tags'];n=p['name']
 if 'highway' not in t:continue
 refs=s['nodeRefs'];cs=f['geometry']['coordinates'];S[s['osmId']]=f
 for ref,c in zip(refs,cs):XY[ref]=c
 for ref in refs:D.setdefault(n,set()).add(ref)
 for i,(a,b) in enumerate(zip(refs,refs[1:])):
  x1,y1=T(*cs[i]);x2,y2=T(*cs[i+1]);length=math.hypot(x2-x1,y2-y1)
  G.setdefault(a,[]).append((b,length,s['osmId'],n));G.setdefault(b,[]).append((a,length,s['osmId'],n))
report=[]
for a,b in [('Apponyi tér','Baross utca'),('Attila út','Koszta József utca'),('Szilfa utca','Vásárhelyi út')]:
 q=[(0,n)for n in D[a]];heapq.heapify(q);dist={n:0 for n in D[a]};prev={};end=None
 while q:
  cost,u=heapq.heappop(q)
  if cost!=dist[u]:continue
  if u in D[b]:end=u;break
  for v,l,w,n in G[u]:
   nc=cost+l
   if nc<dist.get(v,math.inf):dist[v]=nc;prev[v]=(u,w,n,l);heapq.heappush(q,(nc,v))
 if end is None:print('NO PATH',a,b);continue
 nodes=[end];edges=[]
 while end in prev:
  u,w,n,l=prev[end];edges.append({'wayId':w,'name':n,'lengthM':l,'fromRef':u,'toRef':end});nodes.append(u);end=u
 nodes.reverse();edges.reverse()
 row={'from':a,'to':b,'lengthM':sum(x['lengthM']for x in edges),'edges':edges,'coordinates':[XY[n]for n in nodes]};report.append(row)
 groups=[]
 for e in edges:
  if not groups or groups[-1]['wayId']!=e['wayId']:groups.append({'wayId':e['wayId'],'name':e['name'],'lengthM':0,'tags':S[e['wayId']]['properties']['source']['tags']})
  groups[-1]['lengthM']+=e['lengthM']
 print(a,'--',b,groups)
(OUT/'szentes-real-road-gap-alternatives.json').write_text(json.dumps({'method':'Shortest road graph path between explicit source-circuit features; alternatives diagnostic only, not automatically adopted as neighborhood boundary.','paths':report},ensure_ascii=False,indent=2)+'\n')
