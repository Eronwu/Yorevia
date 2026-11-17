import {test} from 'node:test';
import assert from 'node:assert/strict';
import {escapeHTML,dateLabel,dateEvidence,groupAssets,graphPositions} from '../dist/domain.js';
test('untrusted text never becomes active HTML',()=>assert.equal(escapeHTML('<img onerror="x">&'), '&lt;img onerror=&quot;x&quot;&gt;&amp;'));
test('unknown dates are explicit',()=>assert.equal(dateLabel(null),'时间待确认'));
test('filename inference is labelled',()=>assert.equal(dateEvidence('filename'),'文件名推测'));
test('calendar date is not timezone shifted',()=>assert.equal(dateLabel('2014-01-01T00:10:00'),'2014 年 1 月 1 日'));
test('grouping preserves undated material',()=>assert.equal(groupAssets([{captured_at:null},{captured_at:null}])[0][1].length,2));
test('graph layout handles zero and one node',()=>{assert.deepEqual(graphPositions(0),[]);assert.deepEqual(graphPositions(1),[{x:480,y:290}]);});
test('graph layout stays within canvas',()=>{for(const p of graphPositions(24))assert.ok(p.x>=0&&p.x<=960&&p.y>=0&&p.y<=580);});

test('Baidu modal drains old queued close and repeated opening does not strand status',async()=>{
  const calls=[];
  globalThis.window={__TAURI__:{core:{invoke:async(_cmd,args)=>{calls.push(args.method);return {connected:false};}}}};
  globalThis.location={search:''};
  const {showBaidu}=await import('../dist/baidu.js');
  class Dialog extends EventTarget{
    open=true;innerHTML='';form={};input={value:''};
    close(){if(!this.open)return;this.open=false;setTimeout(()=>this.dispatchEvent(new Event('close')),0);}
    showModal(){this.open=true;}
    querySelector(selector){return selector==='form'?this.form:this.input;}
  }
  const modal=new Dialog();
  const fail=()=>assert.fail('unexpected error');
  await Promise.all([showBaidu(modal,async()=>{},fail),showBaidu(modal,async()=>{},fail)]);
  await new Promise(resolve=>setTimeout(resolve,5));
  assert.ok(modal.open);
  assert.match(modal.innerHTML,/Access Token/);
  assert.doesNotMatch(modal.innerHTML,/正在检查连接/);
  assert.deepEqual(calls,['baidu.status']);
  modal.close();await new Promise(resolve=>setTimeout(resolve,5));
  await showBaidu(modal,async()=>{},fail);
  assert.match(modal.innerHTML,/Access Token/);
  modal.close();await new Promise(resolve=>setTimeout(resolve,5));
});

test('Baidu OAuth closing during start cancels the late attempt without displaying a code',async()=>{
  const calls=[];let finish;let login;
  globalThis.document={createElement:tag=>({append(){},before(){},set textContent(value){if(value==='使用百度账号授权（测试版）')login=this;}})};
  globalThis.window={__TAURI__:{core:{invoke:async(_cmd,args)=>{
    calls.push(args);
    if(args.method==='baidu.status')return {connected:false,oauth_available:true};
    if(args.method==='baidu.auth.start')return new Promise(resolve=>finish=resolve);
    return {ok:true};
  }}}};
  globalThis.location={search:''};
  const {showBaidu}=await import('../dist/baidu.js');
  class Dialog extends EventTarget{
    open=false;innerHTML='';form={before(){}};input={value:''};
    close(){if(!this.open)return;this.open=false;setTimeout(()=>this.dispatchEvent(new Event('close')),0);}
    showModal(){this.open=true;}
    querySelector(selector){return selector==='form'?this.form:this.input;}
  }
  const modal=new Dialog();await showBaidu(modal,async()=>{},()=>assert.fail());
  assert.ok(login);login.onclick();
  assert.ok(finish);modal.close();await new Promise(resolve=>setTimeout(resolve,5));
  finish({user_code:'TEST1234',verification_url:'https://openapi.baidu.com/device',interval:5,browser_opened:true});
  await new Promise(resolve=>setTimeout(resolve,5));
  assert.doesNotMatch(modal.innerHTML,/TEST1234/);
  assert.ok(calls.some(c=>c.method==='baidu.auth.cancel'));
  assert.ok(!calls.some(c=>c.method==='baidu.auth.poll'));
});
