import {createRequire} from 'node:module';
import {join, resolve} from 'node:path';
import {mkdirSync, writeFileSync} from 'node:fs';
const {chromium}=createRequire(join(process.cwd(),'noop.js'))('playwright');
const base=process.argv[2],out=resolve(process.argv[3]);mkdirSync(out,{recursive:true});
const browser=await chromium.launch({channel:'msedge'});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const result={kind:'READ_ONLY_COMPARE_UI',base,browser:browser.version(),model_calls:0,candidate_executions:0,errors:[],writes:[],batches:{}};
page.on('pageerror',e=>result.errors.push(e.message));
page.on('request',r=>{if(r.method()!=='GET')result.writes.push(r.method()+' '+r.url())});
try{
 await page.goto(base+'/#compare',{waitUntil:'networkidle'});
 await page.waitForSelector('#compare-numbers tbody tr');
 const response=await page.request.get(base+'/api/compare');
 const data=await response.json();
 if(response.status()!==200)throw Error('compare HTTP '+response.status());
 for(const b of [{id:'all',denominators:data.comparison.denominators,methods:data.comparison.methods},...data.comparison.batches]){
  await page.locator(`[data-compare-batch="${b.id}"]`).click();
  const rows=await page.locator('#compare-numbers tbody tr').allTextContents();
  for(let i=0;i<b.methods.length;i++){
   const m=b.methods[i],cells=await page.locator('#compare-numbers tbody tr').nth(i).locator('td').allTextContents();
   if(cells[1].replace(/\s/g,'')!==`${m.accepted_unsafe}/${m.coverage.unsafe}`)throw Error('unsafe count '+b.id+' '+m.id);
   if(!cells[2].replace(/\s/g,'').startsWith(`${m.rejected_good}/${m.coverage.good}`))throw Error('good count '+b.id+' '+m.id);
   if(cells[3].replace(/\s/g,'')!==`${m.invalid}覆盖${m.coverage.rows}份`)throw Error('invalid count '+b.id+' '+m.id);
  }
  result.batches[b.id]={rows,denominator:await page.locator('#compare-denominator').textContent()};
 }
 const onboarding=await page.locator('#onboarding-results tbody tr').allTextContents();
 for(const [i,expected] of ['116/117','117/117','117/117','117/117'].entries())if(!onboarding[i].includes(expected))throw Error('onboarding count '+i);
 result.onboarding=onboarding;
 await page.locator('[data-compare-batch="all"]').click();
 await page.screenshot({path:join(out,'compare-desktop.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
 result.mobile_overflow_px=overflow;if(overflow>0)throw Error('mobile overflow '+overflow);
 await page.screenshot({path:join(out,'compare-mobile.png'),fullPage:true});
}catch(e){result.errors.push(String(e))}finally{await browser.close()}
result.pass=!result.errors.length&&!result.writes.length;
writeFileSync(join(out,'summary.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({pass:result.pass,batches:Object.keys(result.batches),errors:result.errors,writes:result.writes}));
process.exit(result.pass?0:1);
