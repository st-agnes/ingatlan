#!/usr/bin/env python3
"""Infer missing local areas from actual progressively finer street/rail/water cells."""
from pathlib import Path
import json,gzip,hashlib,unicodedata
from collections import Counter
from shapely.geometry import shape,mapping
from shapely.ops import unary_union,polygonize,transform
from shapely.strtree import STRtree
from pyproj import Transformer

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];DATA=ROOT/'data/neighborhoods'
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
write=lambda file,obj:(HERE/file).write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n')
labels_path=HERE/'context-name-points.geojson'
if not labels_path.exists():
    labels=json.loads(gzip.decompress((DATA/'sources/country-osm/named-nodes.geojson.gz').read_bytes()))['features']
    write(labels_path.name,{'type':'FeatureCollection','features':[f for f in labels if f['properties'].get('municipality') in ['Debrecen','Kecskemét']]})
labels=json.loads(labels_path.read_text())['features']
targets_path=HERE/'missing-targets.json'
if not targets_path.exists():
    inv=json.loads((DATA/'expansion-20261114/inventory/known-names.json').read_text())['names']
    write(targets_path.name,{'targets':[{'municipality':r['municipality'],'name':r['name']} for r in inv if r['municipality'] in ['Debrecen','Kecskemét'] and not r['hasCollectedPolygon'] and r['hasKnownPoint']]})
targets={(r['municipality'],norm(r['name'])) for r in json.loads(targets_path.read_text())['targets']}
roads=json.loads((HERE/'context-roads.geojson').read_text())['features'];parents=json.loads((HERE/'context-municipalities.geojson').read_text())['features']
forward=Transformer.from_crs(4326,23700,always_xy=True).transform;inverse=Transformer.from_crs(23700,4326,always_xy=True).transform
features=[];stats=[];all_candidates=[]
for city in ['Debrecen','Kecskemét']:
    parent=transform(forward,shape(next(f for f in parents if f['properties']['name']==city)['geometry']))
    local=[f for f in labels if f['properties']['municipality']==city];points=[transform(forward,shape(f['geometry'])) for f in local];tree=STRtree(points)
    localroads=[f for f in roads if city in f['properties']['municipalities']]
    roadshapes=[transform(forward,shape(f['geometry'])).intersection(parent) for f in localroads];roadtree=STRtree(roadshapes)
    candidates=[]
    for level in range(3):
        indices=[]
        for i,f in enumerate(localroads):
            t=f['properties']['source']['tags'];kind=t.get('highway')
            accepted=kind in ['motorway','trunk','primary','secondary','tertiary','unclassified'] or t.get('railway') or t.get('waterway')
            if level>=1:accepted=accepted or kind=='residential'
            if level>=2:accepted=accepted or kind in ['service','living_street','track']
            if accepted and not roadshapes[i].is_empty:indices.append(i)
        cells=list(polygonize(unary_union([parent.boundary]+[roadshapes[i] for i in indices])))
        count=0
        for cell in cells:
            if cell.area<5_000 or cell.area>4_000_000 or not parent.covers(cell.representative_point()):continue
            hits=[int(i) for i in tree.query(cell,predicate='covers')]
            identities={(city,norm(local[i]['properties']['name'])) for i in hits}
            if len(identities)!=1:continue
            key=next(iter(identities))
            if key not in targets:continue
            label=local[hits[0]];name=label['properties']['name'];lower=name.casefold()
            minimum=5_000 if 'lakópark' in lower else 10_000 if 'lakótelep' in lower else 20_000
            if cell.area<minimum:continue
            cap=250_000 if 'lakópark' in lower else 750_000 if 'lakótelep' in lower else 4_000_000
            candidate={'city':city,'name':name,'level':level,'geometry':cell,'label':label,'areaCap':cap}
            nearby=[]
            for j in roadtree.query(cell.boundary):
                j=int(j);overlap=cell.boundary.intersection(roadshapes[j]).length
                if overlap>15:nearby.append({'id':localroads[j]['id'],'name':localroads[j]['properties']['name'],'url':localroads[j]['properties']['source']['url'],'boundaryLengthMetres':round(overlap,1)})
            candidate['bounds']=nearby;candidates.append(candidate);count+=1
        stats.append({'municipality':city,'level':level,'sourceWays':len(indices),'allCells':len(cells),'missingSingleNameCandidates':count})
        print(json.dumps(stats[-1]),flush=True)
    selected={}
    all_candidates.extend(candidates)
    for c in sorted(candidates,key=lambda x:-x['geometry'].area):
        if c['geometry'].area>c['areaCap']:continue
        selected.setdefault(norm(c['name']),c)
    for c in selected.values():
        geo=transform(inverse,c['geometry']);assert geo.is_valid
        p={'name':c['name'],'municipality':city,'method':'physical_barrier_cell_estimate','estimated':True,'semanticFootprint':True,
           'candidateBoundaryKind':'neighbourhood','qualityScore':15,'pointRadiusFallback':False,
           'sourceUrl':c['label']['properties']['source']['url'],'source':{'provider':'osm-street-cell-inference','path':str((HERE/'context-roads.geojson').relative_to(ROOT)),'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},
           'nameEvidence':c['label'],'sourceRoadLevel':c['level'],'boundingSourceWays':c['bounds'],'areaSquareMetres':round(c['geometry'].area,1),'coarseAreaCapSquareMetres':c['areaCap'],
           'sourceCandidateAlternativesPath':str((HERE/'all-road-cell-candidates.geojson').relative_to(ROOT)),
           'approximationNote':'Largest plausible actual street/rail/water/municipal-boundary cell containing one distinct named quarter point, from three road-detail levels, with housing-park candidates capped at0.25km² and housing-estate candidates at0.75km². This is a rough source-informed local search footprint, not an observed whole-quarter border. No radius, Voronoi or fitted hull. Street crossings and actual quarter extent can differ.'}
        features.append({'type':'Feature','id':'deb-kecs-road-cell:'+city+':'+norm(c['name']),'properties':p,'geometry':mapping(geo)})
write('road-cell-features.geojson',{'type':'FeatureCollection','features':features})
write('all-road-cell-candidates.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','properties':{'municipality':c['city'],'name':c['name'],'roadLevel':c['level'],'areaSquareMetres':round(c['geometry'].area,1),'areaCapSquareMetres':c['areaCap'],'excludedByEstateScale':c['geometry'].area>c['areaCap'],'boundingSourceWays':c['bounds']},'geometry':mapping(transform(inverse,c['geometry']))} for c in all_candidates]})
write('road-cell-summary.json',{'featureCount':len(features),'cities':dict(Counter(f['properties']['municipality'] for f in features)),'names':[f['properties']['name'] for f in features],'radiusFallbackCount':0,'steps':stats})
print(json.dumps({'featureCount':len(features),'names':[f['properties']['name'] for f in features]},ensure_ascii=False))
