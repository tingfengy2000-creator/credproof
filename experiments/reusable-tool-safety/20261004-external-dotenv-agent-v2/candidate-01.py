"""人工注入的读取适配层，不是 python-dotenv 的上游漏洞或 CVE。"""
from dotenv import dotenv_values
import os


def run(request):
    path = request["path"]
    # Check if the file exists before trying to read it
    if not os.path.exists(path):
        raise FileNotFoundError(f"No such file or directory: '{path}'")
    # Injection for the controlled CredProof case: no configured directory check.
    return {"values": dict(dotenv_values(path))}