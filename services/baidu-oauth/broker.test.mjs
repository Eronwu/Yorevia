import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {Broker,baiduProvider,verificationURL} from './broker.mjs';
const proof='a'.repeat(64), proof_hash=createHash('sha256').update(proof).digest('hex');
const device={device_code:'device-secret-fixture',user_code:'ABCD1234',verification_url:'https://openapi.baidu.com/device',expires_in:600,interval:5};
function fixture(options={}) {let clock=100000;let calls=0;const broker=new Broker({start:async()=>({...device}),poll:async()=>{calls++;return {access_token:'synthetic_token_12345',refresh_token:'never_return'};}},{now:()=>clock,...options});return {broker,tick:(n=5000)=>clock+=n,calls:()=>calls};}
async function session(broker){const d=await broker.start({proof_hash});return {session_id:d.session_id,proof};}
test('start exposes only user authorization fields, caps lifetime',async()=>{const {broker}=fixture();const d=await broker.start({proof_hash});assert.deepEqual(Object.keys(d).sort(),['expires_in','interval','session_id','user_code','verification_url']);assert.equal(d.expires_in,600);});
test('proof-bound single-use authorized response drops refresh token',async()=>{const {broker,tick}=fixture();const b=await session(broker);tick();await assert.rejects(()=>broker.poll({...b,proof:'b'.repeat(64)}),/invalid_session/);assert.deepEqual(await broker.poll(b),{status:'authorized',access_token:'synthetic_token_12345'});await assert.rejects(()=>broker.poll(b),/invalid_session/);});
test('early polling stays pending and does not contact provider',async()=>{const {broker,calls}=fixture();const b=await session(broker);assert.equal((await broker.poll(b)).status,'pending');assert.equal(calls(),0);});
test('expired sessions cannot poll or cancel',async()=>{const {broker,tick}=fixture();const b=await session(broker);tick(600001);await assert.rejects(()=>broker.poll(b),/expired/);assert.throws(()=>broker.cancel(b),/invalid_session/);});
test('cancel then poll cannot retrieve tokens',async()=>{const {broker,tick}=fixture();const b=await session(broker);assert.deepEqual(broker.cancel(b),{status:'cancelled'});tick();await assert.rejects(()=>broker.poll(b),/invalid_session/);});
test('concurrent poll calls cannot duplicate provider exchange',async()=>{const {broker,tick}=fixture();let resolve;broker.provider.poll=()=>new Promise(r=>{resolve=r;});const b=await session(broker);tick();const p=broker.poll(b);assert.equal((await broker.poll(b)).status,'pending');resolve({access_token:'synthetic_token_12345'});await p;await assert.rejects(()=>broker.poll(b),/invalid_session/);});
test('cancellation during provider request wins',async()=>{const {broker,tick}=fixture();let resolve;broker.provider.poll=()=>new Promise(r=>{resolve=r;});const b=await session(broker);tick();const p=broker.poll(b);broker.cancel(b);resolve({access_token:'synthetic_token_12345'});await assert.rejects(()=>p,/invalid_session/);});
test('expiry during provider request wins',async()=>{const {broker,tick}=fixture();let resolve;broker.provider.poll=()=>new Promise(r=>{resolve=r;});const b=await session(broker);tick();const p=broker.poll(b);tick(600000);resolve({access_token:'synthetic_token_12345'});await assert.rejects(()=>p,/expired/);});
test('session and global start bounds include in-flight starts',async()=>{const {broker}=fixture({maxSessions:1});let resolve;broker.provider.start=()=>new Promise(r=>{resolve=r;});const p=broker.start({proof_hash});await assert.rejects(()=>broker.start({proof_hash}),/busy/);resolve(device);await p;});
test('global rate limit and expired sessions sweeping',async()=>{const {broker,tick}=fixture({maxStartsPerMinute:1,maxSessions:1});await session(broker);await assert.rejects(()=>broker.start({proof_hash}),/busy/);tick(600001);await session(broker);assert.equal(broker.sessions.size,1);});
test('denied and slow_down responses normalized',async()=>{const {broker,tick}=fixture();const b=await session(broker);broker.provider.poll=async()=>({error:'slow_down',error_description:'SECRET'});tick();assert.deepEqual(await broker.poll(b),{status:'pending',interval:10});tick(10000);broker.provider.poll=async()=>({error:'access_denied',error_description:'SECRET'});await assert.rejects(()=>broker.poll(b),/^Error: denied$/);});
test('verification URL rejects external destinations and URL credentials',()=>{for(const url of ['http://openapi.baidu.com/device','https://evil.test/device','https://openapi.baidu.com.evil.test/device','https://x@openapi.baidu.com/device','https://openapi.baidu.com/device?code=secret','https://openapi.baidu.com/device#x'])assert.throws(()=>verificationURL(url));});
test('upstream errors redact sensitive diagnostics',async()=>{const {broker,tick}=fixture();const b=await session(broker);broker.provider.poll=async()=>{throw new Error('SECRET');};tick();await assert.rejects(()=>broker.poll(b),/^Error: provider_error$/);});
test('provider uses official device endpoints with no redirects and bounds response',async()=>{const calls=[];const p=baiduProvider({appKey:'synthetic-app',secretKey:'synthetic-secret',fetchImpl:async(url,opts)=>{calls.push({url,opts});return new Response('{}');}});await p.start();await p.poll('device-fixture');assert.equal(calls[0].url.origin,'https://openapi.baidu.com');assert.equal(calls[0].url.pathname,'/oauth/2.0/device/code');assert.equal(calls[0].url.searchParams.get('scope'),'basic,netdisk');assert.equal(calls[1].url.searchParams.get('grant_type'),'device_token');assert.equal(calls[1].opts.redirect,'error');});
test('oversized provider responses rejected',async()=>{const p=baiduProvider({appKey:'synthetic-app',secretKey:'synthetic-secret',fetchImpl:async()=>new Response('x'.repeat(65537))});await assert.rejects(()=>p.start(),/^Error: provider_error$/);});
test('rejects coerced proof inputs',async()=>{const {broker}=fixture();await assert.rejects(()=>broker.start({proof_hash:[proof_hash]}),/invalid_request/);const b=await session(broker);await assert.rejects(()=>broker.poll({...b,proof:[proof]}),/invalid_session/);});
test('HTTP transport rejects browsers/methods, serves only no-store JSON',async()=>{
  const {createServer}=await import('./server.mjs');const {broker}=fixture();const server=createServer(broker);
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  try{
    const base=`http://127.0.0.1:${server.address().port}`;
    const get=await fetch(base+'/v1/device/start');assert.equal(get.status,400);assert.equal(get.headers.get('cache-control'),'no-store');
    const browser=await fetch(base+'/v1/device/start',{method:'POST',headers:{'Content-Type':'application/json',Origin:'https://evil.test'},body:JSON.stringify({proof_hash})});assert.equal(browser.status,400);assert.equal(browser.headers.get('access-control-allow-origin'),null);
    const start=await fetch(base+'/v1/device/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({proof_hash})});assert.equal(start.status,200);assert.equal((await start.json()).verification_url,'https://openapi.baidu.com/device');
    const invalid=await fetch(base+'/v1/device/start',{method:'POST',headers:{'Content-Type':'application/json'},body:'{'});assert.deepEqual(await invalid.json(),{error:'invalid_request'});
  }finally{await new Promise(resolve=>server.close(resolve));}
});
test('OAuth HTTP 400 retains allowed control errors but never accepts tokens',async()=>{
  const provider=(data,status=400)=>baiduProvider({appKey:'synthetic-app',secretKey:'synthetic-secret',fetchImpl:async()=>new Response(JSON.stringify(data),{status})});
  for(const error of ['authorization_pending','slow_down','access_denied','expired_token'])assert.deepEqual(await provider({error,error_description:'SECRET'}).poll('fixture'),{error});
  await assert.rejects(()=>provider({access_token:'synthetic_token_12345'}).poll('fixture'),/^Error: provider_error$/);
  await assert.rejects(()=>provider({error:'untrusted-upstream-text'}).poll('fixture'),/^Error: provider_error$/);
  await assert.rejects(()=>provider({error:'authorization_pending'},500).poll('fixture'),/^Error: provider_error$/);
});
