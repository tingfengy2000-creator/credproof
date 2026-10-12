"""Preview render: open the DOCX in headless LibreOffice, refresh the TOC and
page fields, export PDF. Final submission PDF should still be exported from
Word on Windows (real 宋体 metrics). Usage:

    soffice --headless --accept="socket,host=127.0.0.1,port=2002;urp;" &
    python3 docs/report-v2/render-preview.py in.docx out.pdf
"""
import sys
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main(src, dst):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(40):
        try:
            ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
            break
        except Exception:
            time.sleep(0.5)
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL(Path(src).resolve().as_uri(), "_blank", 0, (prop("Hidden", True),))
    indexes = doc.getDocumentIndexes()
    for _ in range(2):  # second pass picks up page numbers shifted by the TOC itself
        for i in range(indexes.getCount()):
            indexes.getByIndex(i).update()
        doc.getTextFields().refresh()
    doc.storeToURL(Path(dst).resolve().as_uri(), (prop("FilterName", "writer_pdf_Export"),))
    doc.close(True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
