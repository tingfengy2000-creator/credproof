"""Operator-selected, pinned model identities. No fallback, template override or download."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

PROFILES = {
    'qwen3': {'name': 'qwen3-coder:30b',
              'manifest': 'models/manifests/registry.ollama.ai/library/qwen3-coder/30b',
              'digest': '06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca'},
    'qwen25': {'name': 'qwen2.5-coder:32b-instruct-q4_K_M',
               'manifest': 'models/manifests/registry.ollama.ai/library/qwen2.5-coder/32b-instruct-q4_K_M',
               'digest': 'b92d6a0bd47ee79114298de0177bf920c05a706d12633950b3936778492bef41'},
}
LIMITS = {'preflights': 1, 'formal_tasks': 1, 'environment_repairs': 1,
          'generations': 3, 'model_requests': 4, 'format_corrections': 1,
          'candidates': 3, 'program_verifications': 3, 'context': 16384,
          'output': 2048, 'safety_reserve': 512, 'request_seconds': 120, 'task_seconds': 900}


def selected_profile():
    key = os.environ.get('CREDPROOF_MODEL_PROFILE', 'qwen3')
    if key not in PROFILES:
        raise ValueError('unknown_model_profile_no_fallback')
    return {'profile': key, **PROFILES[key]}


def verify_profile(profile, runtime):
    if profile != {'profile': profile.get('profile'), **PROFILES.get(profile.get('profile'), {})}:
        raise ValueError('model_profile_identity_mismatch')
    manifest = Path(runtime) / profile['manifest']
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != profile['digest']:
        raise ValueError('pinned_model_manifest_mismatch')
    return manifest


def claim_comparison(kind):
    """Host-only durable claim. A crash consumes the reservation; no restart resets it."""
    profile = selected_profile()
    if profile['profile'] != 'qwen25':
        return None
    if kind not in ('preflight', 'formal', 'environment-repair'):
        raise ValueError('unknown_comparison_action')
    path = Path(os.environ.get('CREDPROOF_MODEL_COMPARISON_LEDGER', ''))
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError('persistent_comparison_ledger_required')
    ledger = json.loads(path.read_text(encoding='utf8'))
    if ledger.get('model') != profile or ledger.get('limits') != LIMITS or ledger.get('task') != 'assistant-original/p01':
        raise ValueError('comparison_registration_mismatch')
    claim = path.with_name(path.stem + '.' + kind + '.claim.json')
    # Exclusive creation is the quota, not a counter in a new run directory.
    with claim.open('x', encoding='utf8') as stream:
        json.dump({'kind': kind, 'registered_round': ledger['round'], 'model': profile,
                   'claimed_at': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid()}, stream, indent=2)
    return claim


def finish_comparison(claim, receipt):
    if claim is not None:
        with claim.with_suffix('.result.json').open('x', encoding='utf8') as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2)
