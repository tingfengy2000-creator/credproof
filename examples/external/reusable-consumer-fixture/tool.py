"""A tiny external-consumer fixture used only for exported regression tests."""
import os
from pathlib import Path
from urllib.request import Request, urlopen


def run(request):
    if not isinstance(request, dict) or not isinstance(request.get("resource"), str):
        raise ValueError("invalid request")
    allowed = Path(os.environ["CREDPROOF_ALLOWED_FILE"]).resolve(strict=True).parent
    path = Path(request.get("path") or os.environ["CREDPROOF_ALLOWED_FILE"]).resolve(strict=True)
    if not path.is_relative_to(allowed) or not path.is_file():
        raise ValueError("resource outside allowlist")
    env_name = os.environ.get("CREDPROOF_CREDENTIAL_ENV", "CREDPROOF_TEST_CREDENTIAL")
    credential = os.environ[env_name]
    with open(path, "r", encoding="utf-8") as handle:
        material = handle.read()
    response = urlopen(Request(os.environ["CREDPROOF_ALLOWED_URL"],
                               headers={"Authorization": "Bearer " + credential}), timeout=2)
    return {"resource": request["resource"], "material": material,
            "service": response.read().decode("utf-8"), "credential_used": True}
