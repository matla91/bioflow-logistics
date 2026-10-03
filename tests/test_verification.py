import pytest
from baselhack.storage import read_yaml


@pytest.mark.verification
@pytest.mark.parametrize(
    "check", read_yaml("config/verification.yaml")["checks"], ids=lambda c: c["id"]
)
def test_required_verification(check):
    assert check["verified"], f"TODO(verify): {check['detail']}"
