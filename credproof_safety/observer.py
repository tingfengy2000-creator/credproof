from __future__ import annotations

import json
from pathlib import Path
import time


class Observation:
    """Independent runtime observations for supported Python APIs.

    The audit hook covers Python's open/socket audit events. It is intentionally
    reported as a supported observation surface, not as a universal syscall
    monitor; native extensions and unsupported operating-system behaviours are
    outside this first profile.
    """

    def __init__(self, allowed_roots: list[str], forbidden_roots: list[str]):
        self.started = time.monotonic()
        self.allowed_roots = [str(Path(x).resolve()) for x in allowed_roots]
        self.forbidden_roots = [str(Path(x).resolve()) for x in forbidden_roots]
        self.events: list[dict] = []
        self.enabled = False

    def install(self) -> None:
        import sys
        if self.enabled:
            return
        sys.addaudithook(self._audit)
        self.enabled = True

    def _inside(self, path: str, roots: list[str]) -> bool:
        try:
            target = str(Path(path).resolve())
        except (OSError, ValueError):
            target = str(path)
        return any(target == root or target.startswith(root + str(Path('/').anchor or '/'))
                   or target.startswith(root + "/") for root in roots)

    def _audit(self, event: str, args: tuple) -> None:
        if event == "open" and args:
            raw = args[0]
            if isinstance(raw, (str, bytes)):
                path = os_path(raw)
                classification = "forbidden" if self._inside(path, self.forbidden_roots) else (
                    "allowed" if self._inside(path, self.allowed_roots) else "other")
                self.events.append({"event": "open", "path": path, "classification": classification,
                                    "mode": str(args[1]) if len(args) > 1 else ""})
        elif event == "socket.connect" and len(args) > 1:
            address = args[1]
            self.events.append({"event": "socket.connect", "address": repr(address)})

    def report(self) -> dict:
        forbidden = [e for e in self.events if e.get("classification") == "forbidden"]
        return {"events": self.events, "forbidden_reads": forbidden,
                "supported_observation": ["Python audit open events", "Python socket.connect events"],
                "uncovered": ["native-extension direct syscalls", "TOCTOU races", "Windows kernel audit"],
                "duration_ms": round((time.monotonic() - self.started) * 1000, 2)}


def os_path(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
