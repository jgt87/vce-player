import { Client } from 'file:///C:/Users/gijst/AppData/Local/npm-cache/_npx/ad9a3fdbcad992c6/node_modules/@modelcontextprotocol/client/dist/index.mjs';
import { StdioClientTransport } from 'file:///C:/Users/gijst/AppData/Local/npm-cache/_npx/ad9a3fdbcad992c6/node_modules/@modelcontextprotocol/client/dist/stdio.mjs';
import { mkdir, readFile, writeFile, readdir } from 'node:fs/promises';
const root = 'C:/Files/Apps/VCE Player';
const analysisDir = root + '/' + (process.argv[2] ?? 'analysis');
await mkdir(analysisDir+'/requests', {recursive:true});
const client = new Client({name:'vce-investigation',version:'1.0.0'});
await client.connect(new StdioClientTransport({command:process.execPath,args:['C:/Users/gijst/AppData/Local/npm-cache/_npx/ad9a3fdbcad992c6/node_modules/rea-agents/scripts/rea.mjs','mcp'],env:{...process.env,GHIDRA_INSTALL_DIR:root+'/.tools/ghidra_12.1.4_PUBLIC',JAVA_HOME:root+'/.tools/jdk-21.0.12.1+1'},stderr:'inherit'}));
console.log('Connected');
const done = new Set();
try {
  for (;;) {
    for(const file of (await readdir(analysisDir+'/requests')).filter(x=>x.endsWith('.json')).sort()) {
      if(done.has(file)) continue;
      const request=JSON.parse(await readFile(analysisDir+'/requests/'+file,'utf8'));
      console.log('Calling '+request.name);
      const result=await client.callTool(request,{timeout:1800000});
      await writeFile(analysisDir+'/'+file,JSON.stringify(result,null,2));
      done.add(file);
      console.log('Saved '+file+(result.isError?' ERROR':''));
      if(request.name==='close_binary') { await client.close(); process.exit(0); }
    }
    await new Promise(r=>setTimeout(r,1000));
  }
} finally { await client.close(); }
