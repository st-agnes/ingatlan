import json,math,heapq
from collections import defaultdict
from pathlib import Path
F=json.load(open('data/neighborhoods/sources/municipal-offline-next/kecskemet-all-local-roads.geojson'))['features']
N={};ADJ=defaultdict(list);byname=defaultdict(set)
def metres(a,b):return math.hypot((a[0]-b[0])*76000,(a[1]-b[1])*111200)
for i,f in enumerate(F):
 p=f['properties'];t=p['source']['tags'];kind=t['highway']
 if kind in ['steps','footway','path','cycleway','corridor','platform','construction','proposed']:continue
 ids=p['source']['nodeRefs'];cs=f['geometry']['coordinates']
 for nid,c in zip(ids,cs): N[nid]=c;byname[p['name']].add(nid)
 for a,b in zip(ids,ids[1:]):
  d=metres(N[a],N[b]);ADJ[a].append((b,d,i));ADJ[b].append((a,d,i))
def path(a,b):
 target=byname[b];best={n:0 for n in byname[a]};todo=[(0,n) for n in byname[a]];heapq.heapify(todo);back={};end=None
 while todo:
  d,u=heapq.heappop(todo)
  if d!=best.get(u):continue
  if u in target:end=u;break
  for v,dist,ix in ADJ[u]:
   f=F[ix];t=f['properties']['source']['tags'];factor=4 if t['highway'] in ['service','living_street'] else 1
   nd=d+dist*factor
   if nd<best.get(v,float('inf')):best[v]=nd;back[v]=(u,ix,dist);heapq.heappush(todo,(nd,v))
 if end is None:return {'a':a,'b':b,'error':'disconnected'}
 seg=[];cs=[N[end]];u=end
 while u in back:
  prev,ix,dist=back[u];seg.append((ix,dist));cs.append(N[prev]);u=prev
 seg=seg[::-1];steps=[]
 for ix,d in seg:
  f=F[ix];name=f['properties']['name'];ident=f['id']
  if steps and steps[-1]['way']==ident:steps[-1]['lengthM']+=d
  else:steps.append({'name':name,'way':ident,'lengthM':d,'tags':f['properties']['source']['tags']})
 return {'a':a,'b':b,'lengthM':sum(x[1] for x in seg),'start':cs[-1],'end':cs[0],'steps':steps,'coordinates':cs[::-1]}
S={'Homoki-domb':['Széchenyi körút','Jókai utca','Hornyik János körút','Gáspár András körút','Petőfi Sándor utca','Mária körút'], 'Bethlenváros':['Bethlen körút','Rákóczi út','Koháry István körút','Jókai utca'], 'Rákócziváros':['Rákóczi út','Kuruc körút','Csongrádi út','Csányi János körút'], 'Kossuthváros':['Kossuth körút','Tizedes utca','Magyar utca','Batthyány utca','Horváth Döme körút','Mezei utca'], 'Városközpont':['Dobó István körút','Horváth Döme körút','Batthyány utca','Csányi János körút','Koháry István körút','Hornyik János körút','Gáspár András körút']}
D={}
for name,names in S.items():
 rows=[path(a,b) for a,b in zip(names,names[1:]+names[:1])];D[name]=rows
 print(name)
 for r in rows:
  if r.get('lengthM',0): print(r['a'],'->',r['b'],round(r['lengthM']),[(s['name'],s['way'],round(s['lengthM']))for s in r['steps']])
Path('data/neighborhoods/sources/municipal-offline-next/exploratory-connections.json').write_text(json.dumps(D,ensure_ascii=False,indent=2)+'\n')
