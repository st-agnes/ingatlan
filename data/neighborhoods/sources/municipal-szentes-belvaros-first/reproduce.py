"""Verify frozen local inputs and replay both finite Szentes alternatives offline.

Set PYTHONPATH=.local/geodata at repository root. --checks additionally runs the
second geometry/support checker against the pinned local municipal parent.
"""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
args=argparse.ArgumentParser();args.add_argument('--checks',action='store_true');opts=args.parse_args()
manifest=json.loads((ROOT/'manifest.json').read_text())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for name,expected in manifest['inputSha256'].items():
 if digest(ROOT/name)!=expected:raise ValueError('Changed frozen input: '+name)
with tempfile.TemporaryDirectory(prefix='szentes-belvaros-replay-')as temp:
 out=Path(temp)
 for name in ['szentes-local-lines.geojson','szentes-build-bounded-inference.py','szentes-check-candidates.py','szentes-parent-control.geojson']:
  shutil.copy2(ROOT/'raw'/name,out/name)
 result=subprocess.run([sys.executable,str(out/'szentes-build-bounded-inference.py')],capture_output=True,text=True,check=True)
 for name,expected in manifest['replayOutputSha256'].items():
  if digest(out/name)!=expected:raise ValueError('Changed reproduced output: '+name)
 if opts.checks:
  result=subprocess.run([sys.executable,str(out/'szentes-check-candidates.py')],capture_output=True,text=True,check=True)
  print(result.stdout.strip())
print(json.dumps({'verifiedFrozenInputs':len(manifest['inputSha256']),'matchingReplayOutputs':len(manifest['replayOutputSha256']),'compiledQuarterCount':1,'rawAlternativesCount':2,'sourceContourIsObserved':False,'usableForAddressAssignment':False}))
