import {cp,mkdir} from 'node:fs/promises';
await mkdir('dist',{recursive:true});
await cp('public','dist',{recursive:true});
console.log('Yorevia frontend built locally; no CDN or runtime JavaScript dependencies.');
