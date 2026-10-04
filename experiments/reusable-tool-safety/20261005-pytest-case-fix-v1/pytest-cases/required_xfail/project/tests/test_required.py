import pytest

@pytest.mark.xfail(strict=True, reason='known failing requirement')
def test_business():
    assert False
