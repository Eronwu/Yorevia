import {rpc, chooseFolder, isDemo} from './bridge.js';
import {escapeHTML as e} from './domain.js';
interface Entry {id:string;name:string;path:string;directory:boolean;size:number;supported:boolean}
interface Listing {items:Entry[];directory:string;page:number;has_more:boolean}
let invocation=0;
let pendingClose:Promise<void>|null=null;
// A developer-only bridge until the public OAuth service is deployed. No credential storage.
export async function showBaidu(modal:HTMLDialogElement, beginJob:(method:string,p:Record<string,unknown>)=>Promise<void>, onError:(err:unknown)=>void){
  if(isDemo)throw new Error('示例不会连接真实网盘，请使用桌面版或本地开发预览。');
  const current=++invocation;
  // close() queues an event: finish it before installing this session's listener.
  // Repeated clicks share the pending close, and only the newest invocation opens.
  if(modal.open&&!pendingClose){
    pendingClose=new Promise<void>(resolve=>{
      modal.addEventListener('close',()=>{pendingClose=null;resolve();},{once:true});
      modal.close();
    });
  }
  if(pendingClose)await pendingClose;
  if(current!==invocation)return;
  let generation=0;
  modal.addEventListener('close',()=>{generation++;const input=modal.querySelector<HTMLInputElement>('input[type=password]');if(input)input.value='';},{once:true});
  const shell=(body:string)=>{modal.innerHTML=`<button class="modal-close" data-action="close-modal" aria-label="关闭">×</button><h2>百度网盘 · 开发者预览</h2>${body}<p role="alert" id="baidu-error"></p>`;};
  const failure=(err:unknown)=>{const el=modal.querySelector('#baidu-error');if(el)el.textContent=err instanceof Error?err.message:'网盘请求失败';};
  const connect=()=>{
    shell('<p>仅供已取得授权的开发者测试。目前尚未接入面向普通用户的登录服务。</p><p class="hint">输入百度网盘 Access Token（不是应用 SecretKey）。令牌仅在本次应用进程中保留，退出或断开即清除；不会写入资料库。请勿将令牌发到聊天或提交 GitHub。</p><form><label>Access Token<input type="password" name="token" autocomplete="off" required maxlength="4096"></label><button class="button primary" type="submit">连接并浏览</button></form>');
    modal.querySelector('form')!.onsubmit=async event=>{
      event.preventDefault();const input=modal.querySelector<HTMLInputElement>('input')!;const token=input.value;input.value='';
      const button=modal.querySelector<HTMLButtonElement>('[type=submit]')!;button.disabled=true;const gen=++generation;const connectionId=crypto.randomUUID();
      try{const listing=await rpc<Listing>('baidu.connect',{access_token:token,connection_id:connectionId});if(modal.open&&gen===generation)browse(listing);else await rpc('baidu.disconnect',{connection_id:connectionId});}catch(err){if(gen===generation){failure(err);button.disabled=false;}}
    };
  };
  const load=async(directory:string,page=0)=>{
    const gen=++generation;modal.querySelectorAll<HTMLButtonElement>('button:not(.modal-close)').forEach(b=>b.disabled=true);
    try{const listing=await rpc<Listing>('baidu.list',{directory,page});if(modal.open&&gen===generation)browse(listing);}catch(err){if(gen===generation){failure(err);modal.querySelectorAll<HTMLButtonElement>('button').forEach(b=>b.disabled=false);}}
  };
  const browse=(listing:Listing)=>{
    shell(`<p class="hint">只下载你勾选的文件，不递归导入文件夹，不修改网盘原件。每次最多 100 个文件、2 GiB，单文件最多 1 GiB。选择仅限当前页。</p><p class="path">${e(listing.directory)}</p><div><button class="button secondary" id="baidu-up" ${listing.directory==='/'?'disabled':''}>上一级</button> <button class="text-button" id="baidu-disconnect">断开连接</button></div><form><div class="baidu-files">${listing.items.map((item,index)=>item.directory?`<div><button type="button" class="text-button" data-baidu-folder="${index}">📁 ${e(item.name)}</button></div>`:`<label class="check-field"><input type="checkbox" name="file" value="${e(item.id)}" ${!item.supported||item.size>1024**3?'disabled':''}>${e(item.name)} · ${(item.size/1024/1024).toFixed(1)} MiB${!item.supported?'（暂不支持）':''}</label>`).join('')||'<p>此目录为空。</p>'}</div><p>第 ${listing.page+1} 页 <button type="button" class="text-button" id="baidu-prev" ${!listing.page?'disabled':''}>上一页</button><button type="button" class="text-button" id="baidu-next" ${!listing.has_more?'disabled':''}>下一页</button></p><button class="button primary" type="submit">选择本地位置并导入勾选文件</button></form><p class="hint">会在你选择的位置新建专用文件夹，再索引到人生资料库。下载需要网络并占用本地磁盘；文件不会传到 Yorevia 服务器。取消后已下载文件保留，可在资料来源中增量扫描。</p>`);
    modal.querySelector('#baidu-up')!.addEventListener('click',()=>void load(listing.directory.replace(/\/[^/]+\/?$/,'')||'/'));
    modal.querySelector('#baidu-prev')!.addEventListener('click',()=>void load(listing.directory,listing.page-1));
    modal.querySelector('#baidu-next')!.addEventListener('click',()=>void load(listing.directory,listing.page+1));
    modal.querySelectorAll<HTMLElement>('[data-baidu-folder]').forEach(b=>b.addEventListener('click',()=>void load(listing.items[Number(b.dataset.baiduFolder)]!.path)));
    modal.querySelector('#baidu-disconnect')!.addEventListener('click',async()=>{const gen=++generation;try{await rpc('baidu.disconnect');if(modal.open&&gen===generation)connect();}catch(err){failure(err);}});
    modal.querySelector('form')!.onsubmit=async event=>{
      event.preventDefault();const form=event.currentTarget as HTMLFormElement;const ids=new FormData(form).getAll('file');
      if(!ids.length){failure(new Error('请先勾选文件。'));return;}
      const gen=++generation;form.querySelectorAll<HTMLButtonElement>('button').forEach(b=>b.disabled=true);
      try{const destination=await chooseFolder('选择网盘文件的本地保存位置（资料库以外）');if(!modal.open||gen!==generation)return;if(!destination){browse(listing);return;}modal.close();await beginJob('baidu.import',{ids,destination});}catch(err){if(modal.open)failure(err);else onError(err);}finally{form.querySelectorAll<HTMLButtonElement>('button').forEach(b=>b.disabled=false);}
    };
  };
  shell('<p>正在检查连接…</p>');modal.showModal();
  const gen=generation;
  try{const status=await rpc<{connected:boolean}>('baidu.status');if(!modal.open||gen!==generation)return;if(status.connected)await load('/');else connect();}catch(err){failure(err);}
}
