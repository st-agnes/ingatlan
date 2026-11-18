#!/usr/bin/env python3
"""Verify retained hashes, then reproduce independently in a temporary packet."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,tempfile

P=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((P/'artifact-manifest.json').read_text())
assert manifest['selfContainedReproduction'] and manifest['networkCalls']==0
for row in manifest['files']:
    p=P/row['path'];assert p.is_file() and p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],row['path']
assert any(r['path']=='independent-review.json' for r in manifest['files'])
review=json.loads((P/'independent-review.json').read_text())
assert review['accepted'] is True and review['featureCount']==23
with tempfile.TemporaryDirectory(prefix='debrecen-remaining-reproduce-') as tmp:
    target=Path(tmp)/'data/neighborhoods/sources'/P.name
    shutil.copytree(P,target)
    result=subprocess.run([sys.executable,str(target/'reproduce.py')],check=True,capture_output=True,text=True)
    for row in manifest['files']:
        assert sha(target/row['path'])==row['sha256'],row['path']
    assert (target/'artifact-manifest.json').read_bytes()==(P/'artifact-manifest.json').read_bytes()
report={'schemaVersion':1,'retainedManifestFilesVerified':len(manifest['files']),'selfContainedTemporaryReproduction':'byte_identical','independentReviewAccepted':True,'originalPbfPdfRevalidationRetained':(P/'original-source-revalidation.json').exists(),'networkCalls':0,'globalWrites':False,'reproducerStdout':result.stdout.strip()}
(P/'reproduction-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
