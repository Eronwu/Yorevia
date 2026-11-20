import {locale,t} from './i18n.js';
import type { Invoke } from './types.js';
import { demoCall } from './demo.js';
export const isLocalWeb=window.__YOREVIA_LOCAL_WEB__===true;
export const isDesktop=Boolean(window.__TAURI__);
export const isDemo=new URLSearchParams(location.search).get('demo')==='1';
const invoke:Invoke=(command,args)=>{
  if(!window.__TAURI__)return Promise.reject(new Error(t('此操作需要桌面版本。')));
  return window.__TAURI__.core.invoke(command,args);
};
export async function rpc<T>(method:string,params:Record<string,unknown>={}):Promise<T>{
  if(isDemo)return demoCall<T>(method,params);
  if(isDesktop)return invoke<T>('rpc',{method,params});
  if(!window.__YOREVIA_TOKEN__)throw new Error(t('请使用桌面版本，或通过 python scripts/preview.py 启动本地开发预览。'));
  const response=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json','X-Yorevia-Token':window.__YOREVIA_TOKEN__},body:JSON.stringify({method,params})});
  const data=await response.json() as {result:T;error?:{message:string}};
  if(!response.ok || data.error)throw new Error(data.error?.message || t('本地请求失败'));
  return data.result;
}
export async function chooseFolder(title:string,purpose?:'vault.open'|'source.add'|'baidu.import'):Promise<string|null>{
  if(isDemo)throw new Error(t('示例不会读取你的文件。请打开桌面版以连接资料。'));
  if(isDesktop)return invoke<string|null>('choose_folder',{title});
  if(isLocalWeb){
    if(!purpose)throw new Error(t('请选择操作后再打开文件夹。'));
    return rpc<string|null>('local.pick',{purpose,locale:locale()});
  }
  return window.prompt(title+t('\n开发预览：请输入这台电脑上的完整目录路径。'));
}
export async function revealAsset(assetId:string):Promise<void>{
  if(isDesktop){await invoke('reveal_asset',{assetId});return;}
  const result=await rpc<{path:string}>('asset.path',{asset_id:assetId});
  window.prompt(t('原始文件路径（只读访问）'),result.path);
}
