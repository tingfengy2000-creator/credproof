"""Insert a TOC field with cached entries (page numbers) in place of the placeholder."""
import json, re, sys, zipfile, shutil
from xml.sax.saxutils import escape
src, out, pages = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else None)
heads = json.load(open(src + '.headings.json'))
nums = json.load(open(pages)) if pages else [''] * len(heads)
def r(t): return f'<w:r><w:t xml:space="preserve">{escape(t)}</w:t></w:r>'
parts = []
for k, h in enumerate(heads):
    begin = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\o "1-2" \\h \\z \\u </w:instrText></w:r>'
             '<w:r><w:fldChar w:fldCharType="separate"/></w:r>') if k == 0 else ''
    end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>' if k == len(heads) - 1 else ''
    parts.append(f'<w:p><w:pPr><w:pStyle w:val="TOC{h["level"]}"/></w:pPr>{begin}{r(h["text"])}<w:r><w:tab/></w:r>{r(str(nums[k]))}{end}</w:p>')
zin = zipfile.ZipFile(src)
zout = zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    data = zin.read(item.filename)
    if item.filename == 'word/document.xml':
        xml = data.decode('utf8')
        m = re.search(r'<w:p>(?:(?!<w:p>).)*?@@TOC_ENTRIES@@.*?</w:p>', xml, re.S)
        if not m: m = re.search(r'<w:p\b(?:(?!<w:p\b).)*?@@TOC_ENTRIES@@.*?</w:p>', xml, re.S)
        assert m, 'placeholder'
        xml = xml[:m.start()] + ''.join(parts) + xml[m.end():]
        def fix(m):
            body = m.group(1)
            items = re.findall(r'<w:(top|left|bottom|right|between|bar)\b[^>]*/>', body)
            parts_ = {k: re.search(r'<w:%s\b[^>]*/>' % k, body).group(0) for k in items}
            order = [k for k in ('top', 'left', 'bottom', 'right', 'between', 'bar') if k in parts_]
            return '<w:pBdr>' + ''.join(parts_[k] for k in order) + '</w:pBdr>'
        xml = re.sub(r'<w:pBdr>(.*?)</w:pBdr>', fix, xml)
        data = xml.encode('utf8')
    zout.writestr(item, data)
zout.close()
print('toc entries', len(parts))
