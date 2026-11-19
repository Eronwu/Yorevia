import {t,locale} from './i18n.js';
import type { Asset, Person } from './types.js';
export function escapeHTML(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]!));
}
export function personName(person: Pick<Person,'id'|'name'>): string {
  return person.name || t('未命名 {id}',{id:person.id.slice(0,4)});
}
export function dateLabel(value: string|null): string {
  if(!value) return t('时间待确认');
  const [y,m,d] = value.slice(0,10).split('-');
  return locale()==='en'?`${y}-${m}-${d}`:`${y} 年 ${Number(m)} 月 ${Number(d)} 日`;
}
export function dateEvidence(source:string):string {
  return t(({exif:'拍摄信息',filename:'文件名推测',manual:'你标记的时间',unknown:'时间待确认'} as Record<string,string>)[source] || '时间待确认');
}
export function groupAssets(items:Asset[]): [string,Asset[]][] {
  const groups=new Map<string,Asset[]>();
  for(const item of items){
    const key=item.captured_at ? item.captured_at.slice(0,7) : 'unknown';
    if(!groups.has(key)) groups.set(key,[]);
    groups.get(key)!.push(item);
  }
  return [...groups];
}
export function graphPositions(count:number,width=960,height=580):{x:number;y:number}[]{
  if(count<=0)return [];
  if(count===1)return [{x:width/2,y:height/2}];
  return Array.from({length:count},(_,i)=>{
    const angle=(Math.PI*2*i/count)-Math.PI/2;
    const radius=count>12 && i%2===1 ? .60 : .85;
    return {x:width/2+Math.cos(angle)*width*.43*radius,y:height/2+Math.sin(angle)*height*.38*radius};
  });
}
