import assert from 'node:assert/strict';
import test from 'node:test';
import {execFileSync} from 'node:child_process';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {CI_POLICY,MAX_PROOF_AGE_MS,REPOSITORY_ID,REPOSITORY,WORKFLOW_PATH,REQUIRED_JOBS,REQUIRED_JOB_NAMES,
  receiptArtifactName,readCheckoutIdentity,validateJobResults,makeValidationReceipt,
  validateReusedPlan,findReusableValidation} from '../scripts/ci/reuse-validation.mjs';

const identity=Object.freeze({tree:'a'.repeat(40),checkoutSha:'b'.repeat(40),workflowBlobSha:'c'.repeat(40),reuseBlobSha:'d'.repeat(40)});
const sourceCheckout='f'.repeat(40),sourceHead='e'.repeat(40);
const now=Date.parse('2026-11-21T12:00:00Z');
const context=()=>({repo:{owner:'st-agnes',repo:'ingatlan'},payload:{repository:{id:1441962351}},
  sha:identity.checkoutSha,eventName:'push',ref:'refs/heads/main',runId:1000});
const planOutputs=(value=identity)=>({reuse:'false',tree:value.tree,checkout_sha:value.checkoutSha,workflow_blob_sha:value.workflowBlobSha});
const fullNeeds=(value=identity)=>({plan:{result:'success',outputs:planOutputs(value)},
  ...Object.fromEntries(REQUIRED_JOBS.map(name=>[name,{result:'success'}]))});
const reusedPlan=()=>({result:'success',outputs:{...planOutputs(),reuse:'true',source_run_id:'900',source_attempt:'2'}});

function zip(entries,{zip64=false,compression=8}={}) {
  const script=`import base64,io,json,sys,zipfile\nitems=json.loads(base64.b64decode(sys.argv[1]))\nout=io.BytesIO()\nwith zipfile.ZipFile(out,'w',${compression}) as archive:\n for item in items:\n  if ${zip64?'True':'False'}:\n   with archive.open(item['name'],'w',force_zip64=True) as handle: handle.write(item['value'].encode())\n  else: archive.writestr(item['name'],item['value'])\nsys.stdout.buffer.write(out.getvalue())\n`;
  return execFileSync('python3',['-c',script,Buffer.from(JSON.stringify(entries)).toString('base64')],{stdio:['ignore','pipe','pipe'],maxBuffer:128*1024,timeout:5000});
}

function harness() {
  const current=context(),sourceIdentity={...identity,checkoutSha:sourceCheckout};
  const sourceContext={...context(),sha:sourceCheckout,eventName:'pull_request',ref:'refs/pull/1/merge',runId:900};
  const receipt=makeValidationReceipt({context:sourceContext,...sourceIdentity,runAttempt:2,needs:fullNeeds(sourceIdentity)});
  const run={id:900,run_attempt:2,head_sha:sourceHead,event:'pull_request',status:'completed',conclusion:'success',
    path:WORKFLOW_PATH,repository:{id:1441962351},head_repository:{id:1441962351},updated_at:'2026-11-21T11:55:00Z'};
  const artifact={id:901,name:receiptArtifactName(identity.tree),expired:false,size_in_bytes:1000,
    workflow_run:{id:900,repository_id:1441962351,head_repository_id:1441962351,head_sha:sourceHead}};
  const jobs=[...REQUIRED_JOB_NAMES,'Plan CI validation','CI validation'].map((name,index)=>({id:index+1,name,status:'completed',conclusion:'success'}));
  const commit={sha:sourceCheckout,tree:{sha:identity.tree},parents:[{sha:'1'.repeat(40)},{sha:sourceHead}]};
  const h={current,receipt,run,artifact,jobs,commit,artifacts:[artifact],calls:[],latestRun:null,archive:null,
    workflowSha:identity.workflowBlobSha,reuseSha:identity.reuseBlobSha,failAt:null,downloads:0};
  const call=(method,args)=>{h.calls.push({method,args});if(h.failAt===method)throw new Error('Synthetic unavailable proof');};
  const github={rest:{actions:{
    async listArtifactsForRepo(args){call('listArtifactsForRepo',args);return {data:{artifacts:h.artifacts}};},
    async getWorkflowRun(args){call('getWorkflowRun',args);const count=h.calls.filter(row=>row.method==='getWorkflowRun').length;return {data:count>1&&h.latestRun?h.latestRun:h.run};},
    async downloadArtifact(args){call('downloadArtifact',args);h.downloads++;return {data:h.archive??zip([{name:'receipt.json',value:JSON.stringify(h.receipt)}])};},
    async listJobsForWorkflowRun(args){call('listJobsForWorkflowRun',args);return {data:{jobs:h.jobs}};}
  },git:{async getCommit(args){call('getCommit',args);return {data:h.commit};}},
  repos:{async getContent(args){call('getContent',args);return {data:{type:'file',sha:args.path===WORKFLOW_PATH?h.workflowSha:h.reuseSha}};}}}};
  h.execute=()=>findReusableValidation({github,context:h.current,...identity,now});return h;
}

