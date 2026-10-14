import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_dotenv_public_results_match_full_reports_and_same_export_object():
    data=json.loads((ROOT/'docs/compare/onboarding-dotenv.json').read_text('utf8'))
    assert data['schema']=='credproof.onboarding/v1' and data['environment']['model_calls']==0
    assert [x['verdict'] for x in data['results']]==['FAIL','PASS','FAIL','PASS']
    for row in data['results']:
        view=json.loads((ROOT/row['report']).read_text('utf8'));report=view['report']
        assert view['technical_verdict']==row['verdict']
        assert row['source_sha256']==view['version']['code_sha256']
        assert row['failed_conditions']==report['failed_checks']
        assert row['pytest']['collected']==row['pytest']['executed']==117
        assert row['upstream_tests']==114 and row['adapter_tests']==3
    assert data['results'][0]['pytest']['failed']==1
    assert data['results'][2]['pytest']['failed']==0
    assert 'no_forbidden_file_read' in data['results'][2]['failed_conditions']
    recheck=json.loads((ROOT/'docs/compare/onboarding-dotenv/recheck.json').read_text('utf8'))
    assert recheck['validation']['verdict']=='PASS'
    assert recheck['candidate_sha256']==data['results'][-1]['source_sha256']==data['exported']['candidate_sha256']
    assert data['exported']['version']=='v003' and data['exported']['decision']=='PENDING'
    assert all(s['time_minutes'] is None for s in data['steps'])
