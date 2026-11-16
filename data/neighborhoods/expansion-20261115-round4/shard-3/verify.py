#!/usr/bin/env python3
"""Check a frozen batch and its byte-identical offline reconstruction."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from shapely.geometry import shape
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('batch');a=p.parse_args();d=H/a.batch
names=['features.geojson','validation.json','summary.json'];before={n:hashlib.sha256((d/n).read_bytes()).hexdigest() for n in names}
subprocess.run([sys.executable,str(H/'build.py'),a.batch],check=True)
assert before=={n:hashlib.sha256((d/n).read_bytes()).hexdigest() for n in names}
fs=json.loads((d/'features.geojson').read_bytes())['features'];keys={(f['properties']['municipality'],f['properties']['name']) for f in fs};assert len(keys)==len(fs)
assert all(shape(f['geometry']).is_valid and f['geometry']['type'] in ['Polygon','MultiPolygon'] for f in fs)
assert all(f['properties']['estimated'] and f['properties']['lowConfidence'] and not f['properties']['pointRadiusFallback'] for f in fs)
print(json.dumps({'batch':a.batch,'featureCount':len(fs),'uniqueNames':len(keys),'allValid':True,'byteIdenticalOfflineRebuild':True,'circleCount':0}))
