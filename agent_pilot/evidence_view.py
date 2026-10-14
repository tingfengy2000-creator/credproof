"""Five reader questions derived from one checker report; never a new verdict.

The checker's 14 required conditions remain the decision.  This module only
groups recorded report fields so a reviewer can answer: is the business still
working, did file access stay in scope, where did requests go, where did the
credential appear, and can the version be adopted.  Credential values are never
read or returned; only channel names and counts.
"""
from __future__ import annotations

from pathlib import PurePosixPath

STATES = ('ok', 'bad', 'missing', 'unknown')


def _list(value):
    return value if isinstance(value, list) else []


def _int(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _lab_relative(path):
    """Show lab paths as data/x or secrets/x; never a host path."""
    if not isinstance(path, str):
        return None
    parts = PurePosixPath(path).parts
    if len(parts) > 3 and parts[:3] == ('/', 'tmp', 'lab'):
        return '/'.join(parts[3:])
    return PurePosixPath(path).name or None


def five_questions(report, *, decision='PENDING', application='NOT_APPLIED', applicable=True):
    """Return the summary described in docs/ui/PRODUCT-API.md section 5.

    ``report`` is a credproof.safety.report/v1 dictionary (already redacted by
    the checker).  ``None`` means there is no applicable report.
    """
    if not isinstance(report, dict) or not applicable:
        return None
    verdict = report.get('verdict') if report.get('verdict') in ('PASS', 'FAIL', 'UNKNOWN') else 'UNKNOWN'
    execution = report.get('execution') if isinstance(report.get('execution'), dict) else {}
    summary = report.get('observation_summary') if isinstance(report.get('observation_summary'), dict) else {}
    checks = report.get('required_checks') if isinstance(report.get('required_checks'), dict) else {}
    complete = verdict in ('PASS', 'FAIL') and bool(checks)
    config = report.get('config') if isinstance(report.get('config'), dict) else {}

    pytest = execution.get('pytest_observation') if isinstance(execution.get('pytest_observation'), dict) else {}
    events = [x for x in _list(execution.get('audit_events')) if isinstance(x, dict)]
    requests = [x for x in _list(execution.get('requests')) if isinstance(x, dict)]
    allowed_reads = sum(1 for x in events if x.get('event') == 'open' and x.get('classification') == 'allowed')
    allowed_requests = [x for x in requests if x.get('service') == 'allow']
    forbidden_requests = [x for x in requests if x.get('service') == 'forbidden']
    allowed_auth = sum(1 for x in allowed_requests if x.get('credential_ok') is True)
    raised = execution.get('raised') if isinstance(execution.get('raised'), dict) else None
    scenarios = [x for x in _list(execution.get('entry_scenarios')) if isinstance(x, dict)]

    def state(bad_keys, must_keys=()):
        if not complete:
            return 'unknown'
        if any(checks.get(key) is False for key in bad_keys):
            return 'bad'
        if any(checks.get(key) is False for key in must_keys):
            return 'missing'
        return 'ok'

    # Business: failing tests or scenarios without an observed violation means
    # the required behaviour did not happen (missing), not an attack (bad).
    business_keys = ('pytest', 'required_pytest_tests', 'entry_completed', 'required_entry_scenarios',
                     'required_allowed_file_read', 'allowed_service_receipt', 'required_service_credential')
    violation = summary.get('classification') == 'ACTUAL_VIOLATION'
    # A scenario that fails only because it reached a forbidden place is a
    # request/credential problem, not missing business behaviour.
    business = state((), [k for k in business_keys if not (violation and k == 'required_entry_scenarios')])
    if business == 'missing' and violation and \
            all(checks.get(k) is not False for k in ('entry_completed', 'required_allowed_file_read',
                                                       'allowed_service_receipt', 'required_service_credential')):
        # Behaviour happened but business tests failed alongside an actual violation.
        business = 'bad'
    files_state = state(('no_forbidden_file_read', 'no_out_of_scope_file_read'), ('required_allowed_file_read',))
    request_state = state(('no_forbidden_service_receipt', 'no_unauthorized_connection', 'allowed_service_path'),
                          ('allowed_service_receipt', 'required_service_credential'))
    credential_state = state(('no_credential_output', 'no_forbidden_service_receipt'))
    if credential_state == 'ok' and complete and config.get('require_service_credential') and allowed_auth == 0:
        credential_state = 'missing'

    forbidden_paths = sorted({p for p in (_lab_relative(x.get('resolved_path') or x.get('path'))
                                          for x in _list(execution.get('forbidden_reads')) if isinstance(x, dict)) if p})
    channels = [x if isinstance(x, str) else x.get('channel') for x in _list(execution.get('credential_leaks'))
                if isinstance(x, (str, dict))]
    redirects = []
    for row in scenarios:
        observed = [x for x in _list(row.get('request_observations')) if isinstance(x, dict)]
        if row.get('require_network') or any(str(x.get('path', '')).endswith('/redirect') for x in observed):
            redirects.append({'name': row.get('name'), 'expected_error': row.get('expected_error'),
                              'raised': (row.get('raised') or {}).get('type') if isinstance(row.get('raised'), dict) else None,
                              'followed_to_forbidden': any(x.get('service') == 'forbidden' for x in observed)})
    adoption_state = 'ok' if verdict == 'PASS' and decision == 'APPROVED' else \
        'bad' if verdict == 'FAIL' or decision in ('REJECTED', 'NEEDS_CHANGES') else \
        'unknown' if verdict == 'UNKNOWN' else 'missing'
    questions = [
        {'id': 'business', 'state': business, 'facts': {
            'tests_required': _int(pytest.get('required_case_count')),
            'tests_collected': _int(pytest.get('collected')),
            'tests_executed': _int(pytest.get('executed')),
            'tests_passed': _int(pytest.get('passed')),
            'tests_failed': _int(pytest.get('failed')),
            'tests_skipped': _int(pytest.get('skipped')),
            'allowed_reads': allowed_reads,
            'allowed_auth_requests': allowed_auth,
            'entry_error': {'type': raised.get('type')} if raised else None,
            'require_allowed_file_read': bool(config.get('require_allowed_file_read')),
            'require_service_credential': bool(config.get('require_service_credential'))}},
        {'id': 'files', 'state': files_state, 'facts': {
            'allowed_dir': (_list(config.get('allowed_dirs')) or [None])[0],
            'forbidden_dir': (_list(config.get('forbidden_dirs')) or [None])[0],
            'allowed_reads': allowed_reads,
            'forbidden_reads': len(_list(execution.get('forbidden_reads'))),
            'out_of_scope_reads': len(_list(execution.get('out_of_scope_reads'))),
            'forbidden_paths': forbidden_paths}},
        {'id': 'requests', 'state': request_state, 'facts': {
            'allowed': len(allowed_requests), 'forbidden': len(forbidden_requests),
            'unauthorized_connections': len(_list(execution.get('unauthorized_connections'))),
            'paths': [{'service': x.get('service'), 'path': x.get('path'),
                       'authorization': x.get('authorization_present') is True} for x in requests[:40]],
            'redirect_scenarios': redirects}},
        {'id': 'credential', 'state': credential_state, 'facts': {
            'output_channels': sorted({c for c in channels if isinstance(c, str)}),
            'sent_to_forbidden': sum(1 for x in forbidden_requests if x.get('authorization_present') is True),
            'used_with_allowed_service': allowed_auth}},
        {'id': 'adoption', 'state': adoption_state, 'facts': {
            'technical': verdict, 'decision': decision, 'application': application}},
    ]
    return {'verdict': verdict,
            'classification': summary.get('classification') or ('INCOMPLETE' if verdict == 'UNKNOWN' else None),
            'unknown_reason': report.get('reason') if verdict == 'UNKNOWN' else None,
            'questions': questions,
            'failed_conditions': [x for x in _list(report.get('failed_checks')) if isinstance(x, str)],
            'duration_ms': report.get('duration_ms') if isinstance(report.get('duration_ms'), (int, float)) else None}
