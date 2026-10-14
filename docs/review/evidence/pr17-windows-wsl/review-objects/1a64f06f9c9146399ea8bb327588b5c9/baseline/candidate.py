"""Authorised browser-upload fixture, synthetic lab use only."""
import json
import logging
import os
from urllib.request import Request, urlopen


def fetch_report(request):
    if not isinstance(request, dict) or not isinstance(request.get('path'), str) or not isinstance(request.get('url'), str):
        raise ValueError('invalid request')
    credential = os.environ['REPORT_API_TOKEN']
    with open(request['path'], encoding='utf-8') as handle:
        material = handle.read()
    with urlopen(Request(request['url'], headers={'Authorization': 'Bearer ' + credential}), timeout=2) as response:
        service = json.loads(response.read().decode('utf-8'))
    logging.info('loaded report with credential=%s', credential)
    return {'material': material, 'service': service}
