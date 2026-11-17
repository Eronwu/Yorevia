import {createHash, randomBytes, timingSafeEqual} from 'node:crypto';
export class BrokerError extends Error {
  constructor(code, status=400, interval) { super(code); this.status=status; this.interval=interval; }
}
const fail=(code,status=400,interval)=>{throw new BrokerError(code,status,interval);};
const hash=value=>createHash('sha256').update(value).digest();
const sessionPattern=/^[A-Za-z0-9_-]{43}$/;
const proofPattern=/^(?:[A-Za-z0-9_-]{43}|[0-9a-f]{64})$/;
export function verificationURL(value) {
  const u=new URL(value);
  if(u.protocol!=='https:' || u.hostname!=='openapi.baidu.com' || u.port || u.username || u.password || u.hash || u.search || u.pathname!=='/device')throw new Error('invalid_provider');
  return u.href;
}
// One process, bounded memory, fail closed across restarts. Never log request bodies.
export class Broker {
  constructor(provider,{now=Date.now,maxSessions=500,maxStartsPerMinute=30}={}) {
    this.provider=provider; this.now=now; this.maxSessions=maxSessions;
    this.maxStarts=maxStartsPerMinute; this.sessions=new Map(); this.starts=[]; this.starting=0;
  }
  sweep() { for(const [id,s] of this.sessions)if(s.expires<=this.now())this.sessions.delete(id); }
  async start(body) {
    if(!body || typeof body.proof_hash!=='string' || !/^[0-9a-f]{64}$/.test(body.proof_hash))fail('invalid_request');
    this.sweep();const now=this.now();this.starts=this.starts.filter(x=>x>now-60000);
    if(this.starts.length>=this.maxStarts || this.sessions.size+this.starting>=this.maxSessions)fail('busy',429);
    this.starts.push(now);this.starting++;
    try {
      const d=await this.provider.start();
      const url=verificationURL(d.verification_url);
      if(typeof d.device_code!=='string'||d.device_code.length<8||d.device_code.length>4096||typeof d.user_code!=='string'||!/^[A-Za-z0-9-]{4,32}$/.test(d.user_code)||!Number.isInteger(d.expires_in)||d.expires_in<1)fail('provider_error',502);
      const interval=Math.max(5,Math.min(60,Number.isInteger(d.interval)?d.interval:5));
      const expires_in=Math.min(600,d.expires_in);const id=randomBytes(32).toString('base64url');
      this.sessions.set(id,{proof:Buffer.from(body.proof_hash,'hex'),code:d.device_code,expires:this.now()+expires_in*1000,next:this.now()+interval*1000,interval,busy:false});
      return {session_id:id,verification_url:url,user_code:d.user_code,interval,expires_in};
    } catch(e) { if(e instanceof BrokerError)throw e;fail('provider_error',502); }
    finally {this.starting--;}
  }
  session(body) {
    if(!body||typeof body.session_id!=='string'||typeof body.proof!=='string'||!sessionPattern.test(body.session_id)||!proofPattern.test(body.proof))fail('invalid_session');
    const s=this.sessions.get(body.session_id);
    if(!s||!timingSafeEqual(s.proof,hash(body.proof)))fail('invalid_session');
    if(s.expires<=this.now()){this.sessions.delete(body.session_id);fail('expired');}
    return s;
  }
  cancel(body) {this.session(body);this.sessions.delete(body.session_id);return {status:'cancelled'};}
  async poll(body) {
    const s=this.session(body);
    if(s.busy||this.now()<s.next)return {status:'pending',interval:s.interval};
    s.busy=true;s.next=this.now()+s.interval*1000;
    try {
      const d=await this.provider.poll(s.code);
      // Cancellation/expiration wins, including while provider request is in flight.
      if(this.sessions.get(body.session_id)!==s)fail('invalid_session');
      if(s.expires<=this.now()){this.sessions.delete(body.session_id);fail('expired');}
      if(d.error==='authorization_pending')return {status:'pending',interval:s.interval};
      if(d.error==='slow_down'){s.interval=Math.min(60,s.interval+5);s.next=this.now()+s.interval*1000;return {status:'pending',interval:s.interval};}
      if(d.error){this.sessions.delete(body.session_id);fail('denied');}
      if(typeof d.access_token!=='string'||!/^[A-Za-z0-9._~-]{10,4096}$/.test(d.access_token))fail('provider_error',502);
      // Consume before returning. A lost response requires reauthorization, never replay.
      this.sessions.delete(body.session_id);
      return {status:'authorized',access_token:d.access_token};
    } catch(e) {if(e instanceof BrokerError)throw e;fail('provider_error',502);}
    finally {s.busy=false;}
  }
}
export function baiduProvider({appKey,secretKey,fetchImpl=fetch}) {
  if(!appKey||!secretKey)throw new Error('Missing server credentials');
  async function request(path,params) {
    // Official SDK currently uses GET; transport/proxy logging must redact URL queries.
    const u=new URL(path,'https://openapi.baidu.com');u.search=new URLSearchParams(params);
    try {
      const r=await fetchImpl(u,{redirect:'error',signal:AbortSignal.timeout(15000),headers:{Accept:'application/json'}});
      if((!r.ok&&r.status!==400)||!r.body)throw new Error();
      const chunks=[];let size=0;
      for await(const chunk of r.body){size+=chunk.byteLength;if(size>65536)throw new Error();chunks.push(Buffer.from(chunk));}
      const d=JSON.parse(Buffer.concat(chunks).toString());if(!d||typeof d!=='object'||Array.isArray(d))throw new Error();
      if(!r.ok){
        if(!['authorization_pending','slow_down','access_denied','authorization_declined','expired_token','invalid_grant'].includes(d.error))throw new Error();
        return {error:d.error};
      }
      return d;
    }catch{throw new Error('provider_error');}
  }
  return {start:()=>request('/oauth/2.0/device/code',{response_type:'device_code',client_id:appKey,scope:'basic,netdisk'}),poll:code=>request('/oauth/2.0/token',{grant_type:'device_token',code,client_id:appKey,client_secret:secretKey})};
}
