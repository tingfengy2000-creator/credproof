"""Small program-enforced tool boundary shared by the handshake and repair pilot."""
import json
import time
from pathlib import Path

import jsonschema
from qwen_agent.tools.base import BaseTool


class StrictTool(BaseTool):
    def __init__(self, name, description, properties, required, handler, audit):
        self.name, self.description = name, description
        self.parameters = {'type': 'object', 'properties': properties, 'required': required}
        self.handler, self.audit = handler, audit
        super().__init__()

    def call(self, params, **kwargs):
        started = time.perf_counter()
        try:
            data = json.loads(params) if isinstance(params, str) else params
            schema = dict(self.parameters, additionalProperties=False)
            jsonschema.validate(data, schema)
            result = self.handler(data)
        except (ValueError, TypeError, KeyError, jsonschema.ValidationError):
            # Do not echo untrusted content or host paths in parsing errors.
            result = {'status': 'REJECTED', 'reason': 'invalid_arguments_or_disallowed_path'}
        self.audit.append({'tool': self.name, 'arguments': params, 'result': result,
                           'elapsed_s': time.perf_counter() - started})
        return json.dumps(result, ensure_ascii=False)


def dispatch(tools, name, params):
    table = {tool.name: tool for tool in tools}
    if name not in table:
        return {'status': 'REJECTED', 'reason': 'unknown_tool'}
    return json.loads(table[name].call(params))


def code_path(value):
    if value != 'tool.py':
        raise ValueError('Only the explicit task source is readable/editable')
    return value


def write_json_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
