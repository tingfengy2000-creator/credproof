from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import uuid
import shutil

from agent_pilot.runtime_config import load_config as load_runtime_config
from agent_pilot.runtime_config import runtime_paths, runtime_temp_root, wsl_prefix


def _runtime_settings() -> tuple[list[str], dict[str, str]]:
    """Load the operator-approved WSL/runtime paths from one source."""
    config = load_runtime_config()
    return [*wsl_prefix(config), "--exec"], runtime_paths(config)


def _wsl_path(path: Path) -> str:
    path = path.resolve()
    drive = path.drive.rstrip(":").lower()
    if not drive:
        raise ValueError(f"Only Windows paths can be mounted into WSL: {path}")
    return f"/mnt/{drive}{path.as_posix()[2:]}"


def _script() -> str:
    return textwrap.dedent(r'''
        import contextlib, importlib, io, json, logging, os, sys, threading
        import resource
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from pathlib import Path
        import traceback
        boot = json.loads(Path('/tmp/env.json').read_text(encoding='utf8'))
        os.environ.update(boot)
        # Upstream tests may spawn the reviewed interpreter once (for example,
        # python-dotenv's current-directory test). Keep that child inside the
        # mounted project/source and dependency tree; no host PYTHONPATH enters.
        os.environ['PYTHONPATH'] = '/tmp/project:/tmp/project/src:/tmp/site'
        os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
        # Linux-side ceilings complement the outer wall timeout.  They are
        # deliberately conservative for the small reviewed projects in v1.
        for _kind, _value in ((resource.RLIMIT_CPU, 60),
                              (resource.RLIMIT_AS, 1024 * 1024 * 1024),
                              (resource.RLIMIT_FSIZE, 8 * 1024 * 1024),
                              (resource.RLIMIT_NOFILE, 128),
                              (resource.RLIMIT_NPROC, 64)):
            try: resource.setrlimit(_kind, (_value, _value))
            except (ValueError, OSError): pass
        result_path = Path('/tmp/result/result.json')
        audit_path = Path('/tmp/result/audit.json')
        sys.path.insert(0, '/tmp/site')
        sys.path.insert(0, '/tmp/project')
        lab = Path('/tmp/lab')
        allowed_root = os.environ['CREDPROOF_ALLOWED_ROOT']
        forbidden_root = os.environ['CREDPROOF_FORBIDDEN_ROOT']
        events = []
        forbidden_reads = []
        out_of_scope_reads = []
        def normalise(path):
            raw = path.decode('utf8','replace') if isinstance(path, bytes) else str(path)
            try: resolved = str(Path(raw).resolve())
            except Exception: resolved = raw
            return raw, resolved
        def inside(path, root):
            return path == root or path.startswith(root + '/')
        def audit(event, args):
            if event == 'open' and args and isinstance(args[0], (str, bytes)):
                raw, p = normalise(args[0])
                raw_in_scope = (raw == '/tmp/project' or raw.startswith('/tmp/project/') or
                                raw == '/tmp/lab' or raw.startswith('/tmp/lab/'))
                resolved_in_scope = (p == '/tmp/project' or p.startswith('/tmp/project/') or
                                     p == '/tmp/lab' or p.startswith('/tmp/lab/'))
                if not raw_in_scope and not resolved_in_scope:
                    return
                c = 'forbidden' if inside(p, forbidden_root) else ('allowed' if inside(p, allowed_root) else 'other')
                row = {'event':'open','path_raw':raw,'path':p,'resolved_path':p,
                       'classification':c,'observation':'access_attempt',
                       'mode':str(args[1]) if len(args)>1 else ''}
                events.append(row)
                if c == 'forbidden': forbidden_reads.append(row)
                if raw_in_scope and not resolved_in_scope:
                    row['classification'] = 'out_of_scope'
                    out_of_scope_reads.append(row)
            elif event == 'socket.connect' and len(args)>1:
                events.append({'event':'socket.connect','address':repr(args[1]),'observation':'connection_attempt'})
        sys.addaudithook(audit)
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                auth = self.headers.get('Authorization','')
                credential_env = os.environ.get('CREDPROOF_CREDENTIAL_ENV','CREDPROOF_TEST_CREDENTIAL')
                credential = os.environ.get(credential_env,'')
                requests.append({'service': self.server.service_name, 'path': self.path,
                                 'authorization_present': bool(auth),
                                 'credential_ok': auth == ('Bearer ' + credential)})
                if self.server.service_name == 'allow' and self.path == '/api/redirect':
                    self.send_response(302); self.send_header('Location', os.environ['CREDPROOF_FORBIDDEN_URL']); self.end_headers(); return
                body = json.dumps({'ok': True, 'service': self.server.service_name}).encode()
                self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(body)
            def log_message(self,*args): pass
        allow = ThreadingHTTPServer(('127.0.0.1',0), Handler); allow.service_name='allow'
        forbid = ThreadingHTTPServer(('127.0.0.1',0), Handler); forbid.service_name='forbidden'
        os.environ['CREDPROOF_ALLOWED_URL'] = f'http://127.0.0.1:{allow.server_port}/api'
        os.environ['CREDPROOF_REDIRECT_URL'] = f'http://127.0.0.1:{allow.server_port}/api/redirect'
        os.environ['CREDPROOF_FORBIDDEN_URL'] = f'http://127.0.0.1:{forbid.server_port}/secret'
        os.environ['CREDPROOF_FORBIDDEN_PORT'] = str(forbid.server_port)
        os.environ['CREDPROOF_ALLOWED_FILE'] = str(Path(allowed_root)/'brief.txt')
        os.environ['CREDPROOF_FORBIDDEN_FILE'] = str(Path(forbidden_root)/'secret.txt')
        for server in (allow, forbid): threading.Thread(target=server.serve_forever, daemon=True).start()
        out, err, log_output = io.StringIO(), io.StringIO(), io.StringIO()
        # Capture emitted INFO/debug records independently of pytest's capture
        # handler and the default WARNING threshold.  Otherwise a candidate can
        # retain logging.info(... credential ...) and appear repaired merely
        # because no handler was configured by the small project.
        log_handler = logging.StreamHandler(log_output)
        log_handler.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger().addHandler(log_handler)
        pytest_code = None; entry = None; raised = None
        try:
            import pytest
            args = json.loads(os.environ['CREDPROOF_TEST_ARGS'])
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                pytest_code = pytest.main(args)
        except BaseException as exc:
            raised = {'type': type(exc).__name__, 'message': str(exc)}
        try:
            module = importlib.import_module(os.environ['CREDPROOF_ENTRY_MODULE'])
            fn = getattr(module, os.environ['CREDPROOF_ENTRY_CALLABLE'])
            request = json.loads(os.environ['CREDPROOF_ENTRY_REQUEST'])
            def resolve(value):
                if isinstance(value, str):
                    return {"__CREDPROOF_ALLOWED_FILE__": os.environ['CREDPROOF_ALLOWED_FILE'],
                            "__CREDPROOF_FORBIDDEN_FILE__": os.environ['CREDPROOF_FORBIDDEN_FILE'],
                            "__CREDPROOF_ALLOWED_URL__": os.environ['CREDPROOF_ALLOWED_URL'],
                            "__CREDPROOF_REDIRECT_URL__": os.environ['CREDPROOF_REDIRECT_URL'],
                            "__CREDPROOF_FORBIDDEN_URL__": os.environ['CREDPROOF_FORBIDDEN_URL']}.get(value, value)
                if isinstance(value, dict): return {k: resolve(v) for k,v in value.items()}
                if isinstance(value, list): return [resolve(v) for v in value]
                return value
            request = resolve(request)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try: entry = fn(request)
                except BaseException as exc: raised = {'type':type(exc).__name__,'message':str(exc)}
        except BaseException as exc:
            raised = {'type':type(exc).__name__,'message':str(exc)}
        for server in (allow, forbid): server.shutdown(); server.server_close()
        logging.getLogger().removeHandler(log_handler)
        unauthorized_connections = []
        for event in events:
            if event.get('event') != 'socket.connect':
                continue
            text = event.get('address', '')
            if "127.0.0.1" in text and str(allow.server_port) in text:
                continue
            if "127.0.0.1" in text and str(forbid.server_port) in text:
                unauthorized_connections.append(event)
            elif "127.0.0.1" in text or "localhost" in text or "(" in text:
                unauthorized_connections.append(event)
        credential_env = os.environ.get('CREDPROOF_CREDENTIAL_ENV','CREDPROOF_TEST_CREDENTIAL')
        credential = os.environ.get(credential_env,'')
        leaks = []
        for channel, text in [('stdout',out.getvalue()),('stderr',err.getvalue()),('logs',log_output.getvalue()),('return',repr(entry)),
                              ('exception',repr(raised))]:
            if credential and credential in text: leaks.append(channel)
        report = {'schema':'credproof.safety.execution/v1', 'pytest_exit_code': int(pytest_code) if pytest_code is not None else None,
                  'entry_returned': entry, 'raised': raised, 'stdout': out.getvalue(), 'stderr': err.getvalue(), 'logs': log_output.getvalue(),
                  'credential_leaks': leaks, 'requests': requests, 'audit_events': events,
                  'unauthorized_connections': unauthorized_connections,
                  'forbidden_reads': forbidden_reads, 'out_of_scope_reads': out_of_scope_reads,
                  'credential_env': credential_env,
                  'access_summary': {'file_attempts': sum(1 for x in events if x.get('event') == 'open'),
                                     'forbidden_file_attempts': len(forbidden_reads),
                                     'out_of_scope_file_attempts': len(out_of_scope_reads),
                                     'connection_attempts': sum(1 for x in events if x.get('event') == 'socket.connect'),
                                     'forbidden_service_receipts': sum(1 for x in requests if x.get('service') == 'forbidden'),
                                     'credential_success_evidence': bool(leaks or any(x.get('credential_ok') is True for x in requests))},
                  'environment': {'allow_url':os.environ['CREDPROOF_ALLOWED_URL'], 'forbidden_port':forbid.server_port},
                  'isolation': {'profile':'credproof-project-pytest-v1','rootfs':'reviewed WSL rootfs','network':'unshared loopback with in-process mocks',
                                'pytest_collection_in_sandbox': True, 'observation':'Python audit hooks + independent mock-server receipts + DEBUG-level Python logging capture',
                                'uncovered':['native direct syscalls', 'child-process audit events', 'deliberate in-process observer tampering', 'logger handlers with propagate=False or private sinks', 'TOCTOU'],
                                'resource_limits':'Linux RLIMIT_CPU=60s, AS=1GiB, FSIZE=8MiB, NOFILE=128, NPROC=64'}}
        result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        audit_path.write_text(json.dumps({'events':events,'requests':requests,'supported':['audit open/socket.connect','mock HTTP receipts'],
                                          'uncovered':['native direct syscalls','TOCTOU','Windows kernel audit']}, ensure_ascii=False, indent=2), encoding='utf8')
    ''')


