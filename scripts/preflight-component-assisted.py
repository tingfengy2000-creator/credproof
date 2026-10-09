"""Current production serialization/budget on saved states; no model or execution."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from credproof_safety.agent import _bounded_initial_context, _model_work_feedback
from credproof_safety.project import _redact_execution
from credproof_safety.config import load_config
from agent_pilot.bounded_patch import build_payload, generation_state, OUTPUT_TOKENS
from agent_pilot.model_client import estimate_input_budget

dest=Path(sys.argv[1]);dest.mkdir(parents=True,exist_ok=False)
config=load_config(ROOT/'examples/material_assistant/credproof.toml')
base=ROOT/'docs/reusable-tool-safety/acceptance'
original=json.loads((base/'20261009-component-assisted/component-controls-final/unchanged-original-report.json').read_text(encoding='utf8'))
context=_bounded_initial_context(original,config)
tests={'tests/test_business.py':(config.project_root/'tests/test_business.py').read_text(encoding='utf8')}
states=[('original', config.project_root/'tool.py', original, 0)]
old=base/'20261009-bounded-patch/public-evidence'
for number in (1,2):
    report=_redact_execution(json.loads((old/f'verification-{number:02d}.json').read_text(encoding='utf8')),'unused')
    states.append((f'saved-failed-candidate-{number}',old/f'candidate-{number:02d}.py',report,number))
rows=[]
for name,source,report,n in states:
    code=source.read_text(encoding='utf8')
    feedback=_model_work_feedback(report,config)
    host={'current_candidate':n or None,'current_candidate_sha256':hashlib.sha256(code.encode()).hexdigest(),
          'last_verified_candidate':n or None,'last_verification_verdict':'FAIL' if n else None,
          'remaining_candidates':3-n,'remaining_verifications':3-n}
    for correction in ([None,'truncated_or_nonstop_response'] if n==2 else [None]):
        label=name+('-format-correction' if correction else '')
        payload=build_payload(context,code,tests,feedback,{'strategy':'bounded_patch','executor':generation_state(host),
             'remaining_generations':3-n,'remaining_requests':4-n,'remaining_format_corrections':1}, correction=correction)
        budget=estimate_input_budget(payload,OUTPUT_TOKENS)
        (dest/(label+'-payload.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        checks={'source':code in payload['messages'][1]['content'],
                'tests':all(x in payload['messages'][1]['content'] for x in tests.values()),
                'contract':context['runtime_contract']['policy_sha256'] in payload['messages'][1]['content'],
                'api': 'get_json' in payload['messages'][1]['content'],
                'real_fail':feedback['verdict']=='FAIL','no_tools':'tools' not in payload,
                'budget':budget['within_context_budget'] and budget['within_wire_limit']}
        rows.append({'state':label,'kind':'NO_MODEL_SAVED_STATE_PROTOCOL','source':source.relative_to(ROOT).as_posix(),
                     'source_bytes':len(code.encode()),'checks':checks,'budget':budget})
summary={'pass':all(all(x['checks'].values()) for x in rows),'model_calls':0,'candidate_execution':False,
         'rows':rows,'scope':'original and two saved failure sources, with component work package and one format correction; not arbitrary length guarantee'}
(dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps(summary,indent=2))
raise SystemExit(0 if summary['pass'] else 1)
