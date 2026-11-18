import json,math,heapq
from collections import defaultdict
from pathlib import Path
from shapely.geometry import Polygon,mapping
from shapely.validation import explain_validity
F=json.load(open('data/neighborhoods/sources/municipal-offline-next/kecskemet-all-local-roads.geojson'))['features']; D=json.load(open('data/neighborhoods/sources/municipal-offline-next/exploratory-connections.json'))
N={};ADJ=defaultdict(list);byname=defaultdict(set)
def metres(a,b):return math.hypot((a[0]-b[0])*76000,(a[1]-b[1])*111200)
for i,f in enumerate(F):
 p=f['properties'];t=p['source']['tags'];kind=t['highway']
 if kind in ['steps','footway','path','cycleway','corridor','platform','construction','proposed']:continue
 ids=p['source']['nodeRefs'];cs=f['geometry']['coordinates']
 for nid,c in zip(ids,cs): N[nid]=c;byname[p['name']].add(nid)
 for a,b in zip(ids,ids[1:]):
  d=metres(N[a],N[b]);ADJ[a].append((b,d,i));ADJ[b].append((a,d,i))
inv={tuple(c):n for n,c in N.items()}
def path(start,end,name):
 best={start:0};todo=[(0,start)];back={}
 while todo:
  d,u=heapq.heappop(todo)
  if d!=best.get(u):continue
  if u==end:break
  for v,dist,ix in ADJ[u]:
   f=F[ix];t=f['properties']['source']['tags'];nm=f['properties']['name'];factor=1 if nm==name else (3 if not nm else 100)
   nd=d+dist*factor
   if nd<best.get(v,float('inf')):best[v]=nd;back[v]=(u,ix,dist);heapq.heappush(todo,(nd,v))
 if end not in best:raise ValueError('disconnected')
 seg=[];cs=[N[end]];u=end
 while u!=start:
  prev,ix,dist=back[u];seg.append((ix,dist));cs.append(N[prev]);u=prev
 seg=seg[::-1];steps=[]
 for ix,d in seg:
  f=F[ix];nm=f['properties']['name'];ident=f['id']
  if steps and steps[-1]['way']==ident:steps[-1]['lengthM']+=d
  else:steps.append({'name':nm,'way':ident,'lengthM':d})
 return cs[::-1],steps
for name in ['Városközpont','Kossuthváros']:
 rows=D[name];coords=[];proof=[]
 for i,row in enumerate(rows):
  previous=rows[i-1];start=inv[tuple(previous['coordinates'][-1])];end=inv[tuple(row['coordinates'][0])];cs,steps=path(start,end,row['a']);coords+=cs if not coords else cs[1:];proof.append({'road':row['a'],'steps':steps});coords+=row['coordinates'][1:]
 g=Polygon(coords);print(name,g.is_valid,explain_validity(g),len(coords),g.area*8e9)
 print([(p['road'],[(s['name'],round(s['lengthM']))for s in p['steps']if s['name']!=p['road']])for p in proof])
 Path(f'data/neighborhoods/sources/municipal-offline-more/{name}-ordered-diagnostic.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':name,'proof':proof,'diagnosticOnly':True},'geometry':mapping(g)}]},ensure_ascii=False,indent=2)+'\n')
