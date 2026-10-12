import {test} from 'node:test';
import assert from 'node:assert/strict';
import {localURL,noPaidProvider,frozenInput,nativeResult,PI_JEV_SHA} from '../scripts/run_pi_jev_local_laya.mjs';
const catalog=Array.from({length:82},(_,i)=>({name:'t'+i,description:'d'}));
const cases=Array.from({length:16},(_,i)=>({id:'q'+i,query:'query '+i}));
const fixture={schema_version:1,pi_jev_commit:PI_JEV_SHA,top_k:3,external_execution:false,
  catalog,cases,catalog_sha256:'a'.repeat(64),cases_sha256:'b'.repeat(64)};
test('restrict to local unauthenticated HTTP',()=>{
  assert.equal(localURL('http://127.0.0.1:8000'),'http://127.0.0.1:8000');
  for(const u of ['https://localhost:8000','http://typesafe.ai','http://user:pass@localhost:8000',
      'http://localhost:8000?token=1','http://127.0.0.2:8000']) assert.throws(()=>localURL(u));
});
test('reject paid credentials',()=>{
  noPaidProvider({},'/unlikely/not/a/file');
  assert.throws(()=>noPaidProvider({TYPESAFE_API_KEY:'paid'},'/no/file'));
  assert.throws(()=>noPaidProvider({TYPESAFE_BASE_URL:'https://typesafe.ai'},'/no/file'));
});
test('frozen 82/16 fixture and Top-K3 are immutable',()=>{
  frozenInput(fixture);
  assert.throws(()=>frozenInput({...fixture,top_k:10}));
  assert.throws(()=>frozenInput({...fixture,catalog:[...catalog.slice(0,81),catalog[0]]}));
});
test('no fallback or forged activation; numeric probability + latency only',()=>{
  const valid={fallbackUsed:false,candidates:['t0','t1'],activated:['t1'],
    elapsedMs:5,probabilities:{t0:0.1,t1:0.9}};
  nativeResult(valid,catalog);
  for(const bad of [{...valid,fallbackUsed:true},{...valid,activated:['t2']},
      {...valid,candidates:['t0','t0']},{...valid,probabilities:{t0:0.1,t1:Infinity}},
      {...valid,elapsedMs:Infinity}]) assert.throws(()=>nativeResult(bad,catalog));
});
