"""Trusted Linux namespace supervisor. Candidate text is never host-executed."""
from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

BASE = Path('/home/tingfeng/credproof-agent-runtime/isolation')
PACKAGE_URL = 'https://archive.ubuntu.com/ubuntu/pool/main/b/bubblewrap/bubblewrap_0.9.0-1ubuntu0.3_amd64.deb'
PACKAGE_SHA256 = '2461f1beee9cb04c8942739fe1a2b37e7b7c2a3d518f0779dc75f9245baa3094'
MEMORY = 256 * 1024 * 1024
OUTPUT_LIMIT = 256 * 1024
CPU_SECONDS = 3
REQUIRED_CHECKS = frozenset(('no_host_home no_windows_mount no_gpu no_host_pid_root '
    'empty_routes capabilities_dropped no_new_privileges seccomp_active socket_denied '
    'fork_denied input_readonly device_directory_readonly shared_memory_readonly_or_absent '
    'runtime_readonly root_mount_readonly env_scrubbed fd_scope namespace_creation_denied '
    'memory_limited private_scratch_available scratch_size_limited namespace_ids_distinct '
    'output_bounded cpu_limited wall_time_limited').split())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, data):
    temporary = path.with_suffix('.new')
    temporary.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def tree_identity(root):
    return digest(json.dumps({p.relative_to(root).as_posix(): digest(p.read_bytes())
        for p in sorted(root.rglob('*')) if p.is_file()}, sort_keys=True).encode())


def prepare(runner_id):
    if sys.platform != 'linux' or platform.machine() != 'x86_64' or os.getuid() == 0:
        raise ValueError('The reviewed profile requires unprivileged x86_64 Linux')
    BASE.mkdir(parents=True, exist_ok=True)
    for path in (BASE, *BASE.parents):
        if path.is_symlink():
            raise ValueError('Linked runtime path is not accepted')
    root = BASE / 'rootfs'
    binary = BASE / 'tools/usr/bin/bwrap'
    if not binary.is_file():
        request = urllib.request.Request(PACKAGE_URL, headers={'User-Agent': 'CredProof-isolation-probe'})
        with urllib.request.urlopen(request, timeout=30) as response:
            package = response.read(200000)
        if digest(package) != PACKAGE_SHA256:
            raise ValueError('Official Ubuntu package checksum mismatch')
        deb = BASE / 'bubblewrap.deb'
        deb.write_bytes(package)
        subprocess.run(['dpkg-deb', '-x', str(deb), str(BASE / 'tools')], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    if binary.stat().st_mode & 0o6000:
        raise ValueError('Setuid/setgid bubblewrap is not accepted')
    root.mkdir(exist_ok=True)
    py = Path('/usr/bin/python3').resolve()
    version = f'python{sys.version_info.major}.{sys.version_info.minor}'
    stdlib = Path('/usr/lib') / version
    if not stdlib.is_dir():
        raise ValueError('Reviewed system Python standard library is unavailable')
    copied = set()
    def copy_file(source, destination=None):
        source = Path(source)
        destination = root / str(destination or source).lstrip('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        destination.chmod(0o755 if os.access(source, os.X_OK) else 0o644)
        copied.add(source)
    copy_file(py, '/usr/bin/python3')
    for source in stdlib.rglob('*'):
        if source.is_file() and not any(part in ('__pycache__', 'site-packages', 'dist-packages') for part in source.parts):
            copy_file(source)
    # ldd is applied only to trusted distribution Python binaries/extensions.
    libraries = set()
    for executable in [py, *sorted((stdlib / 'lib-dynload').glob('*.so'))]:
        result = subprocess.run(['ldd', str(executable)], capture_output=True, text=True, check=True, timeout=5)
        for name in re.findall(r'(/[^\s()]+)', result.stdout):
            if Path(name).is_file():
                libraries.add(Path(name))
    for library in sorted(libraries):
        copy_file(library)
    for name in ('proc', 'dev', 'tmp', 'work', 'nonexistent'):
        (root / name).mkdir(exist_ok=True)
    filter_file = BASE / 'seccomp.bpf'
    build_seccomp(filter_file)
    receipt = {'profile': 'credproof-python-single-process-v1', 'runner_id': runner_id,
               'package_url': PACKAGE_URL, 'package_sha256': PACKAGE_SHA256,
               'bwrap_sha256': digest(binary.read_bytes()), 'rootfs_id': tree_identity(root),
               'seccomp_sha256': digest(filter_file.read_bytes()), 'kernel': platform.release(),
               'python_version': platform.python_version(), 'candidate_executed': False,
               'ready': False, 'limits': {'address_space_bytes': MEMORY, 'cpu_seconds': CPU_SECONDS,
                   'output_bytes': OUTPUT_LIMIT, 'file_bytes': 4 * 1024 * 1024,
                   'open_files': 32, 'tmpfs_bytes': 16 * 1024 * 1024}}
    atomic_json(BASE / 'preparation.json', receipt)
    atomic_json(BASE / 'probe-receipt.json', receipt)
    return receipt


def build_seccomp(destination):
    library = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    library.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    context = library.seccomp_init(0x7fff0000)  # native-architecture allow, explicit dangerous-call denial
    if not context:
        raise ValueError('seccomp initialization failed')
    denied = ('socket socketpair connect bind listen accept accept4 sendto recvfrom sendmsg recvmsg '
              'clone clone3 fork vfork unshare setns mount umount2 pivot_root chroot '
              'ptrace process_vm_readv process_vm_writev bpf perf_event_open '
              'kexec_load kexec_file_load open_by_handle_at name_to_handle_at '
              'keyctl add_key request_key userfaultfd io_uring_setup execveat '
              'reboot swapon swapoff init_module finit_module delete_module').split()
    try:
        for name in denied:
            number = library.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and library.seccomp_rule_add(context, 0x00050000 | errno.EPERM, number, 0) != 0:
                raise ValueError('seccomp rule construction failed')
        with destination.open('wb') as output:
            if library.seccomp_export_bpf(context, output.fileno()) != 0:
                raise ValueError('seccomp export failed')
    finally:
        library.seccomp_release(context)


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY, MEMORY))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_MEMLOCK, (0, 0))


