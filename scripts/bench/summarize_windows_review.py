"""Offline accounting of completed bench-v1 evidence; never calls a model/checker."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    args = p.parse_args()
    output = args.evidence/'accounting.json'
    if output.exists():
        raise SystemExit('new accounting receipt required')
    completion = read(args.evidence/'model-run/completion.json')
    if completion['status'] != 'COMPLETE':
        raise SystemExit('run is not complete')
    generation = []
    for folder in sorted((args.run/'patches').iterdir()):
        req, res, ext = [read(folder/f'{name}.json') for name in ('request', 'response', 'extraction')]
        record = read(folder/'check.json') if (folder/'check.json').is_file() else None
        generation.append({'id': folder.name, 'model': req['model'], 'extraction': ext['status'],
                           'verdict': record['verdict'] if record else 'NOT_CHECKED',
                           'business_green': record['business_tests_all_passed'] if record else None,
                           'failed_checks': record['failed_checks'] if record else None,
                           'forbidden_service_receipts': record['forbidden_service_receipts'] if record else None,
                           'credential_sent_to_forbidden': record['credential_sent_to_forbidden'] if record else None,
                           'source_sha256_lf': ext.get('sha256'), 'error': res['error'],
                           'seconds': res['seconds'], 'prompt_tokens': res['raw'].get('prompt_eval_count'),
                           'output_tokens': res['raw'].get('eval_count')})
    judges = {}
    for folder in sorted((args.run/'judges').iterdir()):
        rows = [read(f) for f in sorted(folder.glob('*.json')) if f.name != 'judge.json']
        judges[read(folder/'judge.json')['model']['name']] = {
            'items': len(rows), 'verdicts': dict(Counter(r['verdict'] for r in rows)),
            'errors': sum(r['error'] is not None for r in rows)}
    requests, usage, devices = Counter(), Counter(), {}
    for f in sorted((args.evidence/'model-run/transport').glob('*.request.json')):
        req = read(f)
        if req['path'] != '/api/chat':
            continue
        response = read(f.with_name(f.name.replace('.request.', '.response.')))
        body, raw = json.loads(req['raw_body_utf8']), json.loads(response['body'])
        requests[req['phase']] += 1
        for key in ('prompt_eval_count', 'eval_count'):
            if isinstance(raw.get(key), int):
                usage[key] += raw[key]
        for model in (response.get('ps') or {}).get('models', []):
            devices[model['name']] = {k: model.get(k) for k in ('digest', 'size', 'size_vram', 'context_length', 'details')}
    initial = [r for r in generation if r['id'].endswith('__r0')]
    assert len(initial) == 8*2*3
    for row in initial:
        feedback = next((r for r in generation if r['id'] == row['id'][:-1]+'1'), None)
        assert (feedback is None) == (row['verdict'] == 'PASS')
    assert len(generation) == requests['generation'] == completion['model_request_counts']['generation']
    assert requests['judge'] == sum(j['items'] for j in judges.values()) == completion['model_request_counts']['judge']
    assert all(j['items'] == len(generation)+16 for j in judges.values())
    value = {'kind': 'OFFLINE_DERIVED_ACCOUNTING_NOT_A_NEW_EXPERIMENT',
             'source_commit': completion['source_commit'], 'targets': 8, 'models': 2, 'seeds_per_target_model': 3,
             'initial_requests': len(initial), 'feedback_requests': len(generation)-len(initial),
             'generated_proposals': len(generation), 'distinct_lf_codes': len({r['source_sha256_lf'] for r in generation}),
             'generation_verdicts': dict(Counter(r['verdict'] for r in generation)),
             'by_model': {m: dict(Counter(r['verdict'] for r in generation if r['model'] == m)) for m in {r['model'] for r in generation}},
             'generation_rows': generation, 'judges': judges, 'transport_inferences': dict(requests),
             'usage_sum_actual_service_counts': dict(usage), 'actual_loaded_model_devices': devices,
             'native_model_tool_calls': 0, 'resampling_or_retry': 0,
             'note': '51 proposals, 48 initial sampling slots and 8 targets are different denominators. History is not merged into new-generation success.'}
    output.write_text(json.dumps(value, ensure_ascii=False, indent=1)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({k: v for k, v in value.items() if k not in ('generation_rows',)}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
