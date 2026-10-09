"""Pure construction of the production structured request from saved evidence."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent_pilot.bounded_patch import build_payload, generation_state, OUTPUT_TOKENS
from agent_pilot.model_client import estimate_input_budget
from credproof_safety.agent import _bounded_initial_context, _model_work_feedback
from credproof_safety.config import load_config

dest = Path(sys.argv[1]); dest.mkdir(parents=True, exist_ok=False)
base = ROOT/'docs/reusable-tool-safety/acceptance/20261007-return-redirect'
config = load_config(ROOT/'examples/material_assistant/credproof.toml')
initial = json.loads((base/'context-budget-pilot-v8/public-evidence/initial-report.json').read_text(encoding='utf8'))
context = _bounded_initial_context(initial, config)
tests = {p: (config.project_root/p).read_text(encoding='utf8')
         for p in context['project']['readable_paths'] if p != context['project']['entry_path']}
stages = [
    ('original', config.project_root/'tool.py', base/'context-budget-pilot-v8/public-evidence/initial-report.json', 0),
    ('v8_failed_candidate', base/'context-budget-pilot-v8/public-evidence/candidate-01.py', base/'context-budget-pilot-v8/public-evidence/verification-01.json', 1),
    ('v7_second_candidate', base/'context-budget-pilot-v7/public-evidence/candidate-02.py', base/'context-budget-pilot-v7/public-evidence/candidate-02-verification.json', 2),
]
records = []
for label, code_path, report_path, candidate in stages:
    code = code_path.read_text(encoding='utf8')
    report = json.loads(report_path.read_text(encoding='utf8'))
    feedback = _model_work_feedback(report, config)
    host = {'current_candidate':candidate or None, 'current_candidate_sha256':hashlib.sha256(code.encode()).hexdigest(),
            'last_verified_candidate':candidate or None,'last_verification_verdict':'FAIL' if candidate else None,
            'remaining_candidates':3-candidate,'remaining_verifications':3-candidate}
    state = {'strategy':'bounded_patch','executor':generation_state(host),
             'remaining_generations':3-candidate,'remaining_requests':4-candidate,'remaining_format_corrections':1}
    for correction in ([None, 'truncated_or_nonstop_response'] if candidate == 2 else [None]):
        name=label+('-format-correction' if correction else '')
        payload = build_payload(context, code, tests, feedback, state, correction=correction)
        budget = estimate_input_budget(payload, OUTPUT_TOKENS)
        checks = {'no_tools':'tools' not in payload,'code_in_actual_request':code in payload['messages'][1]['content'],
                  'tests_in_actual_request':all(t in payload['messages'][1]['content'] for t in tests.values()),
                  'real_FAIL':feedback['verdict']=='FAIL','no_old_loop_instruction':'native tool calls only' not in json.dumps(payload),
                  'budget':budget['within_context_budget'] and budget['within_wire_limit']}
        (dest/(name+'-payload.json')).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        records.append({'stage':name,'kind':'NO_MODEL_MESSAGE_CONSTRUCTION','checks':checks,'budget':budget,
                        'source':code_path.relative_to(ROOT).as_posix(),'source_sha256':hashlib.sha256(code_path.read_bytes()).hexdigest(),
                        'report':report_path.relative_to(ROOT).as_posix()})
summary={'schema':'credproof.bounded-patch-preflight/v1','model_calls':0,'candidate_execution':False,
         'records':records,'all_checks_pass':all(all(r['checks'].values()) for r in records),
         'scope':'three saved source/report states and one format correction; not arbitrary source length proof'}
(dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
print(json.dumps(summary,indent=2))
raise SystemExit(0 if summary['all_checks_pass'] else 1)
