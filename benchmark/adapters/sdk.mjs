import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const spec=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const events=[];
const record=(kind,message)=>{ const e={kind,message,at:new Date().toISOString()};events.push(e);process.stderr.write(JSON.stringify(e)+'\n'); };
try {
 const sdk=await import(pathToFileURL(spec.module).href);
 const result=await sdk.render({...spec.options,onWarning:m=>record('warning',m),onProgress:e=>record(e.phase,e.message)});
 process.stdout.write(JSON.stringify(result)+'\n');
} catch(error) {
 // Preserve the target's error representation; do not invent a machine code.
 const data=typeof error.toJSON==='function'?error.toJSON():Object.fromEntries(Object.getOwnPropertyNames(error).filter(k=>k!=='stack').map(k=>[k,error[k]]));
 process.stdout.write(JSON.stringify({ok:false,error:data})+'\n');process.exitCode=1;
}
