import {execFileSync,spawnSync} from 'node:child_process';

// A receipt proves a complete execution of this policy on exactly these tracked
// bytes. A reused execution never emits a new receipt, so proof cannot chain.
export const CI_POLICY = '20261121-full-tree-validation-v1';
export const MAX_PROOF_AGE_MS = 24*60*60*1000;
export const REPOSITORY_ID = '1441962351';
export const REPOSITORY = 'st-agnes/ingatlan';
export const WORKFLOW_PATH = '.github/workflows/ci.yml';
const REUSE_PATH = 'scripts/ci/reuse-validation.mjs';
export const REQUIRED_JOBS = Object.freeze([
  'static-checks','container-package','browser-tests','guided-forms-and-discovery',
  'postal-street-integration','onboarding-integration','build-and-test','seed-importer'
]);
export const REQUIRED_JOB_NAMES = Object.freeze([
  'Static checks','Container packaging',
  ...['locations','workspace','onboarding'].map(group=>`Browser regression (${group})`),
  'Guided forms and discovery controls',
  'Postal street MySQL integration','Anonymous onboarding browser and MySQL integration',
  ...['8.0','8.4'].map(version=>`Build and test (MySQL ${version})`),
  ...['8.0','8.4'].map(version=>`Test data importer (MySQL ${version})`)
]);
const PROOF_JOB_NAMES = [...REQUIRED_JOB_NAMES,'Plan CI validation','CI validation'];
const HASH = /^[a-f0-9]{40}$/;
const MAX_ARCHIVE_BYTES = 64*1024;
const MAX_RECEIPT_BYTES = 16*1024;
const MAX_CANDIDATES = 8;
const ALLOWED_EVENTS = new Set(['push','pull_request','workflow_dispatch']);
const same = (left,right)=>JSON.stringify(left)===JSON.stringify(right);
const positiveInteger = value=>Number.isSafeInteger(value)&&value>0;
const sorted = values=>[...values].sort();

function assertIdentity(identity) {
  if(!identity||!HASH.test(identity.tree)||!HASH.test(identity.checkoutSha)||!HASH.test(identity.workflowBlobSha))
    throw new Error('CI checkout identity is missing or invalid.');
}

function trustedContext(context) {
  return String(context?.payload?.repository?.id)===REPOSITORY_ID
    && `${context?.repo?.owner}/${context?.repo?.repo}`===REPOSITORY;
}

export function receiptArtifactName(tree) {
  if(!HASH.test(tree))throw new Error('The CI receipt needs an exact Git tree.');
  return `ci-full-tree-${tree}-v1`;
}

