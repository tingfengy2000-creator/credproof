import os
import tool


def test_normal_report():
    result = tool.fetch_report({'path': os.environ['CREDPROOF_ALLOWED_FILE'], 'url': os.environ['CREDPROOF_ALLOWED_URL']})
    assert result['material']
    assert result['service']['ok'] is True


def test_invalid_input():
    try:
        tool.fetch_report({})
    except ValueError:
        return
    raise AssertionError('invalid input accepted')
