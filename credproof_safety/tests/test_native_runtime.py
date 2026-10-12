"""Native Linux execution backend: same bubblewrap profile, no wsl.exe prefix."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from credproof_safety import runner


class NativeRuntimeTests(unittest.TestCase):
    def test_linux_host_uses_no_wsl_prefix_and_expands_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "runtime.json"
            config.write_text(json.dumps({"runtime_root": "~/credproof-agent-runtime"}), encoding="utf-8")
            with mock.patch.dict(os.environ, {"CREDPROOF_CONFIG": str(config), "HOME": tmp}), \
                    mock.patch.object(runner, "_native", return_value=True):
                prefix, paths = runner._runtime_settings()
        self.assertEqual(prefix, [])
        self.assertEqual(paths["root"], tmp + "/credproof-agent-runtime")
        self.assertEqual(paths["bubblewrap"], tmp + "/credproof-agent-runtime/isolation/tools/usr/bin/bwrap")
        self.assertTrue(all(value.startswith(tmp + "/") for value in paths.values()))

    def test_linux_host_mounts_posix_paths_directly(self):
        with mock.patch.object(runner, "_native", return_value=True):
            self.assertEqual(runner._wsl_path(Path("/var/tmp/x/../y")), "/var/tmp/y")

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
