#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="$HERE/out"; mkdir -p "$OUT"
(soffice --headless --invisible --accept="socket,host=127.0.0.1,port=2002;urp;" >/dev/null 2>&1 &) ; sleep 5
python3 "$HERE/build.py" --output "$OUT/pass1.docx" >/dev/null
python3 "$HERE/render-preview.py" "$OUT/pass1.docx" "$OUT/pass1.pdf"
python3 "$HERE/toc-pages.py" "$OUT/pass1.pdf" "$HERE/manuscript.md" "$OUT/toc.json"
python3 "$HERE/build.py" --output "$OUT/credproof-report.docx" --toc-pages "$OUT/toc.json"
python3 "$HERE/render-preview.py" "$OUT/credproof-report.docx" "$OUT/credproof-report.pdf"
python3 "$HERE/toc-pages.py" "$OUT/credproof-report.pdf" "$HERE/manuscript.md" "$OUT/toc-check.json"
cmp -s "$OUT/toc.json" "$OUT/toc-check.json" && echo "TOC verified" || echo "WARNING: TOC drifted"
