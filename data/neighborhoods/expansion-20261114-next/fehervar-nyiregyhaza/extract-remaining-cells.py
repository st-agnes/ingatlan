#!/usr/bin/env python3
"""Rough child areas: covered parent labels do not invalidate an actual map cell."""
from pathlib import Path
import json,collections,unicodedata
from pyproj import Transformer
from shapely.geometry import shape,mapping
from shapely.ops import transform,unary_union,polygonize
from shapely.strtree import STRtree
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
TARGETS={
 'Székesfehérvár':['Almássytelep','Demkóhegy','Fecskepart','Feketehegy','Kadocsa','Királykút','Laguna Lakópark','Oncsatelep','Palotavárosi lakótelep','Papagáj-telep','Szedreskert','Sóstó','Tóváros','Velinszky László-lakótelep','Ősz utca'],
 'Nyíregyháza':['Báthory-lakópark','Cúgosrész I.','Fáklyás lakópark','Green City lakópark','Ipari park','Jókaitelep','Kerti lak','Kun lakópark','Sóstóhegyi lakópark','Tópart','Ókistelekiszőlő','Újkistelekiszőlő','Őzdomb-lakókert']}
load=lambda name:json.loads((OUT/name).read_text());norm=lambda s:''.join(c for c in unicodedata.normalize('NFC',s).casefold() if c.isalnum())
to_eov=Transformer.from_crs(4326,23700,always_xy=True).transform;to_geo=Transformer.from_crs(23700,4326,always_xy=True).transform
labels=load('source-labels.geojson')['features'];barriers=load('source-barriers.geojson')['features'];municipalities={f['properties']['name']:f for f in load('source-municipalities.geojson')['features']};native=load('fehervar-native-features.geojson')['features'][:13]
all_candidates=[];reports=[]
for city,wanted in TARGETS.items():
 local=[f for f in labels if f['properties']['municipality']==city and f['properties']['name'] in wanted]
 points=[transform(to_eov,shape(f['geometry'])) for f in local];tree=STRtree(points)
 roads=[]
 for f in barriers:
  if city not in f['properties']['municipalities']:continue
  roads.append((f,transform(to_eov,shape(f['geometry']))))
 network_tree=STRtree([g for f,g in roads])
 parents=[(f['properties']['name'],transform(to_eov,shape(f['geometry'])),f['properties']) for f in native] if city=='Székesfehérvár' else [('Nyíregyháza közigazgatási területe',transform(to_eov,shape(municipalities[city]['geometry'])),None)]
 seen_parents=collections.Counter()
 for level in ['major','local']:
  for parent_name,parent,source in parents:
   indices=[int(i) for i in network_tree.query(parent,predicate='intersects')]
   used=[]
   for i in indices:
    tags=roads[i][0]['properties']['source']['tags']
    if level=='local' or tags.get('highway') in ['motorway','trunk','primary','secondary','tertiary'] or tags.get('railway') or tags.get('waterway'):used.append(i)
   lines=[parent.boundary]+[roads[i][1].intersection(parent) for i in used]
   cells=list(polygonize(unary_union([g for g in lines if not g.is_empty])))
   for cell in cells:
    if not parent.covers(cell.representative_point()):continue
    if not 1500<=cell.area<=3_000_000:continue
    hits=[int(i) for i in tree.query(cell,predicate='covers')]
    names={local[i]['properties']['name'] for i in hits}
    if len(names)!=1:continue
    name=next(iter(names));label=local[hits[0]]
    is_small=label['properties'].get('place')=='neighbourhood' or any(word in name.casefold() for word in ['lakópark','lakótelep','lakónegyed','lakókert']) or name in ['Tópart','Kerti lak','Ősz utca','Papagáj-telep']
    if is_small and cell.area>800_000:continue
    geo=transform(to_geo,cell)
    assert geo.is_valid and not geo.is_empty
    bounds=[]
    for i in used:
     if cell.boundary.intersection(roads[i][1]).length>15:
      original=roads[i][0];bounds.append({'id':original['id'],'name':original['properties'].get('name'),'url':original['properties']['source']['url']})
    if not bounds:continue
    props={'name':name,'municipality':city,'method':'physical_barrier_cell_estimate','estimated':True,'semanticFootprint':True,'qualityScore':18 if source else 12,'candidateBoundaryKind':'neighbourhood',
     'networkLevel':level,'mapParent':parent_name,'approximateAreaSquareMetres':round(cell.area,1),'boundingSourceWays':bounds,
     'sourceUrl':source['sourceUrl'] if source else label['properties']['source']['url'],
     'source':source['source'] if source else {'provider':'osm-street-map-inference','path':(OUT/'source-barriers.geojson').relative_to(ROOT).as_posix(),'pbfSha256':roads[used[0]][0]['properties']['source']['pbfSha256'],'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},
     'nameEvidence':[{'name':name,'coordinates':label['geometry']['coordinates'],'url':label['properties']['source']['url']}],
     'approximationNote':'A closed actual-road/rail/water map cell containing one still-missing target name. Already covered broader parent labels are allowed in the cell, since subdivision levels overlap. Fehérvár is clipped to an actually printed municipal quarter outline. The cell can be a partial block or broad approximation, not an observed complete quarter border. No radius, Voronoi, point-generated hull, invented citywide extent, or nearest-point split.'}
    all_candidates.append({'type':'Feature','properties':props,'geometry':mapping(geo)})
   seen_parents[level]+=len(cells)
 reports.append({'municipality':city,'targetNames':wanted,'sourceCellsByNetworkLevel':dict(seen_parents)})
selected={}
for f in all_candidates:
 p=f['properties'];key=p['municipality'],p['name'];rank=(0 if p['networkLevel']=='major' else 1,-p['approximateAreaSquareMetres'])
 if key not in selected or rank<selected[key][0]:selected[key]=(rank,f)
features=[v[1] for k,v in sorted(selected.items())]
for i,f in enumerate(features):f['id']='next-feh-nyir-remaining:'+str(i)
(OUT/'remaining-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
summary={'featureCount':len(features),'municipalities':dict(collections.Counter(f['properties']['municipality'] for f in features)),'sourceCellCandidates':len(all_candidates),'names':{city:[f['properties']['name'] for f in features if f['properties']['municipality']==city] for city in TARGETS},'unresolvedNames':{city:[n for n in wanted if (city,n) not in selected] for city,wanted in TARGETS.items()},'sourceProcessing':reports,'circleCount':0,'validGeometryCount':len(features)}
(OUT/'remaining-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False),flush=True)
