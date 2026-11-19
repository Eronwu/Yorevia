import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import {english} from '../dist/messages.js';
import {normalizePreference,resolveLocale,preference,setPreference,locale,t,translateError,subscribe} from '../dist/i18n.js';
import {personName,dateLabel} from '../dist/domain.js';
test('locale preference validation and system fallback',()=>{
 assert.equal(normalizePreference('fr'),'system');assert.equal(normalizePreference('en'),'en');
 for(const language of ['zh','zh-CN','zh-TW'])assert.equal(resolveLocale('system',[language]),'zh-CN');
 for(const language of ['en-US','fr-FR','ja-JP'])assert.equal(resolveLocale('system',[language]),'en');
 assert.equal(resolveLocale('zh-CN',['en-US']),'zh-CN');assert.equal(resolveLocale('en',['zh-CN']),'en');
});
test('local preference persists without writing user data; blocked storage is safe',()=>{
 const writes=[];Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{setItem:(...args)=>writes.push(args)}});
 let events=0;const stop=subscribe(()=>events++);setPreference('en');assert.equal(locale(),'en');assert.equal(preference(),'en');
 assert.deepEqual(writes,[['yorevia.language','en']]);assert.equal(events,1);stop();
 Object.defineProperty(globalThis,'localStorage',{configurable:true,get(){throw Error('blocked');}});
 assert.doesNotThrow(()=>setPreference('zh-CN'));delete globalThis.localStorage;
});
test('only app-owned labels translate, not names, diagnostics or parameter values',()=>{
 setPreference('en');assert.equal(t('时间待确认'),'Date unknown');
 assert.equal(personName({name:'时间待确认',id:'abcd'}),'时间待确认');
 assert.equal(personName({name:'',id:'abcd1234'}),'Unnamed abcd');
 assert.equal(t('未命名 {id}',{id:'故事 {id} <script>'}),'Unnamed 故事 {id} <script>');
 assert.equal(translateError(new Error('OS diagnostic /私人/path')),'OS diagnostic /私人/path');
 assert.equal(dateLabel('2014-01-01T00:10:00'),'2014-01-01');setPreference('zh-CN');
});
test('every literal interface translation has a complete English entry and matching placeholders',()=>{
 for(const file of ['app','baidu','bridge','domain']){
  const tree=ts.createSourceFile(file,readFileSync(`src/${file}.ts`,'utf8'),ts.ScriptTarget.Latest,true);
  function visit(node){
   if(ts.isCallExpression(node)&&node.expression.getText(tree)==='t'&&node.arguments[0]&&ts.isStringLiteral(node.arguments[0])){
    const key=node.arguments[0].text;assert.ok(Object.hasOwn(english,key),`${file}: missing ${key}`);
   }ts.forEachChild(node,visit);
  }visit(tree);
 }
 for(const [key,value] of Object.entries(english)){
  assert.ok(value.trim(),key);assert.deepEqual((key.match(/\{[A-Za-z]\w*\}/g)||[]).sort(),(value.match(/\{[A-Za-z]\w*\}/g)||[]).sort(),key);
 }
});
