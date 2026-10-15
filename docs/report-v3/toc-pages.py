"""Read heading page numbers from a rendered PDF (pdftotext) for the static TOC."""
import json, re, subprocess, sys
from pathlib import Path
pdf, manuscript, out = sys.argv[1:4]
text = Path(manuscript).read_text(encoding="utf-8")
body = text.split("## 摘要\n", 1)[1]
heads = ["摘要"] + [l[3:].strip() if l.startswith("## ") else l[4:].strip() for l in body.splitlines() if l.startswith(("## ", "### "))]
pages = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout.split("\f")
norm = lambda s: re.sub(r"\s+", "", s)
found, start = {}, 4  # body starts after cover, instructions and TOC
for h in heads:
    for n in range(start, len(pages) + 1):
        if any(norm(line) == norm(h) for line in pages[n - 1].splitlines()):
            found[h] = n; start = n; break
missing = [h for h in heads if h not in found]
Path(out).write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(found), "found; missing:", missing)
