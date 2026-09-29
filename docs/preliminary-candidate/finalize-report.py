"""Remove application-added identity metadata and render the exported report.

Run after build-report.py and export-report.ps1. Requires pypdf, pypdfium2,
Pillow. This only edits the generated DOCX/PDF; it never changes the reference.
PNG production is not visual approval. Inspect every page before delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
import pypdfium2 as pdfium

HERE = Path(__file__).resolve().parent


def scrub_docx(path):
    temporary = path.with_suffix('.scrub.docx')
    with ZipFile(path) as src, ZipFile(temporary, 'w') as dst:
        for entry in src.infolist():
            if entry.filename == 'docProps/custom.xml':
                continue
            data = src.read(entry.filename)
            if entry.filename in ('docProps/core.xml', 'docProps/app.xml',
                                  '_rels/.rels', '[Content_Types].xml'):
                root = etree.fromstring(data)
                for child in list(root):
                    local = etree.QName(child).localname
                    if local in ('creator', 'lastModifiedBy', 'Company', 'Manager'):
                        root.remove(child)
                    elif local == 'Relationship' and child.get('Type', '').endswith('/custom-properties'):
                        root.remove(child)
                    elif local == 'Override' and child.get('PartName') == '/docProps/custom.xml':
                        root.remove(child)
                    elif local == 'Application':
                        child.text = 'WPS Office'
                data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            dst.writestr(entry, data)
    temporary.replace(path)


def finalize(args):
    scrub_docx(args.docx)
    reader = PdfReader(args.pdf)
    original_text = [p.extract_text() for p in reader.pages]
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    metadata = dict(reader.metadata or {})
    for key in ('/Author', '/Company', '/Comments', '/SourceModified'):
        metadata.pop(key, None)
    writer.metadata = metadata
    # Some renderers also include XMP author metadata independently of Info.
    writer.root_object.pop(NameObject('/Metadata'), None)
    temporary = args.pdf.with_suffix('.scrub.pdf')
    with temporary.open('wb') as stream:
        writer.write(stream)
    temporary.replace(args.pdf)
    checked = PdfReader(args.pdf)
    assert [p.extract_text() for p in checked.pages] == original_text
    assert not checked.metadata.get('/Author')
    args.render_dir.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(args.pdf)
    thumbs = []
    for index in range(len(document)):
        page = document[index]
        bitmap = page.render(scale=1.5)
        img = bitmap.to_pil().convert('RGB')
        img.save(args.render_dir / f'page-{index + 1:02d}.png')
        thumb = img.copy()
        thumb.thumbnail((300, 425))
        thumbs.append(thumb)
        bitmap.close()
        page.close()
    document.close()
    contact = Image.new('RGB', (300 * 5, 455 * ((len(thumbs) + 4) // 5)), 'white')
    draw = ImageDraw.Draw(contact)
    for index, thumb in enumerate(thumbs):
        x, y = index % 5 * 300, index // 5 * 455
        contact.paste(thumb, (x, y + 22))
        draw.text((x + 8, y + 3), f'Page {index + 1}', fill='black')
    contact.save(args.render_dir / 'contact.png')
    receipt = {
        'docx': str(args.docx), 'pdf': str(args.pdf),
        'pages': len(checked.pages), 'pdf_bytes': args.pdf.stat().st_size,
        'docx_sha256': hashlib.sha256(args.docx.read_bytes()).hexdigest(),
        'pdf_sha256': hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        'metadata_author_removed': True,
        'text_unchanged_after_metadata_scrub': True,
        'render_engine': 'WPS Office export + pypdfium2 PNG',
        'render_dir': str(args.render_dir),
        'visual_review_completed': False,
        'note': 'Inspect every rendered page; rendering alone is not visual QA.',
    }
    (HERE / 'working/finalization-receipt.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--docx', type=Path, default=HERE / 'credproof-manuscript-candidate.docx')
    parser.add_argument('--pdf', type=Path, default=HERE / 'credproof-manuscript-candidate.pdf')
    parser.add_argument('--render-dir', type=Path, default=HERE / 'working/render-final')
    finalize(parser.parse_args())