test('the receipt proves every full group and uses a content-addressed artifact name',()=>{
 const h=harness();
 assert.equal(h.receipt.policy,CI_POLICY);assert.equal(h.receipt.repositoryId,REPOSITORY_ID);assert.equal(h.receipt.repository,REPOSITORY);
 assert.equal(h.receipt.mode,'full');assert.deepEqual(h.receipt.requiredJobs,REQUIRED_JOBS);
 assert.equal(receiptArtifactName(identity.tree),`ci-full-tree-${identity.tree}-v1`);
 for(const invalid of ['',null,'x'.repeat(40),'a'.repeat(39)])assert.throws(()=>receiptArtifactName(invalid));
});

test('a successful full PR merge checkout authorizes identical main bytes despite different commit SHAs',async()=>{
 const h=harness(),result=await h.execute();
 assert.equal(result.reuse,true);assert.equal(result.sourceRunId,900);assert.equal(result.sourceAttempt,2);assert.equal(result.tree,identity.tree);
 assert.deepEqual(h.calls[0],{method:'listArtifactsForRepo',args:{owner:'st-agnes',repo:'ingatlan',name:receiptArtifactName(identity.tree),per_page:100}});
 assert.ok(h.calls.some(row=>row.method==='getCommit'&&row.args.commit_sha===sourceCheckout));
 assert.ok(h.calls.some(row=>row.method==='listJobsForWorkflowRun'&&row.args.filter==='latest'));
 for(const path of [WORKFLOW_PATH,'scripts/ci/reuse-validation.mjs'])assert.ok(h.calls.some(row=>row.method==='getContent'&&row.args.path===path&&row.args.ref===sourceHead));
});

test('a complete push or manual source must bind to its exact checked-out source commit',async()=>{
 for(const event of ['push','workflow_dispatch']){
  const h=harness();h.run.event=event;h.run.head_sha=sourceCheckout;h.artifact.workflow_run.head_sha=sourceCheckout;h.receipt.eventName=event;
  assert.equal((await h.execute()).reuse,true,event);
  h.run.head_sha=sourceHead;h.artifact.workflow_run.head_sha=sourceHead;
  assert.equal((await h.execute()).reuse,false,'A non-PR source cannot claim an unrelated checkout');
 }
});

test('PR, manual, non-main and foreign current executions always run full checks',async()=>{
 for(const change of [{eventName:'pull_request'},{eventName:'workflow_dispatch'},{ref:'refs/heads/codex/feature'},
  {sha:'0'.repeat(40)},{payload:{repository:{id:1}}},{repo:{owner:'fork',repo:'ingatlan'}}]){
  const h=harness();Object.assign(h.current,change);assert.equal((await h.execute()).reuse,false);assert.equal(h.calls.length,0);
 }
});

test('missing or expired proofs choose full validation',async()=>{
 for(const mutate of [h=>h.artifacts=[],h=>h.artifact.expired=true,h=>h.artifact.name='different-tree',
  h=>h.artifact.size_in_bytes=65537,h=>h.artifact.size_in_bytes=0,h=>h.artifact.workflow_run.id=h.current.runId]){
  const h=harness();mutate(h);assert.equal((await h.execute()).reuse,false);assert.equal(h.downloads,0);
 }
});

test('proof lookup is bounded and an unrelated recent candidate does not hide an older valid receipt',async()=>{
 const h=harness();h.artifacts=[{...h.artifact,id:902,workflow_run:{...h.artifact.workflow_run,id:899}},h.artifact];
 assert.equal((await h.execute()).reuse,true);
 const bounded=harness();bounded.artifacts=Array.from({length:100},(_,index)=>({...bounded.artifact,id:10000+index,
  workflow_run:{...bounded.artifact.workflow_run,id:10000+index}}));
 assert.equal((await bounded.execute()).reuse,false);
 assert.equal(bounded.calls.filter(row=>row.method==='getWorkflowRun').length,8);
});

test('proof freshness is bounded to24hours, including malformed or future source timestamps',async()=>{
 for(const updated_at of [undefined,'not-a-date','2026',new Date(now+1).toISOString(),new Date(now-MAX_PROOF_AGE_MS-1).toISOString()]){
  const h=harness();h.run.updated_at=updated_at;assert.equal((await h.execute()).reuse,false);assert.equal(h.downloads,0);
 }
 const boundary=harness();boundary.run.updated_at=new Date(now-MAX_PROOF_AGE_MS).toISOString();assert.equal((await boundary.execute()).reuse,true);
});