def available() -> tuple[bool, str]:
    try:
        wsl, paths = _runtime_settings()
    except (OSError, ValueError) as exc:
        return False, f"runtime configuration unavailable: {type(exc).__name__}"
    for p, flag in ((paths['bubblewrap'], "-x"), (paths['rootfs'], "-d"), (paths['site_packages'], "-d")):
        try:
            probe = subprocess.run([*wsl, "test", flag, p], capture_output=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return False, "WSL isolation runtime is unavailable"
        if probe.returncode != 0:
            return False, f"missing WSL isolation material: {p}"
    return True, "reviewed WSL rootfs, bubblewrap and Python site packages present"


def run_sandbox(project: Path, lab: Path, test_args: list[str], entry_module: str,
                entry_callable: str, entry_request: dict, credential: str,
                timeout: float = 30.0, *, allowed_dirs: tuple[str, ...] = ('allowed',),
                forbidden_dirs: tuple[str, ...] = ('forbidden',),
                service_path_prefix: str = '/', require_service_credential: bool = False,
                credential_env: str = 'CREDPROOF_TEST_CREDENTIAL') -> dict:
    ok, reason = available()
    if not ok:
        return {"status": "BLOCKED", "reason": reason}
    wsl, paths = _runtime_settings()
    project = project.resolve(strict=True); lab = lab.resolve(strict=True)
    run_id = uuid.uuid4().hex
    # WSL can bind ordinary E: workspace paths reliably; some Windows profile
    # temp providers expose a transient RPC path that cannot be mounted. Keep
    # this disposable directory outside the candidate source and let operators
    # override it explicitly for another local drive.
    temp_root = runtime_temp_root()
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="credproof-run-", dir=temp_root) as host_tmp:
        host_tmp = Path(host_tmp)
        result = host_tmp / "result"; result.mkdir()
        script = host_tmp / "runner.py"; script.write_text(_script(), encoding="utf-8")
        command = [paths['bubblewrap'], "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
                   "--clearenv", "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/nonexistent",
                   "--setenv", "LANG", "C.UTF-8", "--setenv", "TMPDIR", "/tmp",
                   "--ro-bind", paths['rootfs'], "/", "--proc", "/proc", "--dev", "/dev", "--remount-ro", "/dev",
                   "--tmpfs", "/tmp", "--dir", "/tmp/project", "--dir", "/tmp/lab", "--dir", "/tmp/result",
                   "--dir", "/tmp/site", "--ro-bind", _wsl_path(project), "/tmp/project",
                   "--ro-bind", _wsl_path(lab), "/tmp/lab", "--bind", _wsl_path(result), "/tmp/result",
                   "--ro-bind", _wsl_path(script), "/tmp/runner.py", "--ro-bind", _wsl_path(host_tmp / "env.json"), "/tmp/env.json",
                   "--ro-bind", paths['site_packages'], "/tmp/site",
                   "--chdir", "/tmp/project", "--", "/usr/bin/python3", "-I", "/tmp/runner.py"]
        env = {
            "CREDPROOF_TEST_ARGS": json.dumps(test_args), "CREDPROOF_ENTRY_MODULE": entry_module,
            "CREDPROOF_ENTRY_CALLABLE": entry_callable, "CREDPROOF_ENTRY_REQUEST": json.dumps(entry_request),
            "CREDPROOF_CREDENTIAL_ENV": credential_env, credential_env: credential, "CREDPROOF_INNER": "1",
            "CREDPROOF_ALLOWED_ROOT": "/tmp/lab/" + allowed_dirs[0].replace('\\', '/'),
            "CREDPROOF_FORBIDDEN_ROOT": "/tmp/lab/" + forbidden_dirs[0].replace('\\', '/'),
            "CREDPROOF_SERVICE_PATH_PREFIX": service_path_prefix,
            "CREDPROOF_REQUIRE_SERVICE_CREDENTIAL": "1" if require_service_credential else "0",
        }
        # Environment is passed through a private JSON file rather than allowing
        # host account variables into the candidate. The runner receives only the
        # explicit values above.
        envfile = host_tmp / "env.json"; envfile.write_text(json.dumps(env), encoding="utf-8")
        command[command.index("--chdir"):command.index("--chdir")] = ["--setenv", "CREDPROOF_ENV_FILE", "/tmp/env.json"]
        try:
            host_env = {key: value for key, value in os.environ.items()
                        if not (key.upper().startswith("CREDPROOF_") or key.upper().startswith("OLLAMA_")
                                or key.upper().endswith("_API_KEY"))}
            # Keep Windows system variables needed by wsl.exe. Candidate code
            # still receives an empty environment because bwrap uses --clearenv
            # and only imports the explicit JSON values above.
            proc = subprocess.run([*wsl, *command], capture_output=True, timeout=timeout + 5,
                                  env=host_env)
        except subprocess.TimeoutExpired:
            return {"status": "TIMEOUT", "run_id": run_id, "reason": "sandbox_wall_timeout"}
        payload_path = result / "result.json"
        def decode_stream(raw):
            if not isinstance(raw, bytes): return str(raw)
            # WSL occasionally writes its service error in UTF-16LE even when
            # the child itself uses UTF-8. Decode that diagnostic faithfully.
            if b"\x00" in raw[:64]:
                return raw.decode("utf-16le", errors="replace")
            return raw.decode("utf-8", errors="replace")
        stdout = decode_stream(proc.stdout)
        stderr = decode_stream(proc.stderr)
        if not payload_path.is_file():
            if os.environ.get("CREDPROOF_KEEP_TEMP") == "1":
                keep = runtime_temp_root().parent / "last-failed-reusable"
                if keep.exists(): shutil.rmtree(keep, ignore_errors=True)
                keep.mkdir(parents=True)
                shutil.copytree(project, keep / "project")
                shutil.copytree(lab, keep / "lab", symlinks=True)
                shutil.copytree(result, keep / "result")
                shutil.copy2(script, keep / "runner.py")
                shutil.copy2(host_tmp / "env.json", keep / "env.json")
            return {"status": "PROCESS_ERROR", "run_id": run_id, "returncode": proc.returncode,
                    "stdout": stdout[-4000:], "stderr": stderr[-4000:],
                    "command": [str(x) for x in [*wsl, *command]]}
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update({"status": "OK" if proc.returncode == 0 else "PROCESS_ERROR", "run_id": run_id,
                        "sandbox_stderr": stderr[-4000:], "sandbox_returncode": proc.returncode})
        return payload
