// Read-only snapshots of the two disposable review states, after CUA button tests.
import{createRequire}from'node:module';import{writeFileSync,mkdirSync}from'node:fs';import{join}from'node:path';
const{chromium}=createRequire(join(process.cwd(),'noop.js'))('playwright');
const out='manual-state-captures';mkdirSync(out,{recursive:true});const b=await chromium.launch({channel:'msedge'});const p=await b.newPage({viewport:{width:1440,height:1000}});const results={writes:[],states:[]};
p.on('request',r=>{if(r.method()!=='GET')results.writes.push(r.method()+' '+r.url());});
await p.goto('http://127.0.0.1:8768/#human-review',{waitUntil:'networkidle'});await p.locator('#review-states').waitFor({state:'visible'});
for(const id of ['939e25f42bb142f39567c5cb644ebc6d','6f5ae3791ad343b7ba4ebdf9e52b9d8a']){
 await p.locator('#review-saved').selectOption(id);await p.getByRole('button',{name:'打开',exact:true}).click();
 await p.waitForFunction(x=>document.querySelector('#review-code')?.dataset.identity?.startsWith(x),id);
 const state=await p.locator('#review-states').innerText();results.states.push({id,state,approve_enabled:await p.locator('#review-approve').isEnabled(),adopted_export_enabled:await p.locator('#review-adopted').isEnabled()});
 await p.screenshot({path:join(out,id+'.png'),fullPage:true});
}
writeFileSync(join(out,'summary.json'),JSON.stringify(results,null,2)+'\n');await b.close();console.log(JSON.stringify(results));
