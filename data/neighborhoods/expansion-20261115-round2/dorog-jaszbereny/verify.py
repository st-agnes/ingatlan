#!/usr/bin/env python3
"""Check the frozen packet geometry, identities, source-address extent and rebuild."""
import gzip,hashlib,json,subprocess,sys,unicodedata
from pathlib import Path
from shapely.geometry import shape
H=Path(__file__).resolve().parent
def load(name):
 b=(H/name).read_bytes();return json.loads(gzip.decompress(b) if name.endswith('.gz') else b)
def norm(x):return ''.join(v for v in unicodedata.normalize('NFKC',x).casefold() if v.isalnum()).replace('miklós','')
def main():
 names=['features.geojson','dorog-features-v2.geojson','jaszbereny-features.geojson']
 before={n:hashlib.sha256((H/n).read_bytes()).hexdigest() for n in names}
 subprocess.run([sys.executable,str(H/'build.py')],check=True)
 assert before=={n:hashlib.sha256((H/n).read_bytes()).hexdigest() for n in names},'Offline rebuild changed frozen geometry bytes'
 features=load('features.geojson')['features'];targets=load('baseline-targets.json')['targets'];keys={(f['properties']['municipality'],f['properties']['name']) for f in features}
 assert len(features)==len(keys)==17
 assert keys=={(t['municipality'],t['name']) for t in targets}
 assert all(shape(f['geometry']).is_valid and f['geometry']['type'] in ['Polygon','MultiPolygon'] for f in features)
 assert all(f['properties']['estimated'] and f['properties']['lowConfidence'] and not f['properties']['pointRadiusFallback'] for f in features)
 addresses=load('source-addresses.geojson.gz')['features'];checks=[]
 for f in load('dorog-features-v2.geojson')['features']:
  p=f['properties'];g=shape(f['geometry'])
  rows=[a for a in addresses if a['properties']['municipality']=='Dorog' and norm(a['properties']['tags'].get('addr:street',''))==norm(p['name'])]
  hits=sum(g.covers(shape(a['geometry'])) for a in rows)
  checks.append({'name':p['name'],'sourceAddressCount':len(rows),'coveredAddressCount':hits})
  assert hits==len(rows),(p['name'],hits,len(rows))
 report={'scope':'Technical and source-address extent check; not official boundary or geographic precision validation','featureCount':len(features),'rebuildByteIdentical':True,'all17BaselineTargetsCovered':True,'allValid':True,'circleCount':0,'dorogAddressCount':sum(r['sourceAddressCount'] for r in checks),'dorogCoveredAddressCount':sum(r['coveredAddressCount'] for r in checks),'features':checks,'sha256':before}
 (H/'dorog-address-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ['features','sha256']},ensure_ascii=False))
if __name__=='__main__':main()
