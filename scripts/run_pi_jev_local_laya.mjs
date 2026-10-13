/** Unscored native pi-jev + local Laya acquisition; no hosted Jev (#1312). */
import {execFileSync} from 'node:child_process';
import {existsSync, readFileSync, writeFileSync} from 'node:fs';
import {homedir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

export const PI_JEV_SHA='c5b5847aa189fe5ffec52893b7051fe8f9e7a548';
export function localURL(value) {
  const u=new URL(value);
  if(u.protocol!=='http:' || !['127.0.0.1','localhost','[::1]'].includes(u.hostname) ||
     u.username || u.password || u.search || u.hash || !['','/'].includes(u.pathname)) {
    throw Error('Only credential-free HTTP loopback root is permitted');
  }
  return u.origin;
}
export function noPaidProvider(env, secret) {
  if(env.TYPESAFE_API_KEY?.trim() || env.TYPESAFE_BASE_URL?.trim() || existsSync(secret)) {
    throw Error('Refusing hosted TypeSafe configuration or SDK secret file');
  }
}
export function frozenInput(input) {
  if(input?.schema_version!==1 || input.pi_jev_commit!==PI_JEV_SHA || input.top_k!==3 ||
     input.external_execution!==false || input.catalog?.length!==82 || input.cases?.length!==16 ||
     !/^[a-f0-9]{64}$/.test(input.catalog_sha256||'') ||
     !/^[a-f0-9]{64}$/.test(input.cases_sha256||'')) throw Error('Not the frozen #796 handoff');
  for(const [rows,key] of [[input.catalog,'name'],[input.cases,'id']]) {
    const names=rows.map(r=>r?.[key]);
    if(names.some(n=>typeof n!=='string'||!n) || new Set(names).size!==rows.length) {
      throw Error('Invalid/duplicate frozen IDs');
    }
  }
  if(input.cases.some(c=>typeof c.query!=='string'||!c.query.trim())) throw Error('Missing query');
}
/** Never trust manifest hash strings without verifying the original checked-in source. */
export function sameFrozenHandoff(input, generated) {
  if(JSON.stringify(input)!==JSON.stringify(generated)) {
    throw Error('Frozen catalog/case input differs from the canonical SchemaRouter handoff');
  }
}
/** Capture actual post-inference weight and device provenance (not startup preferences). */
export function loadedLayaEvidence(health) {
  const names=health?.loaded,revs=health?.revisions,devices=health?.checkpoint_devices;
  // Laya's device_is_preference=true means a requested device, NOT a measured
  // loaded model. A healthy process alone is insufficient post-inference proof.
  if(health?.status!=='ok' || health?.device_is_preference!==false ||
     !Array.isArray(names) || names.length===0 || new Set(names).size!==names.length ||
     !revs || typeof revs!=='object' || Array.isArray(revs) ||
     !devices || typeof devices!=='object' || Array.isArray(devices) ||
     Object.keys(revs).length!==names.length ||
     Object.keys(devices).length!==names.length ||
     names.some(name=>typeof name!=='string'||!name ||
       !Object.hasOwn(revs,name) || !Object.hasOwn(devices,name) ||
       typeof revs[name]!=='string'||!revs[name].trim() ||
       typeof devices[name]!=='string'||!devices[name].trim()) ||
     health.device!==devices[names[0]]) {
    throw Error('Local Laya returned no measured loaded-checkpoint provenance');
  }
  return {checkpoint_revisions:revs,checkpoint_devices:devices};
}
export function nativeResult(result, catalog) {
  if(result?.fallbackUsed!==false) throw Error('No native Jev/Laya result (fallback detected)');
  const allowed=new Set(catalog.map(x=>x.name));
  const c=result.candidates,a=result.activated,p=result.probabilities;
  if(!Array.isArray(c)||!Array.isArray(a)||c.length<1||c.length>10 ||
     new Set(c).size!==c.length || new Set(a).size!==a.length ||
     !c.every(x=>allowed.has(x)) || !a.every(x=>c.includes(x)) ||
     !p || typeof p!=='object' || Array.isArray(p) ||
     Object.keys(p).length!==c.length ||
     !Object.entries(p).every(([k,v])=>c.includes(k)&&typeof v==='number'&&Number.isFinite(v)&&v>=0&&v<=1) ||
     typeof result.elapsedMs!=='number' || !Number.isFinite(result.elapsedMs) || result.elapsedMs<0) {
    throw Error('Invalid native shortlist, activation, probability or latency');
  }
}
function options(argv) {
  const o={};
  for(let i=0;i<argv.length;i+=2) {
    if(!argv[i]?.startsWith('--')||!argv[i+1]||argv[i].slice(2) in o) throw Error('Invalid arguments');
    o[argv[i].slice(2)]=argv[i+1];
  }
  if(Object.keys(o).length!==4 || ['input','pi-jev-root','output','local-url'].some(k=>!o[k])) {
    throw Error('Need --input --pi-jev-root --output --local-url');
  }
  return o;
}
export async function run(argv) {
  const o=options(argv), url=localURL(o['local-url']);
  noPaidProvider(process.env,join(homedir(),'.pi','agent','secrets','typesafe_api_key'));
  const root=resolve(o['pi-jev-root']);
  const git=(...args)=>execFileSync('git',['-C',root,...args],{encoding:'utf8',timeout:5000}).trim();
  if(git('rev-parse','HEAD')!==PI_JEV_SHA || git('status','--porcelain','--untracked-files=no')) {
    throw Error('pi-jev must be the clean pinned SHA');
  }
  const input=JSON.parse(readFileSync(resolve(o.input),'utf8'));
  frozenInput(input);
  // The catalog/case digests refer to fuller source objects than this reduced JSON
  // handoff. Compare against a newly generated trusted handoff rather than hashing
  // the reduced rows and incorrectly claiming full-source digest verification.
  const schemaRoot=resolve(dirname(fileURLToPath(import.meta.url)),'..');
  const expected=JSON.parse(execFileSync('python',
    ['-m','scripts.external_validation_jev_contract'],
    {cwd:schemaRoot,encoding:'utf8',timeout:20000,maxBuffer:5*1024*1024}));
  sameFrozenHandoff(input,expected);
  process.env.PI_JEV_BASE_URL=url;
  const response=await fetch(url+'/health',{redirect:'error',signal:AbortSignal.timeout(8000)});
  if(!response.ok) throw Error('Local Laya health failed');
  const health=await response.json();
  if(health?.status!=='ok') throw Error('No healthy Laya server');
  const {JevClient}=await import(pathToFileURL(join(root,'src','jev.ts')).href);
  const {ToolRouter}=await import(pathToFileURL(join(root,'src','router.ts')).href);
  const rows=[];
  for(const item of input.cases) {
    let active=[];
    const pi={
      getAllTools:()=>input.catalog.map(x=>({name:x.name,description:x.description})),
      getActiveTools:()=>[...active],
      setActiveTools:names=>{active=[...names];},
    };
    const r=await new ToolRouter(pi,new JevClient()).findAndActivate(item.query);
    nativeResult(r,input.catalog);
    if(JSON.stringify(active)!==JSON.stringify(r.activated)) throw Error('Activation state mismatch');
    rows.push({id:item.id,candidate_tools:r.candidates,activated_tools:r.activated,
      latency_ms:r.elapsedMs,probabilities:r.probabilities});
  }
  const finalHealthResponse=await fetch(url+'/health',{
    redirect:'error',signal:AbortSignal.timeout(8000)});
  if(!finalHealthResponse.ok) throw Error('Post-inference Laya health failed');
  // LAYA_PRELOAD=0 legitimately reports no loaded checkpoints before the first
  // inference. The initial health probe therefore cannot attest actual weights.
  const loadedEvidence=loadedLayaEvidence(await finalHealthResponse.json());
  const report={schema_version:1,provenance:{label:'UNSCORED pi-jev + local Laya, NOT hosted Jev',
    pi_jev_commit:PI_JEV_SHA,catalog_sha256:input.catalog_sha256,cases_sha256:input.cases_sha256,
    native_shortlist_width:10,schemarouter_reference_top_k:3,comparable_top_k:false,
    ...loadedEvidence},cases:rows};
  writeFileSync(resolve(o.output),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
  process.stdout.write('Saved 16 unscored local-native pi-jev rows; widths are not comparable.\n');
}
if(process.argv[1] && resolve(process.argv[1])===resolve(fileURLToPath(import.meta.url))) {
  run(process.argv.slice(2)).catch(e=>{process.stderr.write(String(e.message)+'\n');process.exitCode=1;});
}
