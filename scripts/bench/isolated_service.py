"""WSL supervisor for bench-v1 transport; no prompts, inference or candidate execution.

Same GPU/rootfs/namespace profile as credproof_safety.agent's reviewed model
supervisor, limited to the two pinned models. Not the benchmark protocol.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    runtime, stage, output, rpc, sentinel = map(Path, sys.argv[1:6])
    expected = {'isolated_worker.py', 'registration.json'}
    if {p.name for p in stage.iterdir()} != expected or any(p.is_symlink() for p in stage.iterdir()):
        raise SystemExit('unexpected model stage')
    registration = json.loads((stage/'registration.json').read_text())
    files = {}
    for profile in registration['models']:
        manifest = runtime/profile['manifest']
        if hashlib.sha256(manifest.read_bytes()).hexdigest() != profile['digest']:
            raise SystemExit('pinned model manifest changed')
        data = json.loads(manifest.read_bytes())
        files[manifest] = str(manifest.relative_to(runtime))
        for item in [data['config'], *data['layers']]:
            digest = item['digest']
            if len(digest) != 71 or not digest.startswith('sha256:'):
                raise SystemExit('invalid model blob identity')
            blob = runtime/'models/blobs'/digest.replace(':', '-')
            if blob.is_symlink() or not blob.is_file():
                raise SystemExit('missing model blob')
            files[blob] = str(blob.relative_to(runtime))
    rootfs = runtime/'isolation/rootfs'
    bwrap = runtime/'isolation/tools/usr/bin/bwrap'
    ollama = runtime/'ollama'
    with tempfile.TemporaryDirectory(prefix='credproof-bench-model-root-') as tmp:
        root = Path(tmp)
        shutil.copytree(rootfs, root, symlinks=True, dirs_exist_ok=True)
        for name in ('libgcc_s.so.1', 'libstdc++.so.6', 'libpthread.so.0', 'libdl.so.2',
                     'libresolv.so.2', 'librt.so.1', 'libmvec.so.1'):
            shutil.copyfile('/lib/x86_64-linux-gnu/'+name, root/'lib/x86_64-linux-gnu'/name)
        (root/'usr/lib/wsl/lib').mkdir(parents=True, exist_ok=True)
        (root/'usr/lib/wsl/drivers').mkdir(parents=True, exist_ok=True)
        work = output/'model-work'
        work.mkdir(exist_ok=False)
        (work/'escape-host-sentinel').symlink_to(sentinel)
        args = [str(bwrap), '--unshare-all', '--unshare-user', '--unshare-cgroup-try', '--disable-userns',
                '--die-with-parent', '--new-session', '--clearenv', '--cap-drop', 'ALL', '--tmpfs', '/',
                '--ro-bind', str(root/'usr'), '/usr', '--ro-bind', str(root/'lib'), '/lib',
                '--ro-bind', str(root/'lib64'), '/lib64',
                '--ro-bind', '/usr/lib/wsl/lib', '/usr/lib/wsl/lib',
                '--ro-bind', '/usr/lib/wsl/drivers', '/usr/lib/wsl/drivers',
                '--dir', '/app', '--ro-bind', str(stage), '/app',
                '--dir', '/runtime', '--ro-bind', str(ollama), '/runtime/ollama',
                '--dir', '/runtime/models', '--dir', '/runtime/models/manifests',
                '--dir', '/runtime/models/manifests/registry.ollama.ai',
                '--dir', '/runtime/models/manifests/registry.ollama.ai/library', '--dir', '/runtime/models/blobs']
        for source, relative in files.items():
            args += ['--ro-bind', str(source), '/runtime/'+relative]
        args += ['--dir', '/gpu-libs', '--ro-bind', '/usr/lib/wsl/lib', '/gpu-libs',
                 '--dev', '/dev', '--dev-bind', '/dev/dxg', '/dev/dxg', '--proc', '/proc',
                 '--tmpfs', '/tmp', '--tmpfs', '/run', '--tmpfs', '/home',
                 '--bind', str(work), '/work', '--bind', str(rpc), '/rpc', '--chdir', '/work']
        environment = {
            'PATH': '/usr/bin:/bin:/usr/lib/wsl/lib', 'HOME': '/home/model', 'LANG': 'C.UTF-8',
            'OLLAMA_HOST': '127.0.0.1:11435', 'OLLAMA_MODELS': '/runtime/models', 'OLLAMA_NO_CLOUD': '1',
            'OLLAMA_LLM_LIBRARY': 'cuda_v12', 'OLLAMA_CONTEXT_LENGTH': '16384',
            'OLLAMA_NUM_PARALLEL': '1', 'OLLAMA_MAX_LOADED_MODELS': '1', 'OLLAMA_KEEP_ALIVE': '-1',
            'OLLAMA_FLASH_ATTENTION': '1', 'OLLAMA_KV_CACHE_TYPE': 'q8_0',
            'LD_LIBRARY_PATH': '/gpu-libs:/runtime/ollama/lib/ollama:/runtime/ollama/lib/ollama/cuda_v12:/runtime/ollama/lib/ollama/cuda_v13',
            'HTTP_PROXY': '', 'HTTPS_PROXY': '', 'ALL_PROXY': '', 'NO_PROXY': '127.0.0.1,localhost',
            'CREDPROOF_HOST_SENTINEL': str(sentinel)}
        for key, value in environment.items():
            args += ['--setenv', key, value]
        args += ['--remount-ro', '/', '/usr/bin/python3', '-I', '/app/isolated_worker.py']
        plan = {'kind': 'BENCH_V1_MODEL_TRANSPORT_BOUNDARY', 'models': registration['models'],
                'model_files': [{'path': rel, 'bytes': p.stat().st_size} for p, rel in files.items()],
                'stage': sorted(expected), 'environment': environment,
                'writable': ['/work', '/rpc', '/tmp', '/run', '/home'],
                'network': 'unshare-all; private loopback, no host/proxy connection',
                'excludes': ['mounted checkout', 'mounted candidate/reference project directories', 'host home', 'other model weights'],
                'supervisor_timeout_seconds': registration['supervisor_timeout_seconds']}
        (output/'boundary-plan.json').write_text(json.dumps(plan, indent=1)+'\n')
        with (output/'boundary-stdout.txt').open('wb') as out, (output/'boundary-stderr.txt').open('wb') as err:
            p = subprocess.Popen(args, stdout=out, stderr=err)
            try:
                code = p.wait(timeout=registration['supervisor_timeout_seconds'])
            finally:
                if p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        p.kill(); p.wait()
        raise SystemExit(code)


if __name__ == '__main__':
    main()
