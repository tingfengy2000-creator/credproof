import pytest

@pytest.mark.skip(reason='declared optional')
def test_optional():
    assert True
