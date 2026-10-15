"""Tiny SVG diagram kit for the report figures (consistent style, CJK font)."""
from html import escape as esc

C = dict(navy='#1E4D7A', navyd='#13233A', ink='#17212B', ink2='#4A5866', ink3='#7A8794', rule='#C9D2DA',
         soft='#EEF3F7', soft2='#F6F8F9', white='#FFFFFF', pass_='#2E7A57', passs='#E2F1E9', fail='#B23A2E',
         fails='#F8E5E2', amber='#9A6A0B', ambers='#F6ECD6', violet='#4D5591', violets='#E7E8F4', teal='#1F6F78', teals='#DFF0F1')
FONT = "'Noto Sans CJK SC','Noto Sans SC','Microsoft YaHei',sans-serif"
MONO = "'DejaVu Sans Mono','Noto Sans Mono',monospace"


class Svg:
    def __init__(self, w, h, title=''):
        self.w, self.h, self.parts = w, h, []
        self.title = title

    def add(self, s):
        self.parts.append(s)
        return self

    def text(self, x, y, s, size=15, color=None, weight=400, anchor='start', mono=False, italic=False):
        fam = MONO if mono else FONT
        return self.add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{color or C["ink"]}" '
                        f'font-weight="{weight}" text-anchor="{anchor}"{" font-style=\"italic\"" if italic else ""}>{esc(s)}</text>')

    def lines(self, x, y, rows, size=14, color=None, lh=None, anchor='start', weight=400, mono=False):
        lh = lh or size * 1.45
        for i, r in enumerate(rows):
            self.text(x, y + i * lh, r, size, color, weight, anchor, mono)
        return self

    def rect(self, x, y, w, h, fill=None, stroke=None, r=8, sw=1.4, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        return self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or C["white"]}" '
                        f'stroke="{stroke or C["rule"]}" stroke-width="{sw}"{d}/>')

    def box(self, x, y, w, h, title, rows=(), fill=None, stroke=None, tcolor=None, size=15, rsize=12.5, center=True, r=8, sw=1.4, dash=None, mono_rows=False):
        self.rect(x, y, w, h, fill, stroke, r, sw, dash)
        n = len(rows)
        block = size * 1.3 + n * rsize * 1.45
        ty = y + (h - block) / 2 + size if center else y + size + 10
        cx = x + w / 2 if center else x + 12
        anc = 'middle' if center else 'start'
        self.text(cx, ty, title, size, tcolor or C['ink'], 700, anc)
        for i, row in enumerate(rows):
            self.text(cx, ty + size * 0.35 + (i + 1) * rsize * 1.45, row, rsize, C['ink2'], 400, anc, mono_rows)
        return self

    def arrow(self, pts, color=None, sw=1.6, dash=None, label=None, lx=None, ly=None, lsize=12.5, head=True, lcolor=None, lbg=True):
        color = color or C['ink2']
        d = 'M' + ' L'.join(f'{x},{y}' for x, y in pts)
        mid = {C['ink2']: 'a0', C['navy']: 'a1', C['fail']: 'a2', C['pass_']: 'a3', C['amber']: 'a4', C['violet']: 'a5', C['ink3']: 'a6'}.get(color, 'a0')
        dd = f' stroke-dasharray="{dash}"' if dash else ''
        mk = f' marker-end="url(#{mid})"' if head else ''
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{dd}{mk}/>')
        if label:
            if lx is None:
                (x1, y1), (x2, y2) = pts[len(pts) // 2 - 1], pts[len(pts) // 2]
                lx, ly = (x1 + x2) / 2, (y1 + y2) / 2 - 6
            if lbg:
                wpx = sum(lsize if ord(ch) > 255 else lsize * 0.58 for ch in label) + 10
                self.add(f'<rect x="{lx - wpx / 2}" y="{ly - lsize}" width="{wpx}" height="{lsize + 7}" rx="3" fill="#FFFFFF" opacity="0.92"/>')
            self.text(lx, ly, label, lsize, lcolor or color, 500, 'middle')
        return self

    def circle(self, cx, cy, r, fill=None, stroke=None, sw=1.4):
        return self.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill or C["white"]}" stroke="{stroke or C["rule"]}" stroke-width="{sw}"/>')

    def ellipse(self, cx, cy, rx, ry, fill=None, stroke=None, sw=1.4):
        return self.add(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill or C["white"]}" stroke="{stroke or C["rule"]}" stroke-width="{sw}"/>')

    def line(self, x1, y1, x2, y2, color=None, sw=1.4, dash=None):
        dd = f' stroke-dasharray="{dash}"' if dash else ''
        return self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color or C["rule"]}" stroke-width="{sw}"{dd}/>')

    def diamond(self, cx, cy, w, h, title, fill=None, stroke=None, size=14):
        pts = f'{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}'
        self.add(f'<polygon points="{pts}" fill="{fill or C["white"]}" stroke="{stroke or C["navy"]}" stroke-width="1.5"/>')
        return self.text(cx, cy + size * 0.35, title, size, C['ink'], 700, 'middle')

    def actor(self, cx, cy, label, color=None):
        c = color or C['navyd']
        self.add(f'<g stroke="{c}" stroke-width="2" fill="none"><circle cx="{cx}" cy="{cy - 30}" r="11"/>'
                 f'<line x1="{cx}" y1="{cy - 19}" x2="{cx}" y2="{cy + 10}"/><line x1="{cx - 16}" y1="{cy - 8}" x2="{cx + 16}" y2="{cy - 8}"/>'
                 f'<line x1="{cx}" y1="{cy + 10}" x2="{cx - 13}" y2="{cy + 32}"/><line x1="{cx}" y1="{cy + 10}" x2="{cx + 13}" y2="{cy + 32}"/></g>')
        for i, part in enumerate(label.split('\n')):
            self.text(cx, cy + 52 + i * 18, part, 14, C['ink'], 600, 'middle')
        return self

    def svg(self):
        markers = ''.join(
            f'<marker id="{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{v}"/></marker>'
            for k, v in (('a0', C['ink2']), ('a1', C['navy']), ('a2', C['fail']), ('a3', C['pass_']), ('a4', C['amber']), ('a5', C['violet']), ('a6', C['ink3'])))
        return (f'<svg id="fig" xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
                f'<defs>{markers}</defs><rect width="100%" height="100%" fill="#FFFFFF"/>' + ''.join(self.parts) + '</svg>')

    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            f.write('<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;background:#fff}</style></head><body>'
                    + self.svg() + '</body></html>')
