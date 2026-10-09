"""Read-only runtime observations. Never prepare, probe, infer or execute a candidate."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import re
import subprocess

REQUIRED_CHECKS = ('no_host_home no_windows_mount no_gpu no_host_pid_root '
    'empty_routes capabilities_dropped no_new_privileges seccomp_active socket_denied '
    'fork_denied input_readonly device_directory_readonly shared_memory_readonly_or_absent '
    'runtime_readonly root_mount_readonly env_scrubbed fd_scope namespace_creation_denied '
    'memory_limited private_scratch_available scratch_size_limited namespace_ids_distinct '
    'output_bounded cpu_limited wall_time_limited').split()


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _inspect_runtime(runtime, runner_id, required_checks):
    """Read existing files only; small blobs are hashed, large weights size-checked."""
    runtime = Path(runtime).expanduser().absolute()
    reasons, model_reasons, checks = [], [], {}
    isolation = runtime / 'isolation'
    try:
        if any(p.is_symlink() for p in (isolation, *isolation.parents)):
            raise ValueError('linked_runtime')
        receipt_path = isolation / 'probe-receipt.json'
        if receipt_path.stat().st_size > 1024 * 1024:
            raise ValueError('oversized_receipt')
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        checks['saved_probe_ready'] = receipt.get('ready') is True
        checks['runner_identity'] = receipt.get('runner_id') == runner_id
        checks['kernel_identity'] = receipt.get('kernel') == platform.release()
        checks['mandatory_saved_checks'] = all(receipt.get('checks', {}).get(k) is True for k in required_checks)
        for field, relative in [('bwrap_sha256', 'tools/usr/bin/bwrap'), ('seccomp_sha256', 'seccomp.bpf')]:
            path = isolation / relative
            checks[field] = path.is_file() and not path.is_symlink() and _file_hash(path) == receipt.get(field)
        rootfs = isolation / 'rootfs'
        files = {}
        if not rootfs.is_dir() or rootfs.is_symlink():
            raise ValueError('rootfs_unavailable')
        for path in sorted(rootfs.rglob('*')):
            if path.is_symlink():
                raise ValueError('linked_rootfs')
            if path.is_file():
                files[path.relative_to(rootfs).as_posix()] = _file_hash(path)
        tree_hash = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        checks['rootfs_identity'] = bool(files) and tree_hash == receipt.get('rootfs_id')
        reasons.extend('isolation_' + name + '_failed' for name, ok in checks.items() if not ok)
    except (OSError, ValueError, TypeError, AttributeError):
        reasons.append('isolation_material_unavailable')
    model_info = {'manifest_sha256': None, 'blob_count': 0, 'warnings': [], 'blob_checks': [],
                  'full_weight_rehashed': False,
                  'blob_verification': 'full SHA256 for blobs up to 16 MiB; larger weights existence and declared size only; no inference'}
    for name in ('venv/bin/python', 'ollama/bin/ollama'):
        path = runtime / name
        if not path.is_file() or not os.access(path, os.X_OK):
            model_reasons.append('model_runtime_executable_missing')
    try:
        manifest_path = runtime / 'models/manifests/registry.ollama.ai/library/qwen3-coder/30b'
        if manifest_path.stat().st_size > 1024 * 1024:
            raise ValueError('oversized_manifest')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        model_info['manifest_sha256'] = _file_hash(manifest_path)
        descriptors = [manifest['config'], *manifest['layers']]
        if not descriptors or not manifest['layers']:
            raise ValueError('empty_model')
        for item in descriptors:
            digest, size = item['digest'], item['size']
            if (not isinstance(digest, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest)
                    or type(size) is not int or size < 0):
                raise ValueError('invalid_blob_descriptor')
            path = runtime / 'models/blobs' / digest.replace(':', '-')
            if not path.is_file():
                raise ValueError('blob_missing')
            actual_size = path.stat().st_size
            item_check = {'digest': digest, 'declared_size': size, 'actual_size': actual_size,
                          'sha256_verified': False}
            if actual_size <= 16 * 1024 * 1024:
                if _file_hash(path) != digest.split(':', 1)[1]:
                    raise ValueError('small_blob_checksum_mismatch')
                item_check['sha256_verified'] = True
                if actual_size != size:
                    model_info['warnings'].append({'code': 'SMALL_BLOB_SIZE_METADATA_MISMATCH', **item_check})
            elif actual_size != size:
                raise ValueError('large_blob_size_mismatch')
            model_info['blob_checks'].append(item_check)
        model_info['blob_count'] = len(descriptors)
    except (OSError, ValueError, TypeError, KeyError):
        model_reasons.append('model_manifest_or_blobs_unavailable')
    isolation_ready, model_ready = not reasons, not model_reasons
    return {'ready': isolation_ready and model_ready, 'isolation_ready': isolation_ready,
            'model_ready': model_ready, 'runtime_root': str(runtime),
            'reasons': sorted(set(reasons + model_reasons)),
            'isolation': {'ready': isolation_ready, 'checks': checks, 'reasons': sorted(set(reasons))},
            'model_files': {'ready': model_ready, **model_info, 'reasons': sorted(set(model_reasons))},
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'model_label': 'qwen3-coder:30b · 本地服务',
            'observation_scope': 'Read-only saved probe/hash and model-file observation; no fresh boundary probe, model inference or candidate execution',
            'model_executed': False, 'candidate_executed': False, 'network_probe_performed': False}


def observe(root=None, config=None):
    from .runtime_config import load_config, linux_runtime_root, wsl_prefix
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    try:
        config = config if config is not None else load_config(root)
        # Program identity comes from the installation, not the data workspace.
        identity = _file_hash(Path(__file__).resolve().with_name('sandbox_runner.py'))
        if os.name != 'nt':
            return _inspect_runtime(linux_runtime_root(config), identity, REQUIRED_CHECKS)
        # Only these trusted read-only functions travel to WSL, never candidate text.
        script = ('from datetime import datetime,timezone\nimport hashlib,json,os,pathlib,platform,re,sys\n'
                  'from pathlib import Path\n' + inspect.getsource(_file_hash) + '\n'
                  + inspect.getsource(_inspect_runtime) + '\n'
                  + 'p=json.load(sys.stdin)\nprint(json.dumps(_inspect_runtime(p["runtime_root"],p["runner_id"],p["required_checks"])))\n')
        result = subprocess.run([*wsl_prefix(config), '--exec', 'python3', '-I', '-c', script],
            input=json.dumps({'runtime_root': config['runtime_root'], 'runner_id': identity,
                             'required_checks': REQUIRED_CHECKS}).encode('utf-8'),
            capture_output=True, timeout=45)
        if result.returncode:
            raise ValueError('WSL read-only observation failed')
        data = json.loads(result.stdout)
        if not isinstance(data.get('runtime_root'), str) or not data['runtime_root'].startswith('/'):
            raise ValueError('Linux absolute runtime path unavailable')
        return data
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        return {'ready': False, 'isolation_ready': False, 'model_ready': False, 'runtime_root': None,
                'reasons': ['runtime_configuration_or_observation_unavailable'],
                'observed_at': datetime.now(timezone.utc).isoformat(),
                'model_executed': False, 'candidate_executed': False, 'network_probe_performed': False,
                'observation_scope': 'Read-only observation unavailable; no readiness inferred'}


def main():
    result = observe()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
