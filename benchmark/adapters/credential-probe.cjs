const fs=require('node:fs');
const env=process.env;
const log=env.REN_CREDENTIAL_LOG;
const watched=/^(DECK(RENDER|FLOW|HTML)_(API_KEY|TOKEN)|DECKOPS_TOKEN)$/;
if(log)fs.appendFileSync(log,JSON.stringify({event:'probe-ready',pid:process.pid})+'\n');
if(log) process.env=new Proxy(env,{get(target,key){
 if(typeof key==='string'&&watched.test(key))fs.appendFileSync(log,JSON.stringify({event:'env-read',key,at:new Date().toISOString()})+'\n');
 return Reflect.get(target,key);
}});
