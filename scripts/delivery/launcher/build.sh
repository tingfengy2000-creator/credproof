#!/bin/sh
# Rebuild CredProof.exe (Windows x64 console launcher) from launcher.c on any OS:
#   python -m pip install ziglang && sh build.sh
set -eu
cd "$(dirname "$0")"
python -m ziglang cc -target x86_64-windows-gnu -O2 -municode -s launcher.c launcher.rc -o CredProof.exe
