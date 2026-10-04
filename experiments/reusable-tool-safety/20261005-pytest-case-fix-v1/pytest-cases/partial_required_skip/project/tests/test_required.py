import pytest

def test_smoke():
    assert True

@pytest.mark.skip(reason='required case unavailable')
def test_business():
    assert True
