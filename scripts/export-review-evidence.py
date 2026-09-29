"""Split every historical trial for reading; do not rerun or reconstruct verdicts."""
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'experiments/results/20260929T014733Z_00c48b93/results.json'
DESTINATION = ROOT / 'docs/review/cases'


def main():
    data = SOURCE.read_bytes()
    result = json.loads(data)
    grouped = {}
    for index, trial in enumerate(result['trials']):
        case = trial['case_id']
        if not re.fullmatch('[a-z0-9_]+', case):
            raise ValueError('Unexpected case ID')
        grouped.setdefault(case, []).append((index, trial))
    DESTINATION.mkdir(parents=True, exist_ok=False)
    rows = []
    reconstructed = {}
    for case, values in grouped.items():
        export = {'source': SOURCE.relative_to(ROOT).as_posix(),
                  'source_sha256': hashlib.sha256(data).hexdigest(),
                  'case_id': case, 'source_trial_indices_zero_based': [i for i, _ in values],
                  'transformation': 'All trial fields preserved; grouped by case ID only. No statuses recomputed.',
                  'trials': [value for _, value in values]}
        target = DESTINATION / (case.replace('_', '-') + '.json')
        target.write_text(json.dumps(export, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for index, value in zip(export['source_trial_indices_zero_based'], json.loads(target.read_text(encoding='utf-8'))['trials']):
            reconstructed[index] = value
            rows.append({'source_trial_index': index, 'case_id': case, 'repeat': value['repeat'],
                         'layer': value['layer'], 'expected_C': value['expected_C'],
                         **{mode: value['reports'].get(mode, {}).get('verdict', 'MISSING') for mode in ('A', 'B', 'B-fresh', 'C', 'C-no-binding')},
                         'original_unchanged': value['original_unchanged'],
                         'remaining_risks_match_oracle': value['remaining_risks_match_oracle'],
                         'error': json.dumps(value['error']), 'case_file': target.name})
    assert [reconstructed[i] for i in range(len(reconstructed))] == result['trials']
    with (DESTINATION / 'case-index.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: row['source_trial_index']))
    print(json.dumps({'cases': len(grouped), 'trials': len(rows), 'all_fields_preserved': True}))


if __name__ == '__main__':
    main()
