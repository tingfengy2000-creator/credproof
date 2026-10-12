"""Identity protocol tests: byte reads only, no candidate or model execution."""
import importlib.util
import json
from pathlib import Path, PurePosixPath, PureWindowsPath

from credproof_safety.project import _digest_tree


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('derive_public_bundle', ROOT/'scripts/derive-project-public-bundle.py')
deriver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deriver)


class Entry:
    def __init__(self, path, data):
        self.path, self.data = path, data

    def relative_to(self, root):
        return self.path

    def is_file(self):
        return True

    def is_symlink(self):
        return False

    def read_bytes(self):
        return self.data

    def __lt__(self, other):
        return self.path < other.path


class Tree:
    def __init__(self, files, flavour):
        self.entries = [Entry(flavour(name), data) for name, data in files]

    def rglob(self, pattern):
        assert pattern == '*'
        return iter(self.entries)


def test_same_bytes_same_identity_under_windows_and_posix_path_flavours():
    files = [('README.md', b'info'), ('credproof.toml', b'rules'),
             ('tests/test_business.py', b'test'), ('tool.py', b'code')]
    posix, windows = Tree(files, PurePosixPath), Tree(files, PureWindowsPath)
    # Reproduce the underlying old ordering difference rather than pretending
    # the two path flavours compare the same way.
    assert [p.path.name for p in sorted(posix.rglob('*'))] != [p.path.name for p in sorted(windows.rglob('*'))]
    expected = _digest_tree(windows)
    assert _digest_tree(posix) == expected
    assert deriver.digest_tree(posix) == deriver.digest_tree(windows) == expected


def test_formal_snapshot_retains_exact_windows_report_identity():
    folder = ROOT/'docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace/runs/human-review/939e25f42bb142f39567c5cb644ebc6d/versions/v001'
    expected = json.loads((folder/'reports/check-01.json').read_text(encoding='utf8'))['project_tree_sha256']
    assert expected == 'd323b459d2b9907555b71cabebd8297c3aef2c4b74919da9266e16dbfed58a3b'
    assert _digest_tree(folder/'project') == deriver.digest_tree(folder/'project') == expected


def test_case_only_paths_remain_distinct_and_order_does_not_depend_on_enumeration():
    files = [('Foo.py', b'upper'), ('foo.py', b'lower'), ('a-/x.py', b'nested'), ('a.txt', b'flat')]
    expected = _digest_tree(Tree(files, PurePosixPath))
    assert _digest_tree(Tree(list(reversed(files)), PurePosixPath)) == expected
    assert deriver.digest_tree(Tree(list(reversed(files)), PurePosixPath)) == expected
    assert _digest_tree(Tree(files[:1]+files[2:], PurePosixPath)) != expected


def test_exact_bytes_and_case_are_not_normalized(tmp_path):
    file = tmp_path/'Tool.py'
    file.write_bytes(b'line\n')
    first = _digest_tree(tmp_path)
    file.write_bytes(b'line\r\n')
    assert _digest_tree(tmp_path) != first
    file.write_bytes(b'line\n')
    # Model a case-only rename without depending on filesystem rename semantics.
    assert _digest_tree(Tree([('Tool.py', b'line\n')], PurePosixPath)) != _digest_tree(Tree([('tool.py', b'line\n')], PurePosixPath))


def test_existing_ignored_material_remains_outside_identity(tmp_path):
    (tmp_path/'tool.py').write_bytes(b'unchanged')
    before = _digest_tree(tmp_path)
    for name in ('.git', '.venv', '__pycache__', '.credproof'):
        folder = tmp_path/name
        folder.mkdir()
        (folder/'local').write_bytes(b'not part of acceptance')
    assert _digest_tree(tmp_path) == deriver.digest_tree(tmp_path) == before
