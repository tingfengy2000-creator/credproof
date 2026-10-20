"""Find printed page numbers of each heading in the rendered PDF (footer numbering starts at the TOC page)."""
import json, re, subprocess, sys
pdf, heads_file, out = sys.argv[1:4]
heads = json.load(open(heads_file))
txt = subprocess.run(['pdftotext', pdf, '-'], capture_output=True, text=True).stdout.split('\f')
norm = lambda s: re.sub(r'\s', '', s)
pages = [norm(p) for p in txt]
res, start = [], 2  # physical page index (0-based) where body begins after cover+toc search
for h in heads:
    key = norm(h['text'])
    found = None
    for i in range(start, len(pages)):
        # heading lines at top of page or anywhere; require exact text
        if key in pages[i]:
            found = i; break
    assert found is not None, h
    res.append(found + 1)
    start = found
json.dump(res, open(out, 'w'))
print(res)
