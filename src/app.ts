import {t,locale,preference,setPreference,subscribe,translateError} from './i18n.js';
import {showBaidu} from './baidu.js';
import type { AssetDetail, Graph, Job, Person, Status, Story, Summary, Timeline } from './types.js';
import {chooseFolder,isDemo,isDesktop,isLocalWeb,revealAsset,rpc} from './bridge.js';
import {dateEvidence,dateLabel,escapeHTML as e,graphPositions,groupAssets,personName} from './domain.js';

type View='timeline'|'people'|'stories'|'settings';
const root=document.querySelector<HTMLDivElement>('#app')!;
const modal=document.querySelector<HTMLDialogElement>('#modal')!;
const state:{view:View;summary:Summary|null;status:Status|null;year:string;query:string;person:string|null;
  people:Person[];timeline:Timeline;graph:Graph|null;stories:Story[];job:Job|null;lastJob:Job|null;loading:boolean}={
  view:'timeline',summary:null,status:null,year:'all',query:'',person:null,people:[],
  timeline:{items:[],total:0,offset:0,limit:60},graph:null,stories:[],job:null,lastJob:null,loading:false};
let revision=0,searchTimer:ReturnType<typeof setTimeout>,toastTimer:ReturnType<typeof setTimeout>;
const imageCache=new Map<string,string>();
let observer:IntersectionObserver|null=null;
const icon=(name:string)=>`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${({
  timeline:'<path d="M6 3v18M10 6h10M10 12h6M10 18h8"/><circle cx="6" cy="6" r="2" fill="currentColor"/><circle cx="6" cy="12" r="2" fill="currentColor"/><circle cx="6" cy="18" r="2" fill="currentColor"/>',
  people:'<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5"/>',
  stories:'<path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4zM13 7a3 3 0 0 1 3-3h5v15h-4a4 4 0 0 0-4 2"/>',
  settings:'<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 15h8"/><circle cx="10" cy="9" r="2" fill="var(--paper)"/><circle cx="14" cy="15" r="2" fill="var(--paper)"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
  lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
  folder:'<path d="M3 7V5h6l2 2h10v13H3z"/>',arrow:'<path d="M4 12h15m-6-6 6 6-6 6"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',download:'<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
  leaf:'<path d="M20 3C8 2 2 8 5 15s15 4 15-12ZM5 21 15 9"/>',photo:'<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m3 17 5-4 4 3 5-6 4 5"/>',
  play:'<path d="m9 5 10 7-10 7z"/>',check:'<path d="m5 12 4 4L19 6"/>'
} as Record<string,string>)[name]||''}</svg>`;
const brand=`<svg class="brand-mark" viewBox="0 0 40 48" fill="none" aria-hidden="true"><path d="M5 8c0 15 15 14 15 32M35 8c0 15-15 14-15 32M20 4v19" stroke="currentColor" stroke-width="1.4"/><circle cx="5" cy="7" r="3" fill="currentColor"/><circle cx="35" cy="7" r="3" fill="currentColor"/><circle cx="20" cy="3" r="2" fill="currentColor"/></svg>`;
function toast(message:string){const el=document.querySelector<HTMLDivElement>('#toast')!;el.textContent=message;el.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('visible'),6000);}
function error(err:unknown){toast(translateError(err));}
function avatar(p:Person,size=''):string{return `<span class="avatar ${size}" aria-hidden="true">${p.face_id?`<img data-face="${e(p.face_id)}" alt="">`:`<span>${e(p.name?.slice(0,1)||'·')}</span>`}</span>`;}
function labelMonth(key:string){
  if(key==='unknown')return e(t("留待想起的时刻"));
  const date=new Date(key+'-01T00:00:00Z');
  return Number.isNaN(date.getTime())?e(key):e(new Intl.DateTimeFormat(locale(),{year:'numeric',month:'long',timeZone:'UTC'}).format(date));
}
function yearLabel(){
  if(state.year==='all')return t("全部时光");
  if(state.year==='unknown')return t("时间待确认");
  return t("{year} 年",{year:state.year});
}
function languagePicker(){
  const labels={system:t("跟随系统"),'zh-CN':'简体中文',en:'English'} as const;
  return `<label class="language-picker">${e(t("界面语言"))} <select id="app-language">${Object.entries(labels).map(([value,label])=>`<option value="${value}"${preference()===value?' selected':''}>${e(label)}</option>`).join('')}</select></label>`;
}
function shell(){
  const s=state.summary;
  const names:{id:View;name:string;en:string}[]=[{id:'timeline',name:t("人生长廊"),en:'TIMELINE'},{id:'people',name:t("同行的人"),en:'PEOPLE'},{id:'stories',name:t("故事手记"),en:'STORIES'}];
  return `<aside class="sidebar"><button class="brand" data-action="home">${brand}<span>Yorevia${locale()==='zh-CN'?'<small>往 途</small>':''}</span></button>
    <nav class="nav-main" aria-label="${e(t("主要视图"))}">${names.map(n=>`<button class="nav-item ${state.view===n.id?'active':''}" data-view="${n.id}">${icon(n.id)}<span>${n.name}${locale()==='zh-CN'?`<small>${n.en}</small>`:''}</span>${state.view===n.id?'<i></i>':''}</button>`).join('')}</nav>
    <div class="year-nav"><div class="eyebrow">${e(t("人生篇章"))}</div><button class="year ${state.year==='all'?'selected':''}" data-year="all">${e(t("全部时光"))}<span>—</span></button>
      ${(s?.years||[]).map(y=>`<button class="year ${state.year===y?'selected':''}" data-year="${e(y)}">${e(y)}<span>·</span></button>`).join('')}
      ${(s?.unknown_dates||0)>0?`<button class="year muted ${state.year==='unknown'?'selected':''}" data-year="unknown">${e(t("时间待确认"))}<span>${s!.unknown_dates}</span></button>`:''}</div>
    <div class="sidebar-bottom"><button class="nav-item ${state.view==='settings'?'active':''}" data-view="settings">${icon('settings')}<span>${e(t("资料与隐私"))}</span></button><div class="local-note">${icon('lock')}<span>${e(t("记忆留在你的设备上"))}<br><small>${e(t("无账号 · 无上传 · 无遥测"))}</small></span></div></div></aside>
    <main><header class="topbar"><span class="breadcrumb">${e(t("我的人生"))} <span>/</span> ${names.find(n=>n.id===state.view)?.name||t("资料与隐私")}</span><div class="top-actions">${isDemo?`<span class="demo-tag">${e(t("虚构示例 · 只读"))}</span><button class="text-button" data-action="exit-demo">${e(t("退出示例"))}</button>`:`<span class="privacy-dot">${isDesktop?t("本地模式"):isLocalWeb?t("本地网页版"):t("本地开发预览")}</span>`}<button class="button primary small" data-action="add-source">${icon('plus')}${e(t("连接资料"))}</button></div></header>
      <section id="content">${renderPage()}</section><footer class="footer">${e(t("你的人生，你的记忆，你的文件。"))}<span>Yorevia · 0.1 Alpha</span></footer></main>
      ${state.job?`<aside class="job" aria-live="polite"><span class="spinner"></span><div><strong>${e(state.job.label)}</strong><small>${state.job.done} / ${state.job.total||'…'} ${e(t("· 本地整理 / 已选网盘文件下载"))}</small><progress max="${state.job.total||1}" value="${state.job.done}"></progress></div><button class="text-button" data-action="cancel-job">${e(t("取消"))}</button></aside>`:''}`;
}
function render(){const scroll=document.querySelector('main')?.scrollTop||0;root.innerHTML=shell();const main=document.querySelector('main');if(main)main.scrollTop=scroll;hydrateImages();}
function welcome(){return `<div class="welcome">${languagePicker()}${state.status?.local_web_startup_error?`<p class="warning" role="status">${e(t("未能打开上次的资料库。请确认磁盘已连接且资料库未在其他进程打开，或重新选择。没有创建新库。"))}</p>`:''}<div class="eyebrow">${e(t("私人的人生地图"))}</div><h1>${e(t("散落的记忆，"))}<br>${e(t("终会成为"))}${locale()==='en'?' ':''}<span>${e(t("来时的路。"))}</span></h1><p>${e(t("不必从第一句话开始。"))}<br>${e(t("连接你的照片、视频和旧日文字，"))}<br>${e(t("沿着时光，重新看见曾经同行的人。"))}</p><button class="button primary large" data-action="open-vault">${icon('folder')}${e(t("创建或打开人生资料库"))}${icon('arrow')}</button><a class="quiet-link" href="?demo=1">${e(t("先漫步一段示例人生 ↗"))}</a><div class="welcome-art" aria-hidden="true"><div class="art-ring ring-one"></div><div class="art-ring ring-two"></div><div class="paper-card card-one"><span>2008</span><i></i><small>${e(t("在某处开始。"))}</small></div><div class="paper-card card-two"><span>2016</span><i></i><small>${e(t("一路同行的人。"))}</small></div><div class="paper-card card-three"><span>2023</span><i></i><small>${e(t("仍在路上。"))}</small></div></div><div class="welcome-promise">${icon('leaf')}${e(t("原始文件保持原位。故事、头像与索引，都属于你。"))}</div></div>`;}
function pageHeader(eyebrow:string,title:string,description:string,extra=''){return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div>${extra}</div>`;}
function empty(title:string,body:string,button=''){return `<div class="empty"><span class="empty-mark">${brand}</span><h3>${title}</h3><p>${body}</p>${button}</div>`;}
function filterBar(){const person=state.people.find(p=>p.id===state.person);return `<div class="filterbar"><div class="filter-caption">${e(yearLabel())}<span> / ${state.timeline.total} ${e(t("份资料"))}</span>${person?`<button class="chip" data-action="clear-person">${e(personName(person))} ×</button>`:''}</div><label class="search">${icon('search')}<input id="search" placeholder="${e(t("寻找一段记忆…"))}" value="${e(state.query)}" aria-label="${e(t("搜索标题、日记和故事"))}"></label></div>`;}
function renderPage():string{
  if(!state.summary)return welcome();
  if(state.view==='settings')return settingsPage();
  if(state.view==='people')return peoplePage();
  if(state.view==='stories')return storiesPage();
  const selected=state.year!=='all'&&state.year!=='unknown';
  const heading=selected?`${e(state.year)}<span class="title-divider"> / </span>${e(t("沿途，有你们。"))}`:`${e(t("把时光，"))}${locale()==='en'?' ':''}<span>${e(t("重新连起来。"))}</span>`;
  const peopleStrip=state.people.length?`<section class="people-strip"><div class="strip-heading"><span>${e(t("这一段时光的同行者"))}</span><button class="text-button" data-view="people">${e(t("展开人物图谱"))} ${icon('arrow')}</button></div><div class="avatar-row">${state.people.slice(0,8).map(p=>`<button class="person-mini" data-person="${e(p.id)}">${avatar(p)}<span>${e(personName(p))}</span><small>${p.count} ${e(t("份影像"))}</small></button>`).join('')}<button class="person-mini add-person" data-action="analyze-faces"><span class="avatar">${icon('plus')}</span><span>${e(t("归类更多人像"))}</span><small>${e(t("仅本地分析"))}</small></button></div></section>`:`<section class="people-invitation">${icon('people')}<div><strong>${e(t("找回那些曾经同行的人"))}</strong><p>${e(t("你同意后，照片中的人像将在本地归类。名字与真实关系，由你来确认。"))}</p></div><button class="button secondary" data-action="analyze-faces">${e(t("开始本地人像分析"))}</button></section>`;
  const grid=groupAssets(state.timeline.items).map(([key,items])=>`<section class="timeline-group"><div class="month-label"><span class="time-dot"></span><h2>${labelMonth(key)}</h2><small>${items.length} ${e(t("份记忆"))}</small></div><div class="memory-grid">${items.map(a=>`<button class="memory-card ${a.kind==='note'?'note-card':''}" data-asset="${e(a.id)}"><div class="memory-image">${(a.thumb||a.remote_photo)?`<img ${a.remote_photo?'data-remote-photo="1"':''} data-media="${e(a.id)}" alt="${e(a.title)}">`:`<div class="media-placeholder">${icon(a.kind==='note'?'stories':a.kind==='video'?'play':'photo')}<span>${a.kind==='note'?t("那时写下的话"):t("暂时没有预览")}</span></div>`}${a.kind==='video'?`<span class="video-mark">${icon('play')}</span>`:''}${!a.available?`<span class="offline-tag">${e(t("原文件离线"))}</span>`:''}</div><div class="memory-caption"><span>${e(a.title)}</span><small>${a.captured_at?e(a.captured_at.slice(0,10)):t("日期待确认")}<i> ${a.story_count?t("· 已有故事"):a.people_count?`· ${a.people_count} ${e(t("位人物"))}`:''}</i></small></div></button>`).join('')}</div></section>`).join('');
  return pageHeader(t("慢慢拾起人生片段"),heading,t("照片不只是过去的画面，也是人与人之间，尚未说完的故事。"),`<button class="button secondary" data-action="write-story">${icon('stories')}${e(t("写下一段故事"))}</button>`)+peopleStrip+filterBar()+(grid||empty(t("每一段人生，都值得留下。"),t("连接照片目录，或换一个年份。没有日期的资料也会保留，不会替你猜测。"),`<button class="button primary" data-action="add-source">${e(t("连接资料文件夹"))}</button>`))+(state.timeline.items.length<state.timeline.total?`<button class="button secondary load-more" data-action="load-more">${e(t("继续沿时光往前"))}</button>`:'');
}
function peoplePage(){
  const g=state.graph;
  const nodes=(g?.nodes||[]).slice(0,24);const points=graphPositions(nodes.length);const position=new Map(nodes.map((n,i)=>[n.id,points[i]!]));
  const paths=(g?.edges||[]).filter(x=>position.has(x.a)&&position.has(x.b)).map(x=>{const a=position.get(x.a)!,b=position.get(x.b)!;return `<path d="M${a.x} ${a.y} Q480 290 ${b.x} ${b.y}" stroke-width="${Math.min(1+x.count*.3,3)}" class="evidence-edge"><title>${x.count} ${e(t("张同框影像 · 不是亲密程度"))}</title></path>`;}).join('');
  const relationPaths=(g?.relationships||[]).filter(x=>position.has(x.a)&&position.has(x.b)).map(x=>{const a=position.get(x.a)!,b=position.get(x.b)!;return `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="relationship-edge"><title>${e(t("你确认的关系：{name}",{name:x.label}))}</title></line>`;}).join('');
  const nodeMarkup=nodes.map((p,i)=>{const pos=points[i]!;return `<g class="graph-node" data-person="${e(p.id)}" tabindex="0" role="button" aria-label="${e(t("查看{name}",{name:personName(p)}))}" transform="translate(${pos.x},${pos.y})"><circle r="39" class="node-ring"/><circle r="32" class="node-disc"/>${p.face_id?`<clipPath id="clip${i}"><circle r="31"/></clipPath><image data-face="${e(p.face_id)}" x="-31" y="-31" width="62" height="62" clip-path="url(#clip${i})"/>`:`<text text-anchor="middle" y="8" class="node-initial">${e(p.name.slice(0,1)||'·')}</text>`}<text text-anchor="middle" y="61" class="node-label">${e(personName(p))}</text><text text-anchor="middle" y="80" class="node-count">${p.count} ${e(t("份影像"))}</text></g>`;}).join('');
  return pageHeader(t("一路同行的人"),`${e(t("有些人，"))}${locale()==='en'?' ':''}<span>${e(t("走过一段时光。"))}</span>`,`${e(yearLabel())} ${e(t("· 切换左侧年份，看看不同时期出现在照片中的人。"))}`,`<button class="button primary" data-action="analyze-faces">${icon('people')}${e(t("归类本地人像"))}</button>`)+
    (nodes.length?`<section class="graph-panel"><div class="graph-top"><span>${state.year==='all'?t("有人同行的人生"):e(t("{year} · 有人同行",{year:state.year}))}</span><span>${g!.nodes.length} ${e(t("位人物"))}</span></div><svg class="people-graph" viewBox="0 0 960 580" aria-label="${e(t("人物同框证据图"))}"><ellipse cx="480" cy="290" rx="370" ry="190" class="orbit"/><ellipse cx="480" cy="290" rx="230" ry="115" class="orbit"/>${paths}${relationPaths}<text x="480" y="280" text-anchor="middle" class="graph-center">${e(t("曾经同行"))}</text><text x="480" y="306" text-anchor="middle" class="graph-center-sub">${e(t("我们的共同记忆"))}</text>${nodeMarkup}</svg><div class="graph-legend"><span><i class="line-key"></i>${e(t("同框证据"))}</span><span><i class="line-key manual"></i>${e(t("你确认的关系"))}</span><small>${e(t("连线不代表关系亲疏 · 画面最多展示 24 位人物"))}</small></div></section><div class="people-cards">${(g?.nodes||[]).map(p=>`<button class="person-tile" data-person="${e(p.id)}">${avatar(p)}<div><strong>${e(personName(p))}</strong><small>${p.first_seen?e(p.first_seen.slice(0,4)):t("日期待确认")} — ${p.last_seen?e(p.last_seen.slice(0,4)):'…'} · ${p.count} ${e(t("份影像"))}</small></div>${icon('arrow')}</button>`).join('')}</div>`:empty(t("还没有归类的人像"),t("先连接照片目录，再同意本地人像分析。不会查询陌生人身份，也不会自动推断你们的真实关系。")));
}
function storiesPage(){return pageHeader(t("留在岁月里的文字"),`${e(t("不止影像，"))}${locale()==='en'?' ':''}<span>${e(t("还有你记得的。"))}</span>`,t("有些转折没有留下照片。这里也为它们留一页。"),`<button class="button primary" data-action="write-story">${icon('plus')}${e(t("写下故事"))}</button>`)+
  (state.stories.length?`<div class="story-list">${state.stories.map((s,i)=>`<button class="story-card" data-story="${e(s.id)}"><span class="chapter-number">${String(i+1).padStart(2,'0')}</span><div><small>${dateLabel(s.happened_at)}</small><h2>${e(s.title)}</h2><p>${e(s.body.slice(0,220))}${s.body.length>220?'…':''}</p><span class="story-footer">${s.asset_ids.length} ${e(t("份参考资料 ·"))} ${s.person_ids.length} ${e(t("位人物"))} ${icon('arrow')}</span></div></button>`).join('')}</div>`:empty(t("第一篇故事，从你想起的地方开始。"),t("不需要从出生写起，也不需要每天坚持。此刻想到的那一段，就已经足够。")));
}
function settingsPage(){const s=state.summary!;const model=state.status?.models;return pageHeader(t("以隐私为先"),`${e(t("一生的资料，"))}${locale()==='en'?' ':''}<span>${e(t("由你保管。"))}</span>`,t("Yorevia 不设账号、不托管私人资料。原始文件只读访问，所有分析在这台设备完成。"))+
 `<div class="settings-grid"><section class="settings-card">${languagePicker()}</section><section class="settings-card"><div class="section-title">${icon('folder')}${e(t("人生资料库"))}</div><p class="path">${e(s.path)}</p><p class="hint">${e(t("SQLite 保存记录；头像、预览和导出也保存在这个文件夹中。同步网盘前请关闭应用，不要在两台设备上同时打开同一个资料库。"))}</p><button class="button secondary" data-action="open-vault">${e(t("打开另一个资料库"))}</button></section>
 <section class="settings-card"><div class="section-title">${icon('download')}${e(t("带走你的故事"))}</div><p class="hint">${e(t("导出 ZIP 包含可阅读的 HTML 故事册、Markdown、JSON 索引及图片预览。不包含原始媒体、人脸特征向量或绝对来源路径。"))}</p><button class="button secondary" data-action="export">${e(t("导出我的档案"))}</button></section>
 <section class="settings-card wide"><div class="section-title">${icon('photo')}${e(t("已连接的资料"))}<button class="text-button" data-action="add-source">${e(t("本地文件夹 +"))}</button><button class="text-button" data-action="baidu-source">${e(t("百度网盘 +"))}</button></div>${s.sources.length?s.sources.map(src=>`<div class="source-row"><div><strong>${e(src.name)}</strong><p class="path">${e(src.root)}</p></div><button class="button secondary small" data-scan="${e(src.id)}">${e(t("增量扫描"))}</button><button class="text-button" data-verify="${e(src.id)}">${e(t("校验全部"))}</button></div>`).join(''):`<p class="hint">${e(t("尚未连接资料文件夹。支持本地目录，以及已完整下载到本机的网盘同步目录。"))}</p>`}</section>
 <section class="settings-card"><div class="section-title">${icon('people')}${e(t("本地人像模型"))}</div><span class="model-status ${model?.installed?'ready':''}">${model?.installed?t("模型已安装"):t("模型未安装")}</span><p class="hint">${e(t("YuNet + SFace · CPU 本地运行。自动归类只是建议，不保证跨年龄识别正确；你可以合并、拆分或命名。"))}</p>${!model?.installed?`<p class="hint">${e(t("源码开发版需显式运行："))}</p><code>python scripts/fetch_models.py</code><p class="hint">${e(t("此命令仅下载官方模型，不上传照片。桌面发布流水线会内置模型。"))}</p>`:''}<button class="button secondary" data-action="analyze-faces">${e(t("开始人像分析"))}</button></section>
 <section class="settings-card"><div class="section-title">${icon('lock')}${e(t("隐私边界"))}</div><p class="hint">${e(t("资料库尚未加密。能访问磁盘的人也可能看到故事与头像；建议启用系统磁盘加密。没有人脸或地点数据上传，也不加载远程字体与地图。"))}</p><button class="text-button danger" data-action="erase-biometrics">${e(t("删除本地人像特征与头像缓存"))}</button><p class="hint">${e(t("保留你写下的名字、关系和故事。不承诺物理擦除磁盘快照或历史备份。"))}</p></section>
 ${state.lastJob?`<section class="settings-card wide"><div class="section-title">${e(t("最近一次任务"))}</div><pre class="job-report">${e(JSON.stringify(state.lastJob.result||state.lastJob.error,null,2))}</pre></section>`:''}</div>`;}
async function loadImage(target:Element){
  if(target.classList.contains('loaded')||target.classList.contains('loading'))return;
  const face=target.getAttribute('data-face'),media=target.getAttribute('data-media');
  const remote=target.hasAttribute('data-remote-photo'),variant=target.getAttribute('data-variant')||'grid';
  const key=face?'face:'+face:'media:'+media;
  const status=variant==='detail'&&remote?target.parentElement?.querySelector<HTMLElement>('[data-photo-status]'):null;
  const retry=variant==='detail'&&remote?target.parentElement?.querySelector<HTMLButtonElement>('[data-action="retry-remote-photo"]'):null;
  target.classList.remove('failed');target.classList.add('loading');
  if(status)status.textContent=t('正在加载网盘预览…');
  if(retry)retry.hidden=true;
  try{
    let url=remote?undefined:imageCache.get(key);
    if(!url){const data=await rpc<{data:string|null}>('image',face?{face_id:face}:{asset_id:media,variant});
      if(!data.data)throw new Error(t('网盘暂未提供可用预览。'));
      url=data.data;
      if(!remote){if(imageCache.size>180)imageCache.delete(imageCache.keys().next().value!);imageCache.set(key,url);}
    }
    if(target.isConnected){target.setAttribute(target.tagName.toLowerCase()==='image'?'href':'src',url);target.classList.add('loaded');}
    if(status)status.textContent='';
  }catch(err){target.classList.add('failed');if(status)status.textContent=translateError(err);if(retry)retry.hidden=false;}
  finally{target.classList.remove('loading');}
}
async function hydrateImages(){
  observer?.disconnect();
  const queue:Element[]=[];let active=0;
  function pump(){while(active<3&&queue.length){const target=queue.shift()!;if(!target.isConnected)continue;active++;void loadImage(target).finally(()=>{active--;pump();});}}
  observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){observer!.unobserve(entry.target);queue.push(entry.target);}pump();},{rootMargin:'0px'});
  document.querySelectorAll('[data-media],[data-face]').forEach(el=>{if(!el.classList.contains('loaded'))observer!.observe(el);});
}
async function refresh(reset=true){
  const serial=++revision;state.loading=true;
  try{const status=await rpc<Status>('status');if(serial!==revision)return;state.status=status;state.summary=status.vault;
    if(!state.summary){render();return;}
    const params={year:state.year,query:state.query,person_id:state.person};
    const [people,timeline,graph,stories]=await Promise.all([
      rpc<Person[]>('people',{year:state.year}),
      state.view==='timeline'?rpc<Timeline>('timeline',{...params,limit:60,offset:reset?0:state.timeline.items.length}):Promise.resolve(state.timeline),
      state.view==='people'?rpc<Graph>('graph',{year:state.year}):Promise.resolve(state.graph),
      rpc<Story[]>('stories')]);
    if(serial!==revision)return;state.people=people;state.timeline=!reset&&state.view==='timeline'?{...timeline,items:[...state.timeline.items,...timeline.items]}:timeline;state.graph=graph;state.stories=stories;render();
  }catch(err){error(err);if(!state.summary)render();}finally{if(serial===revision)state.loading=false;}
}
function showModal(title:string,body:string,submit?: (data:FormData)=>Promise<void>){
  if(modal.open)modal.close();
  modal.innerHTML=`<button class="modal-close" data-action="close-modal" aria-label="${e(t("关闭"))}">${icon('close')}</button><h2 id="modal-title">${title}</h2>${body}`;
  modal.showModal();
  const form=modal.querySelector('form');
  if(form&&submit)form.onsubmit=async event=>{event.preventDefault();const button=form.querySelector<HTMLButtonElement>('[type=submit]');if(button)button.disabled=true;try{await submit(new FormData(form));modal.close();await refresh();}catch(err){error(err);}finally{if(button)button.disabled=false;}};
  void hydrateImages();
}
async function openVault(){const path=await chooseFolder(t("选择人生资料库的位置（新建时会使用其中的 YoreviaVault 子目录）"),"vault.open");if(!path)return;await rpc('vault.open',{path});state.year='all';state.person=null;imageCache.clear();await refresh();}
async function addLocalSource(){if(!state.summary){await openVault();if(!state.summary)return;}const path=await chooseFolder(t("选择原始照片、视频或文字资料所在的文件夹"),"source.add");if(!path)return;const source=await rpc<{id:string}>('source.add',{path});await beginJob('scan.start',{source_id:source.id});}
async function addSource(){
  if(!state.summary){await openVault();if(!state.summary)return;}
  showModal(t("连接你的记忆来源"), `<p>${e(t("本地资料只读索引；百度网盘会把勾选文件下载到你指定的本地目录。"))}</p><button class="button primary" data-action="local-source">${e(t("本地照片、视频或文字文件夹"))}</button><button class="button secondary" data-action="baidu-source">${e(t("百度网盘 · 开发者预览"))}</button><p class="hint">${e(t("百度网盘暂需开发者 Access Token，普通用户一键登录尚未上线。"))}</p>`);
}
async function beginJob(method:string,params:Record<string,unknown>){const response=await rpc<{job_id:string}>(method,params);let active=true;while(active){const job=await rpc<Job>('job.status',{job_id:response.job_id});state.job=job;const jobEl=document.querySelector<HTMLElement>('.job');if(!jobEl)render();else {jobEl.querySelector('strong')!.textContent=job.label;jobEl.querySelector('small')!.textContent=`${job.done} / ${job.total||'…'} ${t("· 本地整理 / 已选网盘文件下载")}`;const progress=jobEl.querySelector('progress')!;progress.max=job.total||1;progress.value=job.done;}if(job.status!=='running'){active=false;state.lastJob=job;state.job=null;if(job.status==='error')toast(job.error?translateError(job.error):t("任务失败"));else if(job.status==='cancelled')toast(t("已取消，已完成的索引保留。"));else{const errors=job.result?.errors as unknown[]|undefined;toast(errors?.length?t("处理完成，有 {count} 项需检查。请看「资料与隐私」中的任务报告。",{count:errors.length}):t("本地整理完成。你的记忆已留在资料库。"));}await refresh();}else await new Promise(r=>setTimeout(r,550));}}
function faceConsent(){showModal(t("让那些面孔，重新相连。"),`<p>${e(t("将分析已连接照片中的人像，生成本地头像和特征向量，并尝试将同一个人归类。"))}</p><div class="consent-note">${icon('lock')}${e(t("原始照片、人脸特征和人物名字都不上传。不会推断年龄、性别、民族或关系亲疏。自动归类可能出错，请按需要修正。"))}</div>${!state.status?.models.installed?`<p class="warning">${e(t("当前构建未安装模型。请到「资料与隐私」查看离线模型的准备方式。确认后仍会提示缺少模型，不会自动下载。"))}</p>`:''}<form><label class="check-field"><input name="consent" type="checkbox" required>${e(t("我同意在这台设备上分析这些照片中的人像。"))}</label><button class="button primary" type="submit">${e(t("开始本地分析"))}</button></form>`,async()=>{void beginJob('faces.start',{consent:true}).catch(error);});}
function writeStory(assetIds:string[]=[],story?:Story){
  showModal(story?t("续写这段故事"):t("你想从哪里说起？"),`<form class="story-form"><label>${e(t("故事标题"))}<input name="title" maxlength="200" required value="${e(story?.title||'')}" placeholder="${e(t("例如：第一次独自离开家的那天"))}"></label><label>${e(t("发生日期"))} <small>${e(t("不确定时留空"))}</small><input type="date" name="date" value="${e(story?.happened_at||'')}"></label><label>${e(t("当时的故事"))}<textarea name="body" rows="8" placeholder="${e(t("画面之外，还有哪些你记得的细节？"))}">${e(story?.body||'')}</textarea></label>${state.people.length?`<fieldset><legend>${e(t("与这段故事有关的人"))}</legend><div class="person-checks">${state.people.map(p=>`<label><input type="checkbox" name="person" value="${e(p.id)}" ${story?.person_ids?.includes(p.id)?'checked':''}>${e(personName(p))}</label>`).join('')}</div></fieldset>`:''}<p class="hint">${e(t("绑定 {count} 份资料 · 保存到你的人生资料库，不上传。",{count:(story?.asset_ids||assetIds).length}))}</p><button class="button primary" type="submit">${e(t("保存这段故事"))}</button></form>`,async data=>{await rpc('story.save',{title:data.get('title'),body:data.get('body'),happened_at:data.get('date')||null,asset_ids:story?.asset_ids||assetIds,person_ids:data.getAll('person'),...(story?{story_id:story.id}:{})});toast(t("故事已保存到你的资料库。"));});
}
async function showAsset(id:string){const a=await rpc<AssetDetail>('asset.detail',{asset_id:id});showModal(e(a.title),`<div class="asset-detail">${(a.thumb||a.remote_photo)?`<img class="detail-photo" ${a.remote_photo?'data-remote-photo="1" data-variant="detail"':''} data-media="${e(id)}" alt="${e(a.title)}">`:''}${a.remote_photo?`<p class="hint" data-photo-status role="status">${e(t('正在加载网盘预览…'))}</p><button class="button secondary small" data-action="retry-remote-photo" hidden>${e(t('重试网盘预览'))}</button>`:''}<div class="asset-meta"><span>${dateLabel(a.captured_at)} · ${dateEvidence(a.date_source)}</span>${a.remote_photo?'':`<button class="text-button" data-reveal="${e(id)}">${e(t("在文件夹中查看 ↗"))}</button>`}</div><div class="date-correction"><label>${e(t("修正日期"))}<input id="corrected-date" type="date" value="${e(a.captured_at?.slice(0,10)||'')}"></label><button class="button secondary small" data-date="${e(id)}">${e(t("保存日期"))}</button></div>${a.note_text?`<pre class="note-text">${e(a.note_text)}</pre>`:''}${a.faces.length?`<div class="detail-faces">${a.faces.map(f=>`<button class="face-chip" data-person="${e(f.person_id)}"><span class="avatar small-avatar"><img data-face="${e(f.id)}" alt=""></span>${e(f.name||t("未命名人物"))}</button>`).join('')}</div>`:''}<div class="detail-stories">${a.stories.map(s=>`<article><small>${dateLabel(s.happened_at)}</small><h3>${e(s.title)}</h3><p>${e(s.body)}</p><button class="text-button" data-story="${e(s.id)}">${e(t("继续写"))}</button></article>`).join('')}</div><button class="button primary" data-write-for="${e(id)}">${icon('stories')}${e(t("写下这段故事"))}</button><p class="hint">${e(t("参考资料："))}${a.locations.map(l=>e(l.name+'/'+l.relative_path)).join(' / ')||e(t("只读示例资料"))}</p></div>`);}
async function showPerson(id:string){const all=await rpc<Person[]>('people');const p=all.find(x=>x.id===id);if(!p)return;const faceList=await rpc<{items:{id:string;asset_id:string;captured_at:string|null;title:string}[];total:number}>('person.faces',{person_id:id});
  showModal(e(personName(p)),`<div class="person-header">${avatar(p,'large-avatar')}<div><p>${e(t("最早影像：{date}",{date:dateLabel(p.first_seen)}))}</p><p>${e(t("最近影像：{date}",{date:dateLabel(p.last_seen)}))}</p><small>${e(t("仅表示资料中的时间，不代表相识或关系结束。"))}</small></div></div><form class="person-form"><label>${e(t("你如何称呼这个人"))}<input name="name" maxlength="100" value="${e(p.name)}" placeholder="${e(t("名字或只有你知道的称呼"))}"></label><label>${e(t("关于这个人"))}<textarea name="description" rows="3" maxlength="5000">${e(p.description)}</textarea></label><button type="submit" class="button primary small">${e(t("保存名字与说明"))}</button></form><div class="person-tools"><button class="button secondary" data-filter-person="${e(id)}">${e(t("查看相关时光"))}</button><button class="button secondary" data-relate="${e(id)}">${e(t("记录真实关系"))}</button></div>${all.length>1?`<div class="merge-row"><label>${e(t("其实是同一个人？"))}<select id="merge-target"><option value="">${e(t("选择另一个分组"))}</option>${all.filter(x=>x.id!==id).map(x=>`<option value="${e(x.id)}">${e(personName(x))} · ${x.count} ${e(t("张"))}</option>`).join('')}</select></label><button class="button secondary small" data-merge="${e(id)}">${e(t("合并到此人物"))}</button></div>`:''}<h3 class="face-heading">${e(t("归类到这里的人像"))} <small>${faceList.total} ${e(t("个 · 显示前 100 个"))}</small></h3><div class="face-review">${faceList.items.map(f=>`<div><button data-asset="${e(f.asset_id)}"><img data-face="${e(f.id)}" alt="${e(f.title)}"><small>${e(f.captured_at?.slice(0,4)||t("未知年份"))}</small></button><button class="text-button" data-split="${e(f.id)}">${e(t("不是此人 · 拆分"))}</button></div>`).join('')}</div>`,async data=>{await rpc('person.rename',{person_id:id,name:data.get('name'),description:data.get('description')});});
}
async function relate(id:string){const people=await rpc<Person[]>('people');showModal(t("关系，由你来定义。"),`<form class="story-form"><p class="hint">${e(t("这是你手动记录的关系。系统不会把同框自动当成朋友、同事或家人。"))}</p><label>${e(t("另一个人"))}<select name="b" required><option value="">${e(t("选择人物"))}</option>${people.filter(p=>p.id!==id).map(p=>`<option value="${e(p.id)}">${e(personName(p))}</option>`).join('')}</select></label><label>${e(t("关系名称"))}<input name="label" required maxlength="100" placeholder="${e(t("例如：同学 / 同事 / 朋友"))}"></label><div class="two-col"><label>${e(t("开始日期（可空）"))}<input type="date" name="start"></label><label>${e(t("结束日期（可空）"))}<input type="date" name="end"></label></div><button type="submit" class="button primary">${e(t("保存关系"))}</button></form>`,async data=>{await rpc('relationship.add',{a:id,b:data.get('b'),label:data.get('label'),start_date:data.get('start')||null,end_date:data.get('end')||null});});}

async function handleClick(target:HTMLElement){
  const d=target.dataset;
  if(d.view){state.view=d.view as View;state.query='';await refresh();return;}
  if(d.year){state.year=d.year;state.person=null;await refresh();return;}
  if(d.asset){await showAsset(d.asset);return;}
  if(d.person){await showPerson(d.person);return;}
  if(d.story){const story=state.stories.find(s=>s.id===d.story);if(story)writeStory([],story);return;}
  if(d.scan||d.verify){await beginJob('scan.start',{source_id:d.scan||d.verify,force:Boolean(d.verify)});return;}
  if(d.reveal){await revealAsset(d.reveal);return;}
  if(d.date){const date=modal.querySelector<HTMLInputElement>('#corrected-date')?.value;await rpc('asset.date',{asset_id:d.date,date:date||null});await refresh();await showAsset(d.date);return;}
  if(d.writeFor){writeStory([d.writeFor]);return;}
  if(d.filterPerson){state.person=d.filterPerson;state.view='timeline';modal.close();await refresh();return;}
  if(d.relate){await relate(d.relate);return;}
  if(d.merge){const merge=modal.querySelector<HTMLSelectElement>('#merge-target')?.value;if(!merge){toast(t("请先选择要合并的分组。"));return;}if(!window.confirm(t("将两个分组合并到此人物，并保留关联故事。确认是同一个人吗？")))return;await rpc('person.merge',{keep:d.merge,merge});imageCache.clear();await refresh();await showPerson(d.merge);return;}
  if(d.split){const name=window.prompt(t("将这个人像拆分为新人物。可填写名字，也可留空。"));if(name===null)return;const result=await rpc<{person_id:string}>('face.split',{face_id:d.split,name});await refresh();await showPerson(result.person_id);return;}
  switch(d.action){
    case 'home':state.view='timeline';await refresh();break;
    case 'open-vault':await openVault();break;
    case 'add-source':await addSource();break;
    case 'local-source':modal.close();await addLocalSource();break;
    case 'retry-remote-photo':{const photo=modal.querySelector('[data-variant=detail]');if(photo)await loadImage(photo);break;}
    case 'baidu-source':await showBaidu(modal,beginJob,error);break;
    case 'analyze-faces':if(!state.summary){await openVault();if(!state.summary)return;}faceConsent();break;
    case 'write-story':writeStory();break;
    case 'clear-person':state.person=null;await refresh();break;
    case 'load-more':await refresh(false);break;
    case 'close-modal':modal.close();break;
    case 'cancel-job':await rpc('job.cancel');break;
    case 'exit-demo':location.href=location.pathname;break;
    case 'export':{const result=await rpc<{path:string;size:number}>('export',{locale:locale()});showModal(t("你的故事，已经可以带走。"),`<p>${e(t("导出包已写入人生资料库的 exports 文件夹。"))}</p><p class="path">${e(result.path)}</p><p>${e(t("解压后打开 index.html，即可离线阅读故事册；也可以通过浏览器打印为 PDF。"))}</p><p class="hint">${e(t("约 {size} MB。包含私人文字和预览图，请谨慎分享。",{size:new Intl.NumberFormat(locale(),{minimumFractionDigits:1,maximumFractionDigits:1}).format(result.size/1024/1024)}))}</p>`);break;}
    case 'erase-biometrics':{if(!window.confirm(t("删除所有本地人脸特征与头像缓存？你写下的名字、关系和故事仍然保留。")))return;await rpc('biometrics.erase',{confirm:'ERASE'});imageCache.clear();await refresh();toast(t("本地特征与头像缓存已删除。历史备份和磁盘快照不在此次删除范围内。"));break;}
  }
}
document.addEventListener('click',event=>{const target=(event.target as Element).closest<HTMLElement>('[data-action],[data-view],[data-year],[data-asset],[data-person],[data-story],[data-scan],[data-verify],[data-reveal],[data-date],[data-write-for],[data-filter-person],[data-relate],[data-merge],[data-split]');if(target)void handleClick(target).catch(error);});
document.addEventListener('input',event=>{if((event.target as HTMLInputElement).id==='search'){const value=(event.target as HTMLInputElement).value;clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.query=value;void refresh().then(()=>{const input=document.querySelector<HTMLInputElement>('#search');input?.focus();input?.setSelectionRange(value.length,value.length);});},350);}});
document.addEventListener('keydown',event=>{const t=event.target as HTMLElement;if((event.key==='Enter'||event.key===' ')&&t.matches('.graph-node')){event.preventDefault();void showPerson(t.dataset.person!).catch(error);}if(event.key==='/'&&!['INPUT','TEXTAREA'].includes(t.tagName)){event.preventDefault();document.querySelector<HTMLInputElement>('#search')?.focus();}});
modal.addEventListener('click',event=>{if(event.target===modal){const r=modal.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)modal.close();}});
document.addEventListener('change',event=>{
  const picker=event.target;
  if(!(picker instanceof HTMLSelectElement)||picker.id!=='app-language')return;
  if(modal.open){picker.value=preference();return;}
  const value=picker.value;
  if(value==='system'||value==='zh-CN'||value==='en')setPreference(value);
});
subscribe(()=>{
  // The modal is outside the app shell. Keep open forms and authorization sessions intact.
  const search=document.querySelector<HTMLInputElement>('#search');
  const searching=search===document.activeElement;
  if(search)state.query=search.value;
  const switching=document.activeElement?.id==='app-language';
  render();
  if(switching)document.querySelector<HTMLSelectElement>('#app-language')?.focus();
  if(searching){
    const next=document.querySelector<HTMLInputElement>('#search');
    next?.focus();
    next?.setSelectionRange(search?.selectionStart??0,search?.selectionEnd??0);
  }
});
render();void refresh();
