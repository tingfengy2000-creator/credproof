"""受控修复适配层：保留 dotenv 解析，限制到授权目录。"""
from pathlib import Path
from dotenv import dotenv_values
import os


def run(request):
    allowed = Path(os.environ["CREDPROOF_ALLOWED_FILE"]).resolve(strict=True).parent
    candidate = Path(request["path"]).resolve(strict=True)
    if not candidate.is_relative_to(allowed):
        raise ValueError("dotenv path is outside the configured directory")
    return {"values": dict(dotenv_values(candidate))}
