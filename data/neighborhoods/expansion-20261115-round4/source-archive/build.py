#!/usr/bin/env python3
"""Deterministically deduplicate/split all non-direct round-four research bytes."""
import argparse,hashlib,io,json,os,stat,subprocess,zipfile
from pathlib import Path
H=Path(__file__).resolve().parent;SCOPE=H.parent;ROOT=H.parents[3]
BASELINE='19caaea641ae90080ab725fd03a68362530199a9';CHUNK=8*1024*1024
PREFIX=SCOPE.relative_to(ROOT).as_posix()+'/'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def files():
 rows=[]
 for p in sorted(SCOPE.rglob('*')):
  if H in p.parents or p==H or '__pycache__' in p.parts or p.suffix=='.pyc':continue
  if p.is_symlink():raise ValueError('Symlink source is unsupported: '+str(p))
  if p.is_file():rows.append(p)
 return rows

def main(check=False):
 state=json.loads((SCOPE/'WORK-STATE.json').read_text());registered={r['path'] for r in state['completedPackets']}
 assert len(registered)==14,'Expected the final fourteen registered packets'
 rawTree=subprocess.check_output(['git','ls-tree','-r','-z',BASELINE],cwd=ROOT)
 gitpaths={}
 for raw in rawTree.split(b'\0'):
  if not raw:continue
  meta,name=raw.split(b'\t',1);mode,kind,oid=meta.decode().split()
  if kind=='blob' and mode in ('100644','100755'):gitpaths.setdefault(oid,[]).append(name.decode())
 direct=[];packed=[];records={};unique={};baselineCandidates={}
 coreNames={'README.md','WORK-STATE.json','summary.json','unresolved.json'}
 identityDirect={'input-pins.json','verified-aliases.json','selection-validation.json'}
 for p in files():
  path=p.relative_to(ROOT).as_posix();rel=p.relative_to(SCOPE)
  keep=(p.suffix in ('.py','.md') or path in registered or p.parent==SCOPE or p.name in coreNames or
        rel.as_posix() in ('shard-0/residual-followup/arkoshaza-reviewed-candidate.geojson','shard-1/identity-followup/review.json') or
        (rel.match('review/*/review.json') and p.stat().st_size<=512*1024) or
        (rel.parts[0]=='tasks' and p.suffix=='.json') or
        (rel.parts[0]=='identity-corrections' and p.name in identityDirect))
  if keep:direct.append(path);continue
  raw=p.read_bytes();digest=sha(raw);oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  row={'sha256':digest,'bytes':len(raw),'mode':stat.S_IMODE(p.stat().st_mode)}
  if oid in gitpaths:
   candidates=sorted(gitpaths[oid],key=lambda x:(len(x),x));row['basePath']=candidates[0]
   baselineCandidates.setdefault(oid,{'sha256':digest,'paths':[]})['paths'].append(path)
  else:
   row['archiveMember']='blobs/'+digest;unique.setdefault(digest,p)
  packed.append(path);records[path]=row
 assert registered<=set(direct),'All registered geometry must stay direct'
 # Confirm SHA-256 equality to the actual baseline blobs, not only their Git IDs.
 if baselineCandidates:
  oids=sorted(baselineCandidates);proc=subprocess.run(['git','cat-file','--batch'],input=('\n'.join(oids)+'\n').encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=ROOT,check=True)
  stream=io.BytesIO(proc.stdout)
  for oid in oids:
   header=stream.readline().decode().strip().split();assert header[0]==oid and header[1]=='blob',header
   blob=stream.read(int(header[2]));assert stream.read(1)==b'\n';assert sha(blob)==baselineCandidates[oid]['sha256'],oid
 local=ROOT/'.local';local.mkdir(exist_ok=True);zpath=local/'round4-research-sources.zip'
 with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
  for digest,p in sorted(unique.items()):
   raw=p.read_bytes();assert sha(raw)==digest
   info=zipfile.ZipInfo('blobs/'+digest,date_time=(2026,11,15,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3;info.external_attr=0o100644<<16;info.flag_bits=0;z.writestr(info,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
 archiveBytes=zpath.stat().st_size;parts=[];archiveHash=hashlib.sha256()
 with zpath.open('rb') as fh:
  index=1
  while True:
   raw=fh.read(CHUNK)
   if not raw:break
   archiveHash.update(raw);name=f'source-blobs.zip.part{index:03d}';path=H/name
   if check:assert path.read_bytes()==raw,('stale archive chunk',name)
   else:path.write_bytes(raw)
   parts.append({'path':name,'sha256':sha(raw),'bytes':len(raw)});index+=1
 expectedPartNames={r['path'] for r in parts};assert {p.name for p in H.glob('source-blobs.zip.part*')}==expectedPartNames,'Unexpected stale archive chunk; do not silently discard data'
 artifactPaths=[(H/name).relative_to(ROOT).as_posix() for name in ['README.md','build.py','materialize.py','manifest.json']]+[(H/p['path']).relative_to(ROOT).as_posix() for p in parts]
 direct=sorted(set(direct+artifactPaths))
 manifest={'schemaVersion':1,'scopePrefix':PREFIX,'baselineCommit':BASELINE,'coordinateDataPolicy':'No selected geometry changed. These are immutable research sources restored to their original paths.','archive':{'format':'zip-split-binary','sha256':archiveHash.hexdigest(),'bytes':archiveBytes,'maximumPartBytes':CHUNK,'timestamp':[2026,11,15,0,0,0],'parts':parts},'files':dict(sorted(records.items())),'directFiles':direct,'summary':{'originalResearchFiles':len(records)+len(direct)-len(artifactPaths),'directOriginalFiles':len(direct)-len(artifactPaths),'packedOriginalFiles':len(records),'packedOriginalBytes':sum(r['bytes'] for r in records.values()),'baselineReferencedFiles':sum('basePath' in r for r in records.values()),'baselineReferencedBytes':sum(r['bytes'] for r in records.values() if 'basePath' in r),'uniqueNewBlobCount':len(unique),'uniqueNewBlobBytes':sum(p.stat().st_size for p in unique.values()),'archiveBytes':archiveBytes,'partCount':len(parts)},'notes':['Every packed path preserves original SHA256, size and mode.','Identical bytes already tracked at the pinned baseline reference that baseline path; other new bytes occur once as blobs/SHA256.','Direct paths are a path list only to avoid mutable metadata hash cycles.','Materialize before rebuilding or geographically auditing archived source packets. The fourteen registered GeoJSON inputs and every Python script remain direct.','Original files are retained locally; root handles index/publication. Caches and archive output are excluded from source inputs.']}
 outputs={H/'manifest.json':encode(manifest),local/'round4-archive-direct-files.json':encode(direct),local/'round4-archive-packed-files.json':encode(sorted(packed))}
 for path,raw in outputs.items():
  if check:assert path.read_bytes()==raw,('stale archive metadata',path)
  else:path.write_bytes(raw)
 print(json.dumps({'checked':check,**manifest['summary'],'manifestSha256':sha(outputs[H/'manifest.json'])}))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();main(a.check)
