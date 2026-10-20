"""Serve editable UI against a temporary, read-only copy of disclosed history.

No model, candidate execution, decisions or exports are available. The status
GET may probe the operator-configured runtime's material availability only.
Use the frozen installed wheel; only UI assets come from the frontend checkout.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.parse import urlsplit

from agent_pilot.web import Application, Handler, Problem, Server


REPOSITORY = Path(__file__).resolve().parents[2]
SNAPSHOT = REPOSITORY / 'docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace'


class ReadOnlyHandler(Handler):
    def route(self):
        self.boundary()
        path = urlsplit(self.path).path
        allowed = path in ('/', '/index.html', '/styles.css', '/app.js',
                           '/api/agent/bootstrap', '/api/agent/health', '/api/project/modes', '/api/bench',
                           '/api/integration', '/api/compare', '/api/workspace/status', '/api/reviews', '/api/intake', '/api/intake/examples')
        allowed = allowed or bool(re.fullmatch(r'/api/review/[0-9a-f]{32}', path))
        allowed = allowed or bool(re.fullmatch(r'/api/bench/patches/[A-Za-z0-9_.:-]{1,160}', path))
        if self.command != 'GET' or not allowed:
            raise Problem(405, 'READ_ONLY_HISTORY: no write, inference, check, decision or export')
        return super().route()


class ReadOnlyApplication(Application):
    def bootstrap(self):
        data = super().bootstrap()
        data['read_only_entry'] = {
            'mode': 'READ_ONLY_HISTORY', 'read_only': True,
            'new_model_calls': 0, 'candidate_execution_enabled': False,
            'decision_writes_enabled': False, 'exports_enabled': False,
            'notice': '历史脱敏材料；不是本机新验收，只读入口不会产生真实审批或安全证据。',
        }
        return data


class ReadOnlyServer(Server):
    def __init__(self, address, application):
        super().__init__(address, application)
        self.RequestHandlerClass = ReadOnlyHandler


@contextmanager
def prepared_view(snapshot=SNAPSHOT, ui=REPOSITORY/'agent_pilot/ui', bench_results=None):
    """Validate disclosed files, copy to disposable data, never import project code."""
    snapshot, ui = Path(snapshot).resolve(strict=True), Path(ui).resolve(strict=True)
    manifest = json.loads((snapshot/'snapshot-manifest.json').read_text(encoding='utf8'))
    members = manifest['files']
    if not isinstance(members, dict) or len(members) > 100:
        raise ValueError('unsupported_snapshot')
    content = {}
    for name, expected in members.items():
        rel = PurePosixPath(name)
        source = snapshot/name
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or source.is_symlink():
            raise ValueError('unsafe_snapshot_path')
        if not source.resolve(strict=True).is_relative_to(snapshot) or source.stat().st_size > 4*1024*1024:
            raise ValueError('unsafe_or_oversized_snapshot')
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('snapshot_bytes_changed: '+name)
        content[name] = data
    with tempfile.TemporaryDirectory(prefix='credproof-frontend-readonly-') as temporary:
        root = Path(temporary)
        for name, data in content.items():
            target = root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        target = root/'agent_pilot/ui'
        target.mkdir(parents=True)
        for name in ('index.html', 'app.js', 'styles.css'):
            source = ui/name
            if source.is_symlink() or not source.is_file():
                raise ValueError('missing_or_linked_ui_asset')
            shutil.copyfile(source, target/name)
        # An explicit notice in the served copy; no production UI is rewritten.
        index = target/'index.html'
        notice = '<aside role="status">只读历史查看 / READ_ONLY_HISTORY：材料来自既有真实记录；本入口禁止生成、检查、修改、审批和导出。</aside>'
        index.write_text(index.read_text(encoding='utf8').replace('<body>', '<body>'+notice, 1), encoding='utf8')
        integration = REPOSITORY / 'docs/integration/ci-demo.json'
        # The API reads only these fixed materials from its disposable root.
        # Allowing the route alone does not make repository data available there.
        for name in ('comparison.json', 'onboarding-dotenv.json'):
            source = REPOSITORY/'docs/compare'/name
            if not source.exists():
                continue
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 4*1024*1024:
                raise ValueError('unsafe_or_oversized_comparison_material')
            target = root/'docs/compare'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        yield ReadOnlyApplication(root=root, access_mode='view', bench_results=bench_results,
                                  integration_results=integration if integration.is_file() else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--ui-dir', type=Path, default=REPOSITORY/'agent_pilot/ui')
    parser.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    parser.add_argument('--bench-results', type=Path,
                        help='Operator-selected recorded results; GET only, no inference or execution.')
    args = parser.parse_args()
    with prepared_view(args.snapshot, args.ui_dir, args.bench_results) as app:
        with ReadOnlyServer(('127.0.0.1', args.port), app) as server:
            print(f'READ_ONLY_HISTORY: http://127.0.0.1:{server.server_address[1]}/#human-review', flush=True)
            print('Frozen history only. Runtime status probes materials; no model, candidate execution or writes. Stop with Ctrl+C.', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == '__main__':
    main()
