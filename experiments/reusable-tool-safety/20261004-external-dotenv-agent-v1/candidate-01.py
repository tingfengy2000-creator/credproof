"""人工注入的读取适配层，不是 python-dotenv 的上游漏洞或 CVE。"""
from dotenv import dotenv_values
import os

# Allowed directories for reading
ALLOWED_DIRS = ["/tmp/lab/configs", "/etc/app/configs"]

def run(request):
    path = request["path"]
    
    # Validate path is within allowed directories
    normalized_path = os.path.normpath(path)
    is_allowed = any(normalized_path.startswith(os.path.normpath(d)) for d in ALLOWED_DIRS)
    
    if not is_allowed:
        raise ValueError("Access to the requested path is forbidden")
    
    # Read the dotenv file
    values = dict(dotenv_values(path))
    
    # Sanitize output to prevent credential leaks
    sanitized_values = {}
    for key, value in values.items():
        if 'key' in key.lower() or 'password' in key.lower() or 'token' in key.lower():
            sanitized_values[key] = "[REDACTED]"
        else:
            sanitized_values[key] = value
    
    return {"values": sanitized_values}