for(const [label,mutate]of [
 ['fork artifact',h=>h.artifact.workflow_run.head_repository_id=123],
 ['foreign artifact repository',h=>h.artifact.workflow_run.repository_id=123],
 ['artifact/source HEAD mismatch',h=>h.artifact.workflow_run.head_sha='0'.repeat(40)],
 ['fork source run',h=>h.run.head_repository={id:123}],
 ['foreign source repository',h=>h.run.repository={id:123}],
 ['missing source repository',h=>delete h.run.repository],
 ['different workflow',h=>h.run.path='.github/workflows/deploy-dev.yml'],
 ['pull request target',h=>h.run.event='pull_request_target'],
 ['pending run',h=>h.run.status='in_progress'],
 ['failed run',h=>h.run.conclusion='failure'],
 ['skipped run',h=>h.run.conclusion='skipped'],
 ['stale source attempt',h=>h.run.run_attempt=3],
 ['changed producer workflow',h=>h.workflowSha='0'.repeat(40)],
 ['changed producer helper',h=>h.reuseSha='0'.repeat(40)]
])test(`untrusted proof falls back to full checks: ${label}`,async()=>{
 const h=harness();mutate(h);assert.equal((await h.execute()).reuse,false);
});

for(const [label,mutate]of [
 ['different tree',h=>h.receipt.tree='0'.repeat(40)],
 ['different workflow blob',h=>h.receipt.workflowBlobSha='0'.repeat(40)],
 ['different policy',h=>h.receipt.policy='old-policy'],
 ['wrong run identity',h=>h.receipt.sourceRunId=901],
 ['wrong run attempt',h=>h.receipt.sourceAttempt=1],
 ['wrong repository',h=>h.receipt.repositoryId='123'],
 ['unexpected field',h=>h.receipt.unknown='ignored-proof'],
 ['nonfull proof chain',h=>h.receipt.mode='reused'],
 ['missing group',h=>h.receipt.requiredJobs.pop()],
 ['skipped receipt group',h=>h.receipt.jobResults[REQUIRED_JOBS[0]]='skipped'],
 ['different checkout tree',h=>h.commit.tree.sha='0'.repeat(40)],
 ['wrong checkout commit',h=>h.commit.sha='0'.repeat(40)],
 ['feature HEAD in wrong parent position',h=>h.commit.parents.reverse()],
 ['multiple-parent checkout',h=>h.commit.parents.push({sha:'2'.repeat(40)})],
 ['non-merge unrelated checkout',h=>h.commit.parents=[]]
])test(`a forged or stale receipt cannot replace testing: ${label}`,async()=>{
 const h=harness();mutate(h);assert.equal((await h.execute()).reuse,false);
});

test('actual GitHub job outcomes prove every matrix member, not only receipt assertions',async()=>{
 for(const name of [...REQUIRED_JOB_NAMES,'Plan CI validation','CI validation']){
  const h=harness();h.jobs.find(job=>job.name===name).conclusion='skipped';assert.equal((await h.execute()).reuse,false,name);
 }
 const missing=harness();missing.jobs.pop();assert.equal((await missing.execute()).reuse,false);
 const duplicate=harness();duplicate.jobs.push({...duplicate.jobs[0]});assert.equal((await duplicate.execute()).reuse,false);
});

test('a source rerun started during lookup invalidates the older receipt',async()=>{
 for(const change of [{run_attempt:3,status:'in_progress',conclusion:null},{run_attempt:3,conclusion:'failure'}]){
  const h=harness();h.latestRun={...h.run,...change};assert.equal((await h.execute()).reuse,false);
 }
});

test('ZIP64 receipts work without extraction; malformed, huge and extra archive files do not',async()=>{
 const valid=harness();valid.archive=zip([{name:'receipt.json',value:JSON.stringify(valid.receipt)}],{zip64:true});assert.equal((await valid.execute()).reuse,true);
 for(const archive of [Buffer.from('not a zip'),Buffer.alloc(65537),
  zip([{name:'../receipt.json',value:'{}'}]),zip([{name:'receipt.json',value:'not json'}]),
  zip([{name:'receipt.json',value:'x'.repeat(16385)}]),
  zip([{name:'receipt.json',value:'{}'}],{compression:12}),
  zip([{name:'receipt.json',value:'{}'},{name:'unexpected.txt',value:'extra'}])]){
  const h=harness();h.archive=archive;assert.equal((await h.execute()).reuse,false);
 }
});

