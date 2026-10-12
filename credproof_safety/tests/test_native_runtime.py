"""Native Linux execution backend: same bubblewrap profile, no wsl.exe prefix."""
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest import mock

from credproof_safety import runner


class NativeRuntimeTests(unittest.TestCase):
    def test_linux_host_uses_no_wsl_prefix_and_expands_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "runtime.json"
            config.write_text(json.dumps({"runtime_root": "~/credproof-agent-runtime"}), encoding="utf-8")
            # A Windows test host cannot emulate POSIX expanduser by changing
            # HOME alone (ntpath uses USERPROFILE). Mock only that host service.
            expanded = "/home/bench/credproof-agent-runtime"
            with mock.patch.dict(os.environ, {"CREDPROOF_CONFIG": str(config)}), \
                    mock.patch.object(runner, "_native", return_value=True), \
                    mock.patch.object(runner.os.path, "expanduser", return_value=expanded) as expand:
                prefix, paths = runner._runtime_settings()
                expand.assert_called_once_with("~/credproof-agent-runtime")
        self.assertEqual(prefix, [])
        self.assertEqual(paths["root"], expanded)
        self.assertEqual(paths["bubblewrap"], expanded + "/isolation/tools/usr/bin/bwrap")
        self.assertTrue(all(value == expanded or value.startswith(expanded + "/") for value in paths.values()))

    def test_linux_host_mounts_posix_paths_directly(self):
        source = mock.Mock()
        source.resolve.return_value = PurePosixPath("/var/tmp/y")
        with mock.patch.object(runner, "_native", return_value=True):
            self.assertEqual(runner._wsl_path(source), "/var/tmp/y")
        source.resolve.assert_called_once_with()

    def test_windows_host_keeps_wsl_bridge(self):
        with mock.patch.object(runner, "_native", return_value=False), \
                mock.patch.object(runner, "execution_runtime_paths", return_value={"root": "/home/u/r"}), \
                mock.patch.object(runner, "load_runtime_config",
                                  return_value={"wsl_distribution": "Ubuntu-24.04", "wsl_user": "", "runtime_root": "~/r"}):
            prefix, paths = runner._runtime_settings()
        self.assertEqual(prefix, ["wsl.exe", "-d", "Ubuntu-24.04", "--exec"])
        self.assertEqual(paths, {"root": "/home/u/r"})


if __name__ == "__main__":
    unittest.main()
