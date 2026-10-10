"""Clear author/editor metadata after WPS export; leave document content intact."""
import argparse
from pathlib import Path
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pypdf import PdfReader, PdfWriter

p = argparse.ArgumentParser()
p.add_argument('--docx', type=Path, required=True)
p.add_argument('--pdf', type=Path, required=True)
a = p.parse_args()
with zipfile.ZipFile(a.docx) as original:
    entries = [(info, original.read(info.filename)) for info in original.infolist()]
with tempfile.TemporaryDirectory(dir=a.docx.parent) as temporary:
    target = Path(temporary)/a.docx.name
    with zipfile.ZipFile(target, 'w') as result:
        for info, data in entries:
            if info.filename == 'docProps/core.xml':
                root = ET.fromstring(data)
                for tag in ('{http://purl.org/dc/elements/1.1/}creator',
                            '{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy'):
                    element = root.find(tag)
                    if element is not None:
                        element.text = ''
                data = ET.tostring(root, encoding='utf8', xml_declaration=True)
            result.writestr(info, data)
    a.docx.write_bytes(target.read_bytes())
reader = PdfReader(a.pdf)
writer = PdfWriter()
writer.clone_document_from_reader(reader)
writer.add_metadata({'/Author':'', '/Creator':'', '/Producer':'',
                     '/Keywords':'Python工具 AI辅助修复 程序验收 人工采纳'})
with tempfile.TemporaryDirectory(dir=a.pdf.parent) as temporary:
    target = Path(temporary)/a.pdf.name
    writer.write(target)
    a.pdf.write_bytes(target.read_bytes())
print('Author/editor metadata cleared; no page content edited. Render final PDF before delivery.')
