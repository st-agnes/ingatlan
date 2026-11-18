#!/usr/bin/env python3
from pathlib import Path
import json,gzip,runpy
from shapely.geometry import shape,box
HERE=Path(__file__).resolve().parent
m=runpy.run_path(str(HERE/'render-context.py'));load=m['load'];render=m['render'];roads=load(HERE/'source-roads.geojson.gz');areas=load(HERE/'source-areas.geojson.gz')+load(HERE/'source-buildings.geojson.gz');points=load(HERE/'source-name-points.geojson')
targets={'denesmajor-context':([21.4146791,46.6557719],800),'varoserdo-context':([21.322545,46.7007122],700),'kincsestelep-context':([20.3069251,46.4346963],850),'malvyad-colony-context':([21.398084,46.702387],600),'ponyi-context':([19.8375264,48.1195244],550)}
for name,(c,r) in targets.items():
 bb=box(c[0]-.02,c[1]-.015,c[0]+.02,c[1]+.015)
 keep=lambda f:shape(f['geometry']).intersects(bb)
 render(name,c,r,[f for f in roads if keep(f)],[f for f in areas if keep(f)],points);print(name,flush=True)
