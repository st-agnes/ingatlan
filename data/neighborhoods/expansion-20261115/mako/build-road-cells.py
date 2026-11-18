#!/usr/bin/env python3
"""Named representative fragments built from actual closed street/barrier circuits."""
from pathlib import Path
import gzip,json
from shapely.geometry import shape,Point,mapping
from shapely.ops import unary_union,polygonize,transform
from pyproj import Transformer
H=Path(__file__).resolve().parent
roads=json.loads(gzip.open(H/'source-roads.geojson.gz','rt').read())['features'];points={f['properties']['name']:f for f in json.loads(gzip.open(H/'source-points.geojson.gz','rt').read())['features']}
to_eov=Transformer.from_crs(4326,23700,always_xy=True);to_ll=Transformer.from_crs(23700,4326,always_xy=True)
selected=[]
for f in roads:
 p=f['properties'];tags=p.get('tags',{});kind=tags.get('highway')
 if kind in ['footway','path','steps','cycleway','track','construction','proposed']:continue
 if not(kind or tags.get('railway')or tags.get('waterway')):continue
 g=shape(f['geometry'])
 if g.geom_type=='LineString':selected.append((f,transform(to_eov.transform,g)))
cells=[g for g in polygonize(unary_union([g for f,g in selected]))if g.is_valid and 400<g.area<1500000]
all_lines=[(f,transform(to_eov.transform,shape(f['geometry'])))for f in roads if f['geometry']['type']=='LineString']
garden_cells=[g for g in polygonize(unary_union([g for f,g in all_lines]))if g.is_valid and 400<g.area<1500000]
names=['Bajcsy lakótelep','Ráday lakótelep','Ószentlőrinc','Újszentlőrinc','Református városrész','Középváros','Cédulaház','Vertán telep','Honvéd-telep']
features=[];unresolved=[]
for n in names:
 p=transform(to_eov.transform,Point(points[n]['geometry']['coordinates']));covers=[g for g in cells if g.covers(p)]
 circuit_lines=selected
 if not covers:
  covers=[g for g in garden_cells if g.covers(p)];circuit_lines=all_lines
 if not covers:unresolved.append(n);continue
 g=min(covers,key=lambda x:x.area);boundary=g.boundary
 refs=[f['properties']['osmWayId']for f,line in circuit_lines if boundary.intersection(line).length>1]
 roadnames=sorted({f['properties'].get('name')for f,line in circuit_lines if f['properties'].get('name')and boundary.intersection(line).length>1})
 note='Low-confidence representative street-bounded neighbourhood fragment selected by the existing locality name point from an actual closed road/rail/water circuit in the pinned OSM snapshot. Entire source circuit retained; no radius, arbitrary rectangle or parent city footprint generated from the point. Full conventional quarter extent remains unknown; this fragment may be smaller than the commonly understood neighbourhood. Source streets and neighbouring historical/municipal outlines provide physical context, with overlaps intentional.'
 if n=='Újszentlőrinc':note+=' This southern garden-area circuit includes literal tracks and footpaths as physical source edges; it is not a claim that the whole historical agricultural district was urban residential land.'
 if n=='Cédulaház':note+=' The municipal2021heritage study p16 identifies Mező/Szegfű and Justh Gyula/Honvéd street context for the historic locality.'
 if n=='Középváros':note+=' Municipal2021heritage p16 places the historic quarter between Kossuth and Vásárhelyi streets; this is one actual street circuit in that named area, not a reconstruction of its entire historic limit.'
 if n=='Református városrész':note+=' Municipal2021heritage p16 identifies the Reformed Szentlőrinc quarter and its expansion along Aradi utca.'
 features.append({'type':'Feature','properties':{'name':n,'municipality':'Makó','method':'actual_source_road_circuit_neighbourhood_fragment_estimate','estimated':True,'confidence':'low','qualityScore':10,'sourceUrl':points[n]['properties']['source']['url'],'sourceRoadFile':'source-roads.geojson.gz','sourceNamePoint':points[n]['geometry']['coordinates'],'sourceRoadIds':refs,'sourceRoadNames':roadnames,'sourceContextUrl':'https://mako.hu/wp-content/uploads/2021/12/06-oroksegvedelmi-hatastanulmany.pdf','sourceContextPage':16,'approximationNote':note,'radiusFallback':False,'semanticFootprint':True,'currentWholeQuarterExtentEstablished':False,'license':'ODbL-1.0','attribution':'© OpenStreetMap contributors'},'geometry':mapping(transform(to_ll.transform,g))})
(H/'road-cell-features.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},ensure_ascii=False,separators=(',',':'))+'\n')
(H/'road-cell-summary.json').write_text(json.dumps({'featureCount':len(features),'actualClosedCircuits':len(cells),'unresolvedNames':unresolved,'allEstimated':True,'wholeQuarterExtentEstablished':False},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'features':len(features),'unresolved':unresolved},ensure_ascii=False))
