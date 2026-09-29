import os
import logging
import json

def _valid(request):
    return isinstance(request, dict) and isinstance(request.get('request_id'), str) and bool(request['request_id']) and isinstance(request.get('resource'), str) and bool(request['resource']) and (type(request.get('units')) is int) and (1 <= request['units'] <= 5) and (type(request.get('debug', False)) is bool)

def _error(request, kind, message):
    identifier = request.get('request_id', '') if isinstance(request, dict) else ''
    if not isinstance(identifier, str):
        identifier = ''
    return {'ok': False, 'request_id': identifier, 'error': {'type': kind, 'message': message}}

def _success(request, authorization):
    return {'ok': True, 'request_id': request['request_id'], 'resource': request['resource'], 'units': request['units'], 'total': request['units'] * 7, 'subject': authorization['subject'], 'meta': {'route': 'local-mock', 'debug': request.get('debug', False)}}

def _provider_result(service, supplied, resource):
    try:
        return {'reply': service.authenticate(supplied, resource), 'failure': None}
    except RuntimeError as problem:
        return {'reply': None, 'failure': {'operation': 'authenticate', 'details': 'Authentication service unavailable'}}

def _report_provider_failure(failure):
    logging.getLogger('local.provider').warning('provider failure=%s', json.dumps(failure))

def run(request, auth_service):
    if not _valid(request):
        return _error(request, 'invalid_request', 'Invalid request')
    outcome = _provider_result(auth_service, os.environ['CP_TEST_CREDENTIAL'], request['resource'])
    if outcome['failure'] is not None:
        _report_provider_failure(outcome['failure'])
        return _error(request, 'auth_unavailable', 'Authentication service unavailable')
    if not outcome['reply']['authorized']:
        return _error(request, 'permission_denied', 'Permission denied')
    return _cp_redact(_success(request, outcome['reply']))

def _cp_redact(value):
    secret = os.environ.get('CP_TEST_CREDENTIAL', '')
    if isinstance(value, str):
        return value.replace(secret, '[REDACTED]') if secret else value
    if isinstance(value, dict):
        return {_cp_redact(key): _cp_redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_cp_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple((_cp_redact(item) for item in value))
    return value
