#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
python3 -S -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else "Python 3.11+ required")'
exec python3 -S -m agent_pilot.launch --demo --mode view --auto-port --open-browser "$@"