def verify_prepared(runner_id, require_ready=True):
    path = BASE / ('probe-receipt.json' if require_ready else 'preparation.json')
    receipt = json.loads(path.read_text(encoding='utf-8'))
    if require_ready and receipt.get('ready') is not True:
        raise ValueError('Isolation probes have not passed')
    expected = {'runner_id': runner_id, 'bwrap_sha256': digest((BASE / 'tools/usr/bin/bwrap').read_bytes()),
                'rootfs_id': tree_identity(BASE / 'rootfs'),
                'seccomp_sha256': digest((BASE / 'seccomp.bpf').read_bytes()), 'kernel': platform.release()}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('Isolation facilities changed since the probe')
    return receipt


def execute(candidate, harness, inputs, timeout, receipt):
    if not isinstance(candidate, str) or len(candidate.encode()) > 65536:
        raise ValueError('Candidate text exceeds the reviewed limit')
    if not isinstance(harness, str) or len(harness.encode()) > 131072:
        raise ValueError('Trusted harness exceeds the reviewed limit')
    payload = json.dumps(inputs, ensure_ascii=False).encode('utf-8')
    if len(payload) > 32768 or not 0.2 <= timeout <= 15:
        raise ValueError('Input/timeout exceeds the reviewed limit')
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='job-', dir=BASE) as temporary:
        work = Path(temporary)
        (work / 'tool.py').write_text(candidate, encoding='utf-8')
        # -I excludes cwd; explicitly expose only this read-only input directory.
        trusted = "import sys\nsys.path.insert(0, '/work')\n" + harness
        (work / 'runner.py').write_text(trusted, encoding='utf-8')
        with (BASE / 'seccomp.bpf').open('rb') as seccomp:
            command = [str(BASE / 'tools/usr/bin/bwrap'), '--unshare-all', '--die-with-parent',
                '--new-session', '--cap-drop', 'ALL', '--clearenv', '--setenv', 'PATH', '/usr/bin',
                '--setenv', 'HOME', '/nonexistent', '--setenv', 'LANG', 'C.UTF-8',
                '--setenv', 'TMPDIR', '/tmp', '--ro-bind', str(BASE / 'rootfs'), '/',
                '--proc', '/proc', '--dev', '/dev', '--remount-ro', '/dev',
                '--size', str(16 * 1024 * 1024), '--tmpfs', '/tmp',
                '--ro-bind', str(work), '/work', '--chdir', '/work', '--seccomp', str(seccomp.fileno()),
                '--', '/usr/bin/python3', '-I', '-B', '/work/runner.py']
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, pass_fds=(seccomp.fileno(),), close_fds=True,
                start_new_session=True, preexec_fn=limits, cwd=BASE,
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
            selector = selectors.DefaultSelector()
            for pipe, event, name in ((process.stdin, selectors.EVENT_WRITE, 'stdin'),
                                     (process.stdout, selectors.EVENT_READ, 'stdout'),
                                     (process.stderr, selectors.EVENT_READ, 'stderr')):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, event, name)
            output = {'stdout': bytearray(), 'stderr': bytearray()}
            offset, status = 0, None
            deadline = started + timeout
            try:
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        status = 'TIMEOUT'; break
                    for key, events in selector.select(min(0.1, max(0, deadline - time.monotonic()))):
                        if key.data == 'stdin':
                            try:
                                offset += os.write(key.fileobj.fileno(), payload[offset:])
                            except BrokenPipeError:
                                offset = len(payload)
                            if offset == len(payload):
                                selector.unregister(key.fileobj); key.fileobj.close()
                        else:
                            part = os.read(key.fileobj.fileno(), 16384)
                            if not part:
                                selector.unregister(key.fileobj); key.fileobj.close()
                            else:
                                available = OUTPUT_LIMIT - sum(len(x) for x in output.values())
                                output[key.data].extend(part[:available])
                                if len(part) > available:
                                    status = 'OUTPUT_LIMIT'; break
                    if status:
                        break
            finally:
                if status is None and process.poll() is None:
                    try:
                        process.wait(timeout=max(0.01, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        status = 'TIMEOUT'
                if status is not None and process.poll() is None:
                    process.kill()
                process.wait(timeout=3)
                selector.close()
                for pipe in (process.stdin, process.stdout, process.stderr):
                    if not pipe.closed: pipe.close()
            return {'status': status or ('OK' if process.returncode == 0 else 'PROCESS_ERROR'),
                    'returncode': process.returncode, 'stdout': output['stdout'].decode('utf-8', errors='replace'),
                    'stderr': output['stderr'].decode('utf-8', errors='replace'),
                    'duration_ms': round((time.monotonic() - started) * 1000, 2),
                    'isolation_receipt': {key: receipt[key] for key in ('profile', 'runner_id', 'rootfs_id',
                        'bwrap_sha256', 'seccomp_sha256', 'kernel', 'limits')}}


PROBE = '''import os,json,socket,ctypes,errno,resource
def denied(action):
    try: action(); return False
    except OSError as e: return e.errno in (errno.EPERM,errno.EACCES,errno.EROFS,errno.ENOENT)
status=dict(line.strip().split(':',1) for line in open('/proc/self/status') if ':' in line)
lib=ctypes.CDLL(None,use_errno=True)
checks={'no_host_home':not os.path.exists('/home/tingfeng'),
 'no_windows_mount':not os.path.exists('/mnt/e'), 'no_gpu':not any(os.path.exists(p) for p in ('/dev/dxg','/dev/dri')),
 'no_host_pid_root':not os.path.exists('/proc/1/root/mnt/e'),
 'empty_routes':len(open('/proc/net/route').read().splitlines())<=1,
 'capabilities_dropped':int(status['CapEff'].strip(),16)==0,
 'no_new_privileges':status['NoNewPrivs'].strip()=='1',
 'seccomp_active':status['Seccomp'].strip()=='2',
 'socket_denied':denied(lambda:socket.socket()),
 'fork_denied':denied(lambda:os.fork()),
 'input_readonly':denied(lambda:open('/work/tool.py','w')),
 'device_directory_readonly':denied(lambda:open('/dev/probe-regular-file','wb')),
 'shared_memory_readonly_or_absent':not os.path.exists('/dev/shm') or denied(lambda:open('/dev/shm/probe-regular-file','wb')),
 'runtime_readonly':os.path.isfile('/usr/lib/python3.12/os.py') and denied(lambda:open('/usr/lib/python3.12/os.py','ab')),
 'root_mount_readonly':any(line.split()[4]=='/' and 'ro' in line.split()[5].split(',') for line in open('/proc/self/mountinfo')),
 'env_scrubbed':all(x not in os.environ for x in ('WSL_INTEROP','WSLENV','HTTP_PROXY','HTTPS_PROXY','OLLAMA_HOST')),
 'fd_scope':set(os.listdir('/proc/self/fd')).issubset({'0','1','2','3'})}
r=lib.unshare(0x10000000); checks['namespace_creation_denied']=r==-1 and ctypes.get_errno()==errno.EPERM
try: allocation=bytearray(300*1024*1024); checks['memory_limited']=False
except MemoryError: checks['memory_limited']=True
with open('/tmp/probe.txt','w') as f:f.write('scratch')
checks['private_scratch_available']=True
scratch=os.statvfs('/tmp'); checks['scratch_size_limited']=scratch.f_blocks*scratch.f_frsize<=16*1024*1024
print(json.dumps({'checks':checks,'namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('user','mnt','pid','net','ipc','uts')},'root_entries':os.listdir('/'),'pid':os.getpid()}))
'''


def probe(runner_id):
    receipt = verify_prepared(runner_id, False)
    # A failed or interrupted re-probe must not leave an older green gate usable.
    receipt['ready'] = False
    atomic_json(BASE / 'probe-receipt.json', receipt)
    basic = execute('# trusted inert probe input\n', PROBE, {}, 5, receipt)
    observations = json.loads(basic['stdout']) if basic['status'] == 'OK' else {}
    outer = {n: os.readlink('/proc/self/ns/' + n) for n in ('user','mnt','pid','net','ipc','uts')}
    checks = observations.get('checks', {})
    checks['namespace_ids_distinct'] = (set(observations.get('namespaces', {})) == set(outer)
        and all(outer[n] != observations['namespaces'][n] for n in outer))
    output = execute('', "import os\nwhile True: os.write(1,b'x'*16384)\n", {}, 5, receipt)
    checks['output_bounded'] = output['status'] == 'OUTPUT_LIMIT' and len(output['stdout'].encode()) <= OUTPUT_LIMIT
    cpu = execute('', 'while True: pass\n', {}, 8, receipt)
    checks['cpu_limited'] = cpu['status'] == 'PROCESS_ERROR' and cpu['returncode'] != 0 and cpu['duration_ms'] < 6500
    wall = execute('', 'import time\ntime.sleep(5)\n', {}, 0.3, receipt)
    checks['wall_time_limited'] = wall['status'] == 'TIMEOUT' and wall['duration_ms'] < 2000
    receipt.update(ready=(basic['status'] == 'OK' and REQUIRED_CHECKS.issubset(checks)
                         and all(value is True for value in checks.values())), candidate_executed=False,
        probed_at_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        checks=checks, namespace_observation=observations, initial_namespace_ids=outer,
        probe_processes={'basic': {k:v for k,v in basic.items() if k!='stdout'},
                         'cpu': {k:v for k,v in cpu.items() if k!='stdout'},
                         'wall': {k:v for k,v in wall.items() if k!='stdout'}})
    atomic_json(BASE / 'probe-receipt.json', receipt)
    return receipt


def handle(request, runner_id):
    try:
        operation = request.get('operation')
        if operation == 'prepare': return prepare(runner_id)
        if operation == 'probe': return probe(runner_id)
        if operation == 'run':
            receipt = verify_prepared(runner_id)
            return execute(request['candidate_code'], request['harness_code'], request['input_data'],
                           float(request.get('timeout_seconds', 10)), receipt)
        raise ValueError('Unsupported isolation operation')
    except Exception as error:
        # Do not expose code, stdin or environment in infrastructure errors.
        return {'status': 'ISOLATION_ERROR', 'returncode': None, 'stdout': '', 'stderr': '',
                'error_type': type(error).__name__, 'reason': str(error) if request.get('operation') in ('prepare','probe') else 'isolation_unavailable',
                'duration_ms': 0, 'isolation_receipt': None}
