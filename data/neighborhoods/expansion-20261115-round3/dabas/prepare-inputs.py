#!/usr/bin/env python3
"""Recreate retained local inputs from frozen round-2 evidence; no PBF or network."""
from pathlib import Path
import json,gzip,shutil,hashlib
H=Path(__file__).resolve().parent;R=H.parents[3];S=R/'data/neighborhoods/expansion-20261115-round2/pest-northwest'
# Locate repo independent of folder depth.
R=next(x for x in H.parents if (x/'AGENTS.md').exists());S=R/'data/neighborhoods/expansion-20261115-round2/pest-northwest'
origin={}
for n in ['source-roads.geojson.gz','source-surfaces.geojson.gz']:
 origin[n]={'path':str((S/n).relative_to(R)),'sha256':hashlib.sha256((S/n).read_bytes()).hexdigest()}
 j=json.load(gzip.open(S/n,'rt'));j['features']=[f for f in j['features'] if 'Dabas' in f['properties'].get('municipalities',[])]
 with gzip.GzipFile(filename=str(H/n),mode='wb',mtime=0) as f:f.write((json.dumps(j,ensure_ascii=False,separators=(',',':'))+'\n').encode())
 origin[n]['retainedFeatureCount']=len(j['features'])
for n in ['target-selection.json','source-municipalities.geojson','prior-polygons.geojson']:
 j=json.loads((S/n).read_text())
 if isinstance(j,list):j=[x for x in j if x['municipality']=='Dabas']
 else:j['features']=[f for f in j['features'] if f['properties'].get('municipality',f['properties'].get('name'))=='Dabas']
 (H/n).write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
for i in range(7,15):shutil.copy2(S/('context-%02d.png'%i),H/('context-%02d.png'%i))
j=[x for x in json.loads((S/'context-registration.json').read_text()) if x['municipality']=='Dabas'];(H/'context-registration.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
(H/'input-provenance.json').write_text(json.dumps({'date':'2026-11-15','baselineCommit':'9bfa534','sourceBaselineCommit':'3f6e793','sources':origin,'filter':'Dabas membership only; complete original way coordinates and properties unchanged, no clipping or generated geometry','countryPbfSha256':'224897876ea131bcf0cb420e789640402d63aabe5e1491785aa4fca813aa641a','osmSnapshotDate':'2026-11-12T21:23:05Z','license':'ODbL-1.0','attribution':'© OpenStreetMap contributors','attributionUrl':'https://www.openstreetmap.org/copyright','note':'The completed polygon build requires only local packet inputs. This helper is optional local source reacquisition; it does not rescan the country PBF.'},ensure_ascii=False,indent=2)+'\n')
