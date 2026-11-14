import type { Asset, Graph, Person, Story, Summary, Timeline } from './types.js';
const assets: Asset[] = [
 ['demo1','2023-10-14','山间的午后','photo'],['demo2','2023-10-14','湖畔，风慢了下来','photo'],
 ['demo3','2023-06-03','久别后的见面','photo'],['demo4','2020-09-18','从那一扇窗看出去','photo'],
 ['demo5','2020-09-18','秋天的来信','note'],['demo6','2016-07-22','海边，我们没有赶时间','photo'],
 ['demo7','2016-07-21','旅途上的一小段','video'],['demo8','2012-06-16','散场之前，再走一段','photo'],
 ['demo9','2008-04-05','小时候的那条路','photo'],['demo10',null,'一张还没有日期的照片','photo']
].map(([id,date,title,kind])=>({id:id!,captured_at:date ?? null,title:title!,kind:kind as Asset['kind'],date_source:date?'exif':'unknown',thumb:id,available:1,people_count:2,story_count:id==='demo3'?1:0}));
const people: Person[]=['林','陈','周','许','何','苏'].map((name,i)=>({id:`person${i}`,name:`${name} · 示例`,description:'虚构演示人物，不代表识别结果',count:9-i,first_seen:'2012-06-16',last_seen:'2023-10-14',face_id:null}));
const stories: Story[]=[{id:'story1',title:'有些见面，不必从头说起',body:'多年之后，我们又坐在了同一张桌旁。\n\n这是虚构的演示内容，用来展示你的故事将如何被保存；没有使用任何真实人物或私人资料。',happened_at:'2023-06-03',asset_ids:['demo3'],person_ids:['person0','person1']}];
export const demoSummary: Summary={path:'示例资料 · 不读取本地文件',assets:assets.length,people:people.length,stories:stories.length,years:['2023','2020','2016','2012','2008'],unknown_dates:1,sources:[]};
export function landscape(id:string):string{
  const i=Number(id.replace(/\D/g,''))||1;
  const palettes=[['#d9d3ba','#8c9c89','#485e54','#c6a07f'],['#d5dce0','#8fa5aa','#4e747b','#d7b596'],['#e4d8bf','#9eaa84','#64765a','#bc866a']];
  const c=palettes[i%palettes.length]!;
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="840" height="620" viewBox="0 0 840 620"><defs><filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".6" numOctaves="3" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="linear" slope=".10"/></feComponentTransfer></filter><linearGradient id="sky" x2="0" y2="1"><stop stop-color="${c[0]}"/><stop offset="1" stop-color="#ebe4d3"/></linearGradient></defs><rect width="840" height="620" fill="url(#sky)"/><circle cx="${600-i*25}" cy="120" r="45" fill="#f1e9cf"/><path d="M0 350 L130 190 220 280 380 120 560 320 710 190 840 300V620H0" fill="${c[1]}"/><path d="M0 470 Q150 280 300 400T560 390T840 370V620H0" fill="${c[2]}"/><path d="M0 490Q220 410 420 490T840 460V620H0" fill="${c[0]}"/>${i%2?`<path d="M440 620Q350 540 480 485" fill="none" stroke="${c[3]}" stroke-width="42"/><rect x="170" y="330" width="100" height="130" fill="${c[3]}"/><path d="M155 332L218 275L283 332" fill="#555e50"/><rect x="205" y="380" width="28" height="80" fill="#53534c"/>`:`<path d="M0 520Q200 470 400 530T840 500" stroke="#f0ebdc" stroke-width="3" fill="none"/><path d="M380 515h90l-20 18h-55z" fill="${c[2]}"/><path d="M425 511V455l45 56z" fill="#ede5ce"/>`}<rect width="840" height="620" filter="url(#grain)" opacity=".55"/></svg>`;
  return 'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg);
}
export async function demoCall<T>(method:string,p:Record<string,unknown>):Promise<T>{
  let result: unknown;
  const filtered=assets.filter(a=>!p.year||p.year==='all'||(p.year==='unknown'?!a.captured_at:a.captured_at?.startsWith(String(p.year))))
   .filter(a=>!p.query||a.title.includes(String(p.query)));
  if(method==='status')result={version:'0.1.0-alpha.1',vault:demoSummary,models:{installed:false,missing:[],engine:'演示模式'},telemetry:false};
  else if(method==='summary')result=demoSummary;
  else if(method==='timeline')result={items:filtered,total:filtered.length,offset:0,limit:60} satisfies Timeline;
  else if(method==='people')result=people.slice(0,p.year==='2008'?2:people.length);
  else if(method==='graph')result={nodes:people,edges:[{a:'person0',b:'person1',count:4},{a:'person1',b:'person2',count:2},{a:'person0',b:'person3',count:2},{a:'person2',b:'person4',count:1},{a:'person4',b:'person5',count:1}],relationships:[]} satisfies Graph;
  else if(method==='stories')result=stories;
  else if(method==='image')result={data:landscape(String(p.asset_id))};
  else if(method==='asset.detail')result={...assets.find(a=>a.id===p.asset_id),note_text:'这是演示资料。',faces:[],stories:p.asset_id==='demo3'?stories:[],locations:[]};
  else if(method==='person.faces')result={items:[],total:0};
  else throw new Error('这是只读示例。请打开桌面应用，连接你自己的资料库。');
  return result as T;
}
