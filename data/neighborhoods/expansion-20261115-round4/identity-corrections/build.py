#!/usr/bin/env python3
"""Replay two explicitly reviewed identity/display corrections without frozen edits."""
import argparse,copy,hashlib,json
from pathlib import Path
from shapely.geometry import shape
H=Path(__file__).resolve().parent;ROOT=H.parents[3]
def packed(d):return (json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def build():
 pins=json.loads((H/'input-pins.json').read_text())
 for row in pins['inputs']:assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256'],row['path']
 declarations=json.loads((H/'verified-aliases.json').read_text())['aliases'];out=[]
 specs=[('shard-1','Dombóvár','Szuhay-domb','Szuhajdomb','dombovar-szuhajdomb'),('shard-4','Kecskemét','Bordás','Borbás belterület','kecskemet-borbas-belterulet')]
 for shard,city,old,new,suffix in specs:
  path=H.parent/shard/'features.geojson';f=copy.deepcopy(next(f for f in json.loads(path.read_text())['features'] if f['properties']['municipality']==city and f['properties']['name']==old));p=f['properties'];decl=next(d for d in declarations if d['municipality']==city and d['name']==new)
  originalId=f.get('id');f['id']='round4:identity-correction:'+suffix;p['name']=new;p['aliases']=decl['aliases'];p['qualityScore']=p.get('qualityScore',20)+1
  p['identityCorrection']={'originalPacket':path.relative_to(ROOT).as_posix(),'originalFeatureId':originalId,'originalName':old,'canonicalName':new,'reason':decl['reason'],'evidence':decl['evidence'],'inputPins':'data/neighborhoods/expansion-20261115-round4/identity-corrections/input-pins.json','geometryUnchanged':True,'priorityChange':'qualityScore +1, same existing method and uncertainty','notEquivalentToBroadParent':city=='Kecskemét'}
  assert shape(f['geometry']).is_valid and not shape(f['geometry']).is_empty;assert p['estimated'] is True and p['lowConfidence'] is True;out.append(f)
 out.sort(key=lambda f:(f['properties']['municipality'],f['properties']['name']));raw=packed({'type':'FeatureCollection','features':out})
 summary={'schemaVersion':1,'status':'frozen_reviewed_identity_corrections','featureCount':2,'geometryChanges':0,'allLowConfidence':True,'newSpatialAreas':0,'canonicalIdentityCorrections':2,'featuresSha256':hashlib.sha256(raw).hexdigest(),'aliasesFile':'verified-aliases.json','inputPins':pins}
 return {'features.geojson':raw,'summary.json':(json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode()}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();files=build()
 for name,raw in files.items():
  if a.check:assert (H/name).read_bytes()==raw,('stale output',name)
  else:(H/name).write_bytes(raw)
 print(json.dumps({'checked':a.check,'featureCount':2,'featuresSha256':hashlib.sha256(files['features.geojson']).hexdigest()}))