test('binary API response views preserve exact bytes and corrupted ZIP checksums are rejected',async()=>{
 const h=harness(),bytes=zip([{name:'receipt.json',value:JSON.stringify(h.receipt)}]);
 h.archive=Uint8Array.from(bytes).buffer;assert.equal((await h.execute()).reuse,true);
 const padded=Buffer.concat([Buffer.alloc(8),bytes,Buffer.alloc(8)]);
 h.archive=new Uint8Array(padded.buffer,padded.byteOffset+8,bytes.length);assert.equal((await h.execute()).reuse,true);
 const broken=Buffer.from(bytes),offset=30+broken.readUInt16LE(26)+broken.readUInt16LE(28);broken[offset+2]^=1;
 h.archive=broken;assert.equal((await h.execute()).reuse,false);
});

test('missing GitHub metadata, artifacts, policy files or checkout commits run full tests',async()=>{
 for(const method of ['listArtifactsForRepo','getWorkflowRun','getContent','downloadArtifact','getCommit','listJobsForWorkflowRun']){
  const h=harness();h.failAt=method;assert.equal((await h.execute()).reuse,false,method);
 }
});

test('missing, failed or skipped full groups cannot create a success receipt',()=>{
 assert.equal(validateJobResults(fullNeeds()),true);
 for(const name of REQUIRED_JOBS)for(const result of [undefined,'skipped','failure','cancelled']){
  const needs=fullNeeds();needs[name]={result};assert.throws(()=>validateJobResults(needs));
  assert.throws(()=>makeValidationReceipt({context:context(),...identity,runAttempt:1,needs}));
 }
});

test('receipt creation rejects reused, failed, mismatched and missing plans',()=>{
 for(const mutate of [needs=>delete needs.plan,needs=>needs.plan.result='failure',needs=>needs.plan.outputs.reuse='true',
  needs=>needs.plan.outputs.tree='0'.repeat(40),needs=>needs.plan.outputs.checkout_sha='0'.repeat(40),
  needs=>needs.plan.outputs.workflow_blob_sha='0'.repeat(40)]){
  const needs=fullNeeds();mutate(needs);assert.throws(()=>makeValidationReceipt({context:context(),...identity,runAttempt:1,needs}));
 }
 for(const runAttempt of [undefined,0,-1,1.5])assert.throws(()=>makeValidationReceipt({context:context(),...identity,runAttempt,needs:fullNeeds()}));
});

test('the final reused gate binds a successful proof to the same current main checkout',()=>{
 assert.deepEqual(validateReusedPlan({context:context(),identity,plan:reusedPlan()}),{sourceRunId:900,sourceAttempt:2,tree:identity.tree});
 for(const field of ['tree','checkout_sha','workflow_blob_sha','source_run_id','source_attempt','reuse']){
  const plan=reusedPlan();plan.outputs[field]='invalid';assert.throws(()=>validateReusedPlan({context:context(),identity,plan}),field);
 }
 const failed=reusedPlan();failed.result='failure';assert.throws(()=>validateReusedPlan({context:context(),identity,plan:failed}));
 assert.throws(()=>validateReusedPlan({context:{...context(),eventName:'workflow_dispatch'},identity,plan:reusedPlan()}));
});

test('checkout identity comes from clean committed files and includes the policy producer blobs',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'otthonra-ci-proof-'));
 const git=(...args)=>execFileSync('git',args,{cwd:directory,encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
 try {
  git('init','--quiet');await mkdir(join(directory,'.github/workflows'),{recursive:true});await mkdir(join(directory,'scripts/ci'),{recursive:true});
  await writeFile(join(directory,WORKFLOW_PATH),'name: fixture\n');await writeFile(join(directory,'scripts/ci/reuse-validation.mjs'),'// fixture\n');await writeFile(join(directory,'.gitignore'),'.local/\n');
  git('add','.');git('-c','user.name=CI fixture','-c','user.email=ci@example.test','commit','--quiet','-m','fixture');
  const result=readCheckoutIdentity(directory);assert.equal(result.checkoutSha,git('rev-parse','HEAD'));
  assert.equal(result.tree,git('rev-parse','HEAD^{tree}'));assert.equal(result.reuseBlobSha,git('rev-parse','HEAD:scripts/ci/reuse-validation.mjs'));
  await mkdir(join(directory,'.local'));await writeFile(join(directory,'.local/generated'),'ignored');assert.deepEqual(readCheckoutIdentity(directory),result);
  await writeFile(join(directory,WORKFLOW_PATH),'changed\n');assert.throws(()=>readCheckoutIdentity(directory),/clean tracked checkout/);
 }finally{await rm(directory,{recursive:true,force:true});}
});
