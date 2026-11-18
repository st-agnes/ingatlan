#!/usr/bin/env python3
"""Reconstruct cited Füzespark street triangle from preserved actual OSM lines."""
from pathlib import Path
import gzip,json
from shapely.geometry import shape,Point
from shapely.ops import unary_union,polygonize
H=Path(__file__).resolve().parent
rs=json.load(gzip.open(H/'source-roads.geojson.gz','rt'))['features']
sel=[f for f in rs if f['properties'].get('name') in ['Vasvári Pál utca','Sas utca','Szentlászlói út']]
cells=list(polygonize(unary_union([shape(f['geometry']) for f in sel])))
own=[g for g in cells if g.covers(Point(19.0680455,47.6743844))]
ring=list(own[0].simplify(.000025,preserve_topology=True).exterior.coords) if len(own)==1 else [[19.0604333,47.6773895],[19.0610085,47.6782274],[19.0635808,47.6775436],[19.0701861,47.6746412],[19.0681254,47.6727556],[19.0676857,47.6730523],[19.0619417,47.6763011],[19.0604333,47.6773895]]
f={'municipality':'Szentendre','name':'Füzespark lakótelep','ring':ring,'anchors':['Vasvári Pál utca','Sas utca','Szentlászlói út'],'urls':['https://or.njt.hu/onkormanyzati-rendelet/2025-25-SP-420']+[r['properties']['source']['url'] for r in sel],'note':'Source-defined municipal street triangle traced from preserved named road vertices. The short northwestern connection between the Vasvári and Szentlászlói road endpoints is an approximate manual link because the three named way groups alone do not form a closed cell. The legal text names this broad triangle Füzespark; it overlaps the smaller historical Vasvári estate retained separately. Street-centerline convention is an estimated search extent, not property boundaries. No boundary is generated from the label point.'}
(H/'fuzes-trace.json').write_text(json.dumps(f,ensure_ascii=False,indent=2)+'\n')
print('Füzespark source-road triangle',len(f['ring']),'vertices')
