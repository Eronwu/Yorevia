import http from 'node:http';
import {pathToFileURL} from 'node:url';
import {Broker, BrokerError, baiduProvider} from './broker.mjs';
export function createServer(broker) {
  const server=http.createServer(async(req,res)=>{
    const send=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store','Pragma':'no-cache','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'});res.end(JSON.stringify(data));};
    // This is a native-client API, never a browser/CORS endpoint.
    if(req.method!=='POST'||req.headers.origin||req.headers['content-type']!=='application/json')return send(400,{error:'invalid_request'});
    const action={'/v1/device/start':'start','/v1/device/poll':'poll','/v1/device/cancel':'cancel'}[req.url];
    if(!action)return send(404,{error:'not_found'});
    try {
      let raw='';let size=0;
      for await(const chunk of req){size+=chunk.length;if(size>4096){send(413,{error:'too_large'});req.destroy();return;}raw+=chunk.toString('utf8');}
      let body;try{body=JSON.parse(raw);}catch{throw new BrokerError('invalid_request');}
      if(!body||typeof body!=='object'||Array.isArray(body))throw new BrokerError('invalid_request');
      send(200,await broker[action](body));
    }catch(e){send(e instanceof BrokerError?e.status:502,{error:e instanceof BrokerError?e.message:'provider_error',...(e instanceof BrokerError&&e.interval?{interval:e.interval}:{})});}
  });
  const cleanup=setInterval(()=>broker.sweep(),30000);cleanup.unref();server.once('close',()=>clearInterval(cleanup));
  server.requestTimeout=20000;server.headersTimeout=10000;server.maxConnections=100;return server;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  if(!process.env.BAIDU_APP_KEY||!process.env.BAIDU_SECRET_KEY){console.error('Set server-only BAIDU_APP_KEY and BAIDU_SECRET_KEY.');process.exit(1);}
  const port=Number(process.env.PORT||8787);if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Invalid port');
  const server=createServer(new Broker(baiduProvider({appKey:process.env.BAIDU_APP_KEY,secretKey:process.env.BAIDU_SECRET_KEY})));
  // Deliberately no public HTTP binding option: put an HTTPS reverse proxy in front.
  server.listen(port,'127.0.0.1',()=>console.log('OAuth prototype listening on loopback. TLS proxy required.'));
}
