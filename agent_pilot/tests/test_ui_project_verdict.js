const fs = require('fs');
const source = fs.readFileSync('agent_pilot/ui/app.js','utf8');
const body = source.slice(source.indexOf('function renderProjectModes()'), source.indexOf('function renderScope()'));
const els = new Map();
const $ = id => { if (!els.has(id)) els.set(id,{innerHTML:'',textContent:'',hidden:false,disabled:false,value:''}); return els.get(id); };
const state = { projectModes:{modes:[],projects:[]}, project:{label:'fixture',patch_origin:'demo',object_sha256:'abcdef1234567890',last_report:null,last_report_applicable:false,config:{}}, busy:false };
const array=v=>Array.isArray(v)?v:[];
const text=v=>typeof v==='string'?v:v==null?'':JSON.stringify(v,null,2);
const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const displayTime=v=>v||'未提供时间';
const verdictNames={PASS:'通过',FAIL:'未通过',UNKNOWN:'未知'};
const tone=v=>({PASS:'pass',FAIL:'fail',UNKNOWN:'unknown'}[v]||'neutral');
const badge=(label,style='neutral')=>`<span class="badge ${style}">${escape(label)}</span>`;
function run(report, applicable=true){ state.project.last_report=report; state.project.last_report_applicable=applicable; eval(body); renderProjectModes(); return {overall: $('project-current-verdict').innerHTML, cards:$('project-current-checks').innerHTML}; }
const checks={pytest:true,required_pytest_tests:true,entry_completed:true,required_service_credential:false,no_credential_output:true,no_forbidden_file_read:true,no_out_of_scope_file_read:true,required_allowed_file_read:true,allowed_service_receipt:true,allowed_service_path:true,no_forbidden_service_receipt:true,no_unauthorized_connection:true,isolation_receipt:true};
let out=run({verdict:'FAIL',checked_at_utc:'2026-10-06T00:00:00Z',required_checks:checks});
if(!out.overall.includes('未通过')||!out.cards.includes('required_service_credential')||out.cards.includes('业务与认证 <span class="badge pass"')) throw new Error('FAIL verdict or auth failure not visible');
const all=Object.fromEntries(Object.keys(checks).map(k=>[k,true])); out=run({verdict:'PASS',checked_at_utc:'2026-10-06T00:00:00Z',required_checks:all});
if(!out.overall.includes('通过')||!out.cards.includes('业务与认证')) throw new Error('PASS or service credential group missing');
out=run({verdict:'PASS',checked_at_utc:'2026-10-06T00:00:00Z',required_checks:all},false);
if(!out.overall.includes('未知')||out.overall.includes('通过')) throw new Error('stale report displayed as current PASS');
const missing={...all}; delete missing.required_service_credential; out=run({verdict:'PASS',checked_at_utc:'2026-10-06T00:00:00Z',required_checks:missing},true);
if(!out.cards.includes('未知 · UNKNOWN')) throw new Error('missing required check not UNKNOWN');
console.log('ui-project-verdict-regression: PASS (FAIL/PASS/stale/missing cases)');

