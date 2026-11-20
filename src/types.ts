export interface Source { id: string; name: string; root: string }
export interface Summary { path: string; assets: number; people: number; stories: number; years: string[]; unknown_dates: number; sources: Source[] }
export interface Asset { id: string; kind: 'photo'|'video'|'note'; title: string; captured_at: string|null; date_source: string; width?: number; height?: number; thumb?: string|null; remote_photo?: boolean; available: number; people_count: number; story_count: number }
export interface Person { id: string; name: string; description: string; count: number; first_seen: string|null; last_seen: string|null; face_id: string|null }
export interface Story { id: string; title: string; body: string; happened_at: string|null; asset_ids: string[]; person_ids: string[] }
export interface Face { id: string; person_id: string; name: string; confidence: number; locked: number }
export interface AssetDetail extends Asset { note_text: string; faces: Face[]; stories: Story[]; locations: {name:string;relative_path:string;available:number}[] }
export interface Graph { nodes: Person[]; edges: {a:string;b:string;count:number}[]; relationships: {id:string;a:string;b:string;label:string;start_date:string|null;end_date:string|null}[] }
export interface Timeline { items: Asset[]; total: number; offset: number; limit: number }
export interface Job { id:string;status:'running'|'done'|'cancelled'|'error';done:number;total:number;label:string;result:Record<string,unknown>|null;error:string|null }
export interface Status { version:string;vault:Summary|null;models:{installed:boolean;missing:string[];engine:string};telemetry:boolean;local_web_startup_error?:boolean }
export interface Invoke { <T>(command:string,args?:Record<string,unknown>):Promise<T> }
declare global { interface Window { __TAURI__?:{core:{invoke:Invoke}}; __YOREVIA_TOKEN__?:string; __YOREVIA_LOCAL_WEB__?:boolean } }
