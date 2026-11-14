import http from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
const base=path.resolve('dist');
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'};
http.createServer(async(req,res)=>{try{
  const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  const file=path.resolve(base,'.'+(name==='/'?'/index.html':name));
  if(!file.startsWith(base+path.sep)){res.writeHead(403);res.end();return;}
  const data=await readFile(file);res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});res.end(data);
}catch{res.writeHead(404);res.end();}}).listen(4173,'127.0.0.1',()=>console.log('Static desktop development UI: http://127.0.0.1:4173'));
