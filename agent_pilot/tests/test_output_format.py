"""Pure formatting/compile protocol checks. No model or candidate execution."""
import pytest
from agent_pilot.output_format import normalize_python_source, check_python_syntax


def test_plain_source_and_backticks_unchanged():
    source = '\nmarker = "```"\ntext = """\n```\n"""\n'
    actual, receipt = normalize_python_source(source)
    assert actual == source
    assert receipt['deletions'] == []


@pytest.mark.parametrize('language', ['', 'python', 'py'])
def test_one_complete_fence_keeps_body_exactly(language):
    body = '\nvalue = "中文 ` ```"\n\ndef f():\n    return value\n\n'
    source = ' \n```' + language + '\n' + body + '```\n \t'
    actual, receipt = normalize_python_source(source)
    assert actual == body
    assert source == receipt['deletions'][0]['text'] + actual + receipt['deletions'][1]['text']
    assert check_python_syntax(actual)['status'] == 'VALID_SYNTAX'


def test_crlf_body_not_normalized():
    body = 'def f():\r\n    return "ok"\r\n'
    actual, _ = normalize_python_source('```py\r\n' + body + '```\r\n')
    assert actual == body


@pytest.mark.parametrize('source', [
    '```javascript\nx=1\n```', '```python\nx=1',
    'explanation\n```python\nx=1\n```', '```python\nx=1\n```\nextra',
    '```python\nx=1\n```\n```python\ny=2\n```',
    '```python\nx=1\n~~~\n```', '~~~python\nx=1\n~~~',
])
def test_ambiguous_or_unsupported_output_rejected(source):
    with pytest.raises(ValueError, match='OUTPUT_FORMAT_UNSUPPORTED'):
        normalize_python_source(source)


def test_invalid_python_is_not_semantically_repaired():
    actual, _ = normalize_python_source('```python\ndef bad(:\n```')
    assert actual == 'def bad(:\n'
    assert check_python_syntax(actual)['status'] == 'INVALID_SOURCE_SYNTAX'
    assert check_python_syntax('return 1')['status'] == 'INVALID_SOURCE_SYNTAX'
    assert check_python_syntax('x'*65537)['status'] == 'INVALID_SOURCE'
