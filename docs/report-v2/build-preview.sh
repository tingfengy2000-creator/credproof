#!/usr/bin/env bash
# Build DOCX on the official template and a LibreOffice preview PDF with a
# two-pass static table of contents. Needs python-docx 1.2, LibreOffice with
# Python UNO, pdftotext. Final PDF: open the DOCX in Word and export (real 宋体).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; OUT="${1:-$HERE/out}"; PY="${PYTHON:-python3}"
mkdir -p "$OUT"
soffice --headless --invisible --accept="socket,host=127.0.0.1,port=2002;urp;" >/dev/null 2>&1 &
sleep 4
"$PY" "$HERE/build.py" --output "$OUT/pass1.docx" >/dev/null
python3 "$HERE/render-preview.py" "$OUT/pass1.docx" "$OUT/pass1.pdf"
python3 "$HERE/toc-pages.py" "$OUT/pass1.pdf" "$HERE/manuscript.md" "$OUT/toc.json"
"$PY" "$HERE/build.py" --output "$OUT/credproof-report-v2.docx" --toc-pages "$OUT/toc.json"
python3 "$HERE/render-preview.py" "$OUT/credproof-report-v2.docx" "$OUT/credproof-report-v2.pdf"
python3 "$HERE/toc-pages.py" "$OUT/credproof-report-v2.pdf" "$HERE/manuscript.md" "$OUT/toc-check.json"
cmp -s "$OUT/toc.json" "$OUT/toc-check.json" && echo "TOC page numbers verified" || echo "WARNING: TOC drifted; rerun"
rm -f "$OUT/pass1.docx" "$OUT/pass1.pdf"