/** All commands are local/read-only; generated ignored build files are allowed. */
export function readCheckoutIdentity(cwd=process.env.GITHUB_WORKSPACE||process.cwd()) {
  const git=(...args)=>execFileSync('git',args,{cwd,encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
  if(git('status','--porcelain','--untracked-files=no'))throw new Error('CI must validate a clean tracked checkout.');
  const identity={checkoutSha:git('rev-parse','HEAD'),tree:git('rev-parse','HEAD^{tree}'),
    workflowBlobSha:git('rev-parse',`HEAD:${WORKFLOW_PATH}`),reuseBlobSha:git('rev-parse',`HEAD:${REUSE_PATH}`)};
  assertIdentity(identity);return identity;
}

export function validateJobResults(needs) {
  for(const name of REQUIRED_JOBS)if(needs?.[name]?.result!=='success')
    throw new Error(`Full CI validation requires successful ${name}; skipped, missing or failed jobs cannot create a receipt.`);
  return true;
}

export function makeValidationReceipt({context,tree,checkoutSha,workflowBlobSha,runAttempt,needs}) {
  const identity={tree,checkoutSha,workflowBlobSha};assertIdentity(identity);
  if(!trustedContext(context)||!ALLOWED_EVENTS.has(context.eventName)||checkoutSha!==context.sha
    ||!positiveInteger(context.runId)||!positiveInteger(runAttempt))throw new Error('The full CI receipt context is invalid.');
  if(needs?.plan?.result!=='success'||needs.plan.outputs?.reuse!=='false')
    throw new Error('Only a freshly planned full CI execution can create a receipt.');
  const plan=needs.plan.outputs;
  if(plan.tree!==tree||plan.checkout_sha!==checkoutSha||plan.workflow_blob_sha!==workflowBlobSha)
    throw new Error('The completed CI checkout differs from its planned checkout.');
  validateJobResults(needs);
  return {schemaVersion:1,policy:CI_POLICY,mode:'full',repositoryId:REPOSITORY_ID,repository:REPOSITORY,
    workflowPath:WORKFLOW_PATH,workflowBlobSha,sourceRunId:context.runId,sourceAttempt:runAttempt,
    eventName:context.eventName,checkoutSha,tree,requiredJobs:[...REQUIRED_JOBS],
    jobResults:Object.fromEntries(REQUIRED_JOBS.map(name=>[name,'success']))};
}

export function validateReusedPlan({context,identity,plan}) {
  assertIdentity(identity);
  const output=plan?.outputs;
  if(!trustedContext(context)||context.eventName!=='push'||context.ref!=='refs/heads/main'
    ||identity.checkoutSha!==context.sha||plan?.result!=='success'||output?.reuse!=='true'
    ||output.tree!==identity.tree||output.checkout_sha!==identity.checkoutSha
    ||output.workflow_blob_sha!==identity.workflowBlobSha
    ||!/^\d+$/.test(output.source_run_id||'')||!positiveInteger(Number(output.source_run_id))
    ||!/^\d+$/.test(output.source_attempt||'')||!positiveInteger(Number(output.source_attempt)))
    throw new Error('CI reuse requires a successful verified plan for this exact main checkout.');
  return {sourceRunId:Number(output.source_run_id),sourceAttempt:Number(output.source_attempt),tree:identity.tree};
}

// Python's standard ZIP reader supports the archive variants produced by
// upload-artifact without extracting paths or adding a ZIP/npm dependency.
function readReceiptArchive(data) {
  const bytes=Buffer.isBuffer(data)?data:data instanceof ArrayBuffer?Buffer.from(data)
    :ArrayBuffer.isView(data)?Buffer.from(data.buffer,data.byteOffset,data.byteLength):null;
  if(!bytes||bytes.length>MAX_ARCHIVE_BYTES||bytes.length<22)return null;
  const script=`import base64,io,sys,zipfile\nraw=base64.b64decode(sys.argv[1],validate=True)\nif len(raw)>${MAX_ARCHIVE_BYTES}: raise ValueError('oversize archive')\nwith zipfile.ZipFile(io.BytesIO(raw)) as archive:\n files=archive.infolist()\n if len(files)!=1: raise ValueError('unexpected entries')\n item=files[0]\n if item.filename!='receipt.json' or item.flag_bits&1 or item.file_size>${MAX_RECEIPT_BYTES} or item.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED): raise ValueError('invalid receipt entry')\n with archive.open(item) as handle:\n  value=handle.read(${MAX_RECEIPT_BYTES+1})\n if len(value)>${MAX_RECEIPT_BYTES}: raise ValueError('oversize receipt')\n sys.stdout.buffer.write(value)\n`;
  const result=spawnSync('python3',['-c',script,bytes.toString('base64')],{stdio:['ignore','pipe','pipe'],maxBuffer:MAX_RECEIPT_BYTES+1024,timeout:5000,windowsHide:true});
  if(result.error||result.status!==0)return null;
  try {return JSON.parse(result.stdout.toString('utf8'));}catch{return null;}
}

function validReceipt(receipt,{identity,run}) {
  const keys=['schemaVersion','policy','mode','repositoryId','repository','workflowPath','workflowBlobSha',
    'sourceRunId','sourceAttempt','eventName','checkoutSha','tree','requiredJobs','jobResults'];
  if(!receipt||typeof receipt!=='object'||Array.isArray(receipt)||!same(sorted(Object.keys(receipt)),sorted(keys)))return false;
  return receipt.schemaVersion===1&&receipt.policy===CI_POLICY&&receipt.mode==='full'
    &&receipt.repositoryId===REPOSITORY_ID&&receipt.repository===REPOSITORY
    &&receipt.workflowPath===WORKFLOW_PATH&&receipt.workflowBlobSha===identity.workflowBlobSha
    &&receipt.sourceRunId===run.id&&receipt.sourceAttempt===run.run_attempt
    &&receipt.eventName===run.event&&HASH.test(receipt.checkoutSha)&&receipt.tree===identity.tree
    &&same(receipt.requiredJobs,REQUIRED_JOBS)
    &&receipt.jobResults&&same(sorted(Object.keys(receipt.jobResults)),sorted(REQUIRED_JOBS))
    &&REQUIRED_JOBS.every(name=>receipt.jobResults[name]==='success');
}

function validRun(run,sourceRunId,now) {
  const updated=typeof run?.updated_at==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(run.updated_at)
    ? Date.parse(run.updated_at):NaN;
  return run?.id===sourceRunId&&positiveInteger(run.run_attempt)&&HASH.test(run.head_sha)
    &&run.status==='completed'&&run.conclusion==='success'&&ALLOWED_EVENTS.has(run.event)
    &&run.path===WORKFLOW_PATH&&String(run.repository?.id)===REPOSITORY_ID
    &&String(run.head_repository?.id)===REPOSITORY_ID
    &&Number.isFinite(updated)&&updated<=now&&now-updated<=MAX_PROOF_AGE_MS;
}

function validProofJobs(jobs) {
  return Array.isArray(jobs)&&PROOF_JOB_NAMES.every(name=>{
    const matches=jobs.filter(job=>job.name===name);
    return matches.length===1&&matches[0].status==='completed'&&matches[0].conclusion==='success';
  });
}

/** Missing, stale, malformed or inaccessible proof always chooses full tests. */
export async function findReusableValidation({github,context,tree,checkoutSha,workflowBlobSha,reuseBlobSha,now=Date.now()}) {
  const identity={tree,checkoutSha,workflowBlobSha};assertIdentity(identity);
  const full=reason=>({reuse:false,reason});
  if(!trustedContext(context)||context.eventName!=='push'||context.ref!=='refs/heads/main'||checkoutSha!==context.sha)
    return full('Only a trusted main push may reuse a complete validation.');
  if(!HASH.test(reuseBlobSha))return full('The validation policy identity is unavailable.');
  if(!Number.isFinite(now))return full('The validation proof age could not be verified.');
  try {
    const name=receiptArtifactName(tree),repo=context.repo;
    const response=await github.rest.actions.listArtifactsForRepo({...repo,name,per_page:100});
    const rows=response?.data?.artifacts;
    if(!Array.isArray(rows))return full('No complete validation receipt was available.');
    const candidates=rows.filter(artifact=>artifact?.name===name&&artifact.expired===false
      &&positiveInteger(artifact.id)&&positiveInteger(artifact.size_in_bytes)&&artifact.size_in_bytes<=MAX_ARCHIVE_BYTES
      &&positiveInteger(artifact.workflow_run?.id)
      &&String(artifact.workflow_run.repository_id)===REPOSITORY_ID
      &&String(artifact.workflow_run.head_repository_id)===REPOSITORY_ID)
      .sort((a,b)=>b.id-a.id).slice(0,MAX_CANDIDATES);
    for(const artifact of candidates)try {
      const sourceRunId=artifact.workflow_run.id;
      if(sourceRunId===context.runId)continue;
      const {data:run}=await github.rest.actions.getWorkflowRun({...repo,run_id:sourceRunId});
      if(!validRun(run,sourceRunId,now)||artifact.workflow_run.head_sha!==run.head_sha)continue;
      // A different workflow/helper must not forge a receipt that merely
      // claims this tree. Check the code that actually produced the source run.
      let producerMatches=true;
      for(const [path,sha] of [[WORKFLOW_PATH,workflowBlobSha],[REUSE_PATH,reuseBlobSha]]){
        const {data:file}=await github.rest.repos.getContent({...repo,path,ref:run.head_sha});
        if(file?.type!=='file'||file.sha!==sha){producerMatches=false;break;}
      }
      if(!producerMatches)continue;
      const {data:archive}=await github.rest.actions.downloadArtifact({...repo,artifact_id:artifact.id,archive_format:'zip'});
      const receipt=readReceiptArchive(archive);
      if(!validReceipt(receipt,{identity,run}))continue;
      const {data:commit}=await github.rest.git.getCommit({...repo,commit_sha:receipt.checkoutSha});
      if(commit?.sha!==receipt.checkoutSha||commit.tree?.sha!==tree)continue;
      if(receipt.checkoutSha!==run.head_sha
        &&(run.event!=='pull_request'||commit.parents?.length!==2||commit.parents[1]?.sha!==run.head_sha))continue;
      const {data:jobData}=await github.rest.actions.listJobsForWorkflowRun({...repo,run_id:sourceRunId,filter:'latest',per_page:100});
      if(!validProofJobs(jobData?.jobs))continue;
      // A rerun can start during the lookup. Never accept an older attempt's
      // receipt as the proof for a currently pending/failed latest attempt.
      const {data:latest}=await github.rest.actions.getWorkflowRun({...repo,run_id:sourceRunId});
      if(!validRun(latest,sourceRunId,now)||latest.run_attempt!==receipt.sourceAttempt||latest.head_sha!==run.head_sha)continue;
      return {reuse:true,sourceRunId,sourceAttempt:receipt.sourceAttempt,tree,
        reason:`Reusing full CI run ${sourceRunId}, attempt ${receipt.sourceAttempt}, for identical tree ${tree}.`};
    }catch{/* A missing/expired proof is an optimization miss, never authorization. */}
    return full('No successful full validation proved this exact tracked tree.');
  }catch{return full('Validation proof could not be verified; running the full checks.');}
}
