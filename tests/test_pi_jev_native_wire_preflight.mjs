/**
 * Zero-model native pi-jev ↔ strict Jev wire preflight.
 *
 * This runs pinned upstream JevClient + ToolRouter against a loopback HTTP
 * test double, NOT Laya weights and NOT a scored external comparison.
 */
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {join, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {PI_JEV_SHA, nativeResult} from '../scripts/run_pi_jev_local_laya.mjs';

const root=resolve(process.argv[2] || '');
assert.ok(process.argv[2], 'Provide pinned pi-jev checkout root');
assert.equal(execFileSync('git',['-C',root,'rev-parse','HEAD'],{encoding:'utf8'}).trim(),
  PI_JEV_SHA, 'Use exact pinned native pi-jev source');
assert.equal(execFileSync('git',['-C',root,'status','--porcelain','--untracked-files=no'],
  {encoding:'utf8'}).trim(),'', 'Pinned source must be clean');
assert.equal(process.env.TYPESAFE_API_KEY || '', '', 'No paid credential may be set');
assert.equal(process.env.TYPESAFE_BASE_URL || '', '', 'No hosted endpoint may be set');

const catalog=Array.from({length:82},(_,i)=>({
  name:'tool_'+String(i).padStart(2,'0'),
  description:'A test capability for task '+String(i).padStart(2,'0'),
}));
const requests=[];
const server=createServer(async (req,res)=>{
  try {
    assert.equal(req.method,'POST');
    assert.equal(req.url,'/v1/systemone');
    const chunks=[];
    let size=0;
    for await(const chunk of req) {
      size+=chunk.length;
      if(size>1024*1024)throw Error('Unexpected oversized local request');
      chunks.push(chunk);
    }
    const body=JSON.parse(Buffer.concat(chunks).toString('utf8'));
    const keys=Object.keys(body.questions||{});
    assert.equal(keys.length,10,'Pinned native router must request exactly 10 candidates');
    assert.ok(keys.every(k=>catalog.some(t=>t.name===k)));
    assert.ok(keys.every(k=>body.questions[k].type==='noul'));
    requests.push({keys,model:body.model??null});
    const answers=Object.fromEntries(keys.map((key,index)=>[
      key,{type:'noul',noul:index===0?0.99:0.01},
    ]));
    const payload={model:'local-wire-test-double',answers,
      usage:{input_tokens:1,output_tokens:1}};
    res.writeHead(200,{'content-type':'application/json'});
    res.end(JSON.stringify(payload));
  } catch (error) {
    res.writeHead(500,{'content-type':'application/json'});
    res.end(JSON.stringify({error:String(error?.message||error)}));
  }
});
await new Promise((resolveStart,reject)=>{
  server.once('error',reject);
  server.listen(0,'127.0.0.1',resolveStart);
});
try {
  const address=server.address();
  assert.ok(address&&typeof address==='object');
  process.env.PI_JEV_BASE_URL='http://127.0.0.1:'+address.port;
  const {JevClient}=await import(pathToFileURL(join(root,'src','jev.ts')).href);
  const {ToolRouter}=await import(pathToFileURL(join(root,'src','router.ts')).href);
  let active=[];
  const pi={
    getAllTools:()=>catalog.map(x=>({...x})),
    getActiveTools:()=>[...active],
    setActiveTools:names=>{active=[...names];},
  };
  const router=new ToolRouter(pi,new JevClient());
  const result=await router.findAndActivate('Need capability for task 00');
  nativeResult(result,catalog);
  assert.equal(result.fallbackUsed,false,'Native call must not silently fall back');
  assert.equal(result.candidates.length,10);
  assert.deepEqual(result.activated,[result.candidates[0]]);
  assert.deepEqual(active,result.activated);
  assert.equal(requests.length,1,'Exactly one local native SDK request');
  assert.deepEqual(requests[0].keys,result.candidates);
  console.log('PASS: pinned pi-jev native ToolRouter/JevClient over local mock wire; UNSCORED');
} finally {
  delete process.env.PI_JEV_BASE_URL;
  await new Promise((resolveClose,reject)=>server.close(error=>error?reject(error):resolveClose()));
}
