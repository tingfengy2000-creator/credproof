"""Non-semantic source-format derivation. Never imports or executes a candidate."""
from __future__ import annotations

import ast
import hashlib
import re

RULE_VERSION = 'credproof.python-outer-fence/v1'
MAX_SOURCE_BYTES = 65536


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf8')).hexdigest()


def check_python_syntax(source: str) -> dict:
    if not isinstance(source, str) or len(source.encode('utf8')) > MAX_SOURCE_BYTES:
        return {'status': 'INVALID_SOURCE', 'reason': 'source_type_or_size', 'executed': False}
    try:
        tree = ast.parse(source, filename='<derived-candidate>', mode='exec')
        # Also rejects statements which parse to AST but cannot compile at module scope.
        compile(tree, '<derived-candidate>', 'exec', dont_inherit=True)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        return {'status': 'INVALID_SOURCE_SYNTAX', 'type': type(exc).__name__,
                'reason': str(exc), 'line': getattr(exc, 'lineno', None),
                'offset': getattr(exc, 'offset', None), 'executed': False}
    return {'status': 'VALID_SYNTAX', 'source_sha256': _sha(source), 'executed': False}


def normalize_python_source(source: str) -> tuple[str, dict]:
    """Keep pure source, or remove one complete outer ```/python/py block.

    Body bytes, including indentation and internal blank lines/newlines, are
    unchanged. Ambiguous/multiple/unsupported fences are rejected, not repaired.
    """
    if (not isinstance(source, str) or not source.strip() or '\0' in source
            or len(source.encode('utf8')) > MAX_SOURCE_BYTES):
        raise ValueError('OUTPUT_FORMAT_UNSUPPORTED: source_type_size_or_empty')
    lines = source.splitlines(keepends=True)
    active = [i for i, line in enumerate(lines) if line.strip()]
    first, last = active[0], active[-1]
    initial = lines[first].rstrip('\r\n')
    fence_hint = any(re.match(r'^\s*(?:```|~~~)', line) for line in lines)
    receipt = {'rule_version': RULE_VERSION, 'original_code_sha256': _sha(source),
               'original_code_bytes': len(source.encode('utf8')), 'deletions': [],
               'source': 'model_generated_then_format_normalized', 'semantic_edits': False}
    # A valid Python string/comment containing backticks is still pure source.
    if not fence_hint or check_python_syntax(source)['status'] == 'VALID_SYNTAX':
        normalized = source
        receipt['format'] = 'PURE_PYTHON_UNCHANGED'
    else:
        if (first == last or re.fullmatch(r'[^\S\r\n]*```(?:python|py)?[^\S\r\n]*', initial) is None
                or not lines[first].endswith(('\n', '\r'))
                or lines[last].strip() != '```'):
            raise ValueError('OUTPUT_FORMAT_UNSUPPORTED: incomplete_language_or_outer_wrapper')
        # No second block or ambiguous standalone fence inside the body.
        if any(re.match(r'^\s*(?:```|~~~)', line) for line in lines[first+1:last]):
            raise ValueError('OUTPUT_FORMAT_UNSUPPORTED: multiple_or_ambiguous_blocks')
        begin = sum(len(line) for line in lines[:first+1])
        end = sum(len(line) for line in lines[:last])
        normalized = source[begin:end]
        if not normalized.strip():
            raise ValueError('OUTPUT_FORMAT_UNSUPPORTED: empty_body')
        for start, stop in ((0, begin), (end, len(source))):
            receipt['deletions'].append({'character_range': [start, stop],
                'utf8_byte_range': [len(source[:start].encode('utf8')), len(source[:stop].encode('utf8'))],
                'text': source[start:stop]})
        receipt['format'] = 'SINGLE_COMPLETE_OUTER_FENCE_REMOVED'
        receipt['body_preserved_exactly'] = True
    receipt.update(normalized_code_sha256=_sha(normalized), normalized_code_bytes=len(normalized.encode('utf8')))
    return normalized, receipt
