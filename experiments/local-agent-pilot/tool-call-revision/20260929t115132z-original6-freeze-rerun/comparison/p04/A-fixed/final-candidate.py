import os

def _success(request, identity):
    return {'ok': True, 'request_id': request['request_id'], 'resource': request['resource'], 'units': request['units'], 'total': request['units'] * 7, 'subject': identity['subject'], 'meta': {'route': 'local-mock', 'debug': request.get('debug', False)}}

def run(request, auth_service):
    request_id = request.get('request_id', '') if isinstance(request, dict) else ''
    request_id = request_id if isinstance(request_id, str) else ''
    valid = isinstance(request, dict) and isinstance(request.get('request_id'), str) and bool(request['request_id']) and isinstance(request.get('resource'), str) and bool(request['resource']) and (type(request.get('units')) is int) and (1 <= request['units'] <= 5) and (type(request.get('debug', False)) is bool)
    if not valid:
        return {'ok': False, 'request_id': request_id, 'error': {'type': 'invalid_request', 'message': 'Invalid request'}}
    credential = os.environ['CP_TEST_CREDENTIAL']
    try:
        identity = auth_service.authenticate(credential, request['resource'])
    except RuntimeError:
        return {'ok': False, 'request_id': request_id, 'error': {'type': 'auth_unavailable', 'message': 'Authentication service unavailable'}}
    if not identity['authorized']:
        return {'ok': False, 'request_id': request_id, 'error': {'type': 'permission_denied', 'message': 'Permission denied'}}
    result = _success(request, identity)
    result['diagnostic'] = {'history': [{'transport': {'headers': {'Authorization': credential}}}]}
    return _cp_redact(result)

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
