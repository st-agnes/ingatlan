"""Freeze/check isolated Eger proposal files and immutable original inputs."""
import argparse,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];OLD=P.parent/'municipal-east';OUT=P/'artifact-manifest.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inputs=[OLD/n for n in ['eger-map-2016.pdf','eger-pdf-vector-paths.json','eger-planning-units.geojson','eger-geometry-proof.json','eger-extract.py','export-eger.py']]+[ROOT/'data/neighborhoods/research/planning-semantics-recheck.json']
rows=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(P.iterdir()) if p.is_file() and p!=OUT]
entry=json.loads((P/'proposed-registry-entry.json').read_text());check=json.loads((P/'proposal-check.json').read_text())
d={'schemaVersion':1,'status':'frozen_semantic_proposal_not_applied','sourceFeatureCount':32,'proposedQualifiedHistoricalQuarterCount':23,'proposedRetainedPlanningCount':9,'newGeometryAcquisitionCount':0,'geometryChangedCount':0,'originalNamesAndIdsChangedCount':0,'globalRegistryOrExportChangesApplied':0,'currentNameIdentityVerifiedCount':0,'earlier89NameAuditReused':False,'independentInteriorControlCount':0,'absoluteAccuracyMetres':None,'proposedExport':'proposed-semantic-revision.geojson','proposedExportSha256':entry['sha256'],'proposedRegistryEntry':'proposed-registry-entry.json','applyByReplacementOnly':True,'strictGeometryPassCount':check['strictPassCount'],'inputFingerprints':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in inputs],'artifacts':rows}
s=json.dumps(d,ensure_ascii=False,indent=2)+'\n';parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
if args.check:assert OUT.read_text()==s,'Eger package or frozen input changed'
else:OUT.write_text(s)
print(json.dumps({'artifacts':len(rows),'proposedHistoricalQuarters':23,'retainedPlanning':9,'geometryChanged':0,'check':args.check}))
