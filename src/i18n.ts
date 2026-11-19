import {english} from './messages.js';
export type Locale = 'zh-CN'|'en';
export type LanguagePreference = 'system'|Locale;
const languageKey='yorevia.language';
export function normalizePreference(value:unknown):LanguagePreference{return value==='en'||value==='zh-CN'?value:'system';}
export function resolveLocale(value:LanguagePreference,languages:readonly string[]):Locale{
  if(value!=='system')return value;
  return languages[0]?.toLowerCase().startsWith('zh')?'zh-CN':'en';
}
let selected:LanguagePreference='system';
try{selected=normalizePreference(globalThis.localStorage?.getItem(languageKey));}catch{/* Private/blocked storage: keep an in-memory preference. */}
const listeners=new Set<()=>void>();
export function preference():LanguagePreference{return selected;}
export function locale():Locale{return resolveLocale(selected,typeof navigator==='undefined'?['zh-CN']:navigator.languages?.length?navigator.languages:[navigator.language]);}
function publish(){if(typeof document!=='undefined'&&document.documentElement){document.documentElement.lang=locale();document.title=locale()==='en'?'Yorevia · Your life atlas':'Yorevia · 往途';}for(const fn of listeners)fn();}
export function setPreference(value:unknown):void{selected=normalizePreference(value);try{globalThis.localStorage?.setItem(languageKey,selected);}catch{/* Session preference still works. */}publish();}
export function subscribe(listener:()=>void):()=>void{listeners.add(listener);return()=>listeners.delete(listener);}
if(typeof window!=='undefined'&&window.addEventListener){window.addEventListener('languagechange',()=>{if(selected==='system')publish();});window.addEventListener('storage',event=>{if(event.key===languageKey){selected=normalizePreference(event.newValue);publish();}});}
export function t(source:string,params:Record<string,string|number>={}):string{
  const message=locale()==='en'?(english[source]??source):source;
  return message.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g,(whole,key:string)=>Object.hasOwn(params,key)?String(params[key]):whole);
}
// Only app-owned, exact messages are translated. OS/library diagnostics and user data stay verbatim.
export function translateError(err:unknown):string{const message=err instanceof Error?err.message:String(err);const code=message.match(/^百度网盘拒绝请求（错误码 (-?\d+|未知)）。请检查授权、应用权限或稍后重试。$/);return code?t('百度网盘拒绝请求（错误码 {code}）。请检查授权、应用权限或稍后重试。',{code:code[1]==='未知'?(locale()==='en'?'unknown':'未知'):code[1]!}):t(message);}
publish();
