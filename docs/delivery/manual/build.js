// Formal judge manual: black text, 宋体/黑体, numbered figures and tables, cover + TOC.
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType,
  AlignmentType, HeadingLevel, BorderStyle, PageBreak, Header, Footer, PageNumber, TableLayoutType,
  TabStopType, LineRuleType, VerticalAlign, VerticalMergeType,
} = require('docx');

const [out, tocJson] = process.argv.slice(2);
const toc = tocJson && fs.existsSync(tocJson) ? JSON.parse(fs.readFileSync(tocJson, 'utf8')) : null;
const content = require('./content.js');
const IMG = path.join(__dirname, 'img');

const SONG = { ascii: 'Times New Roman', hAnsi: 'Times New Roman', eastAsia: '宋体', cs: 'Times New Roman' };
const HEI = { ascii: 'Arial', hAnsi: 'Arial', eastAsia: '黑体', cs: 'Arial' };
const MONO = { ascii: 'Consolas', hAnsi: 'Consolas', eastAsia: '宋体', cs: 'Consolas' };
const BLACK = '000000', GRAY = '595959', RULE = '7F7F7F', FILL = 'EDEDED';
const PAGE_W = 11906, MARGIN_LR = 1418, CONTENT = PAGE_W - 2 * MARGIN_LR; // 9070 dxa
const CONTENT_PX = Math.round(CONTENT / 15);                             // ≈ 605 px
const BODY = 21; // 五号 10.5pt
const LINE = { line: 360, lineRule: LineRuleType.AUTO };                  // 1.5 倍

function runs(text, base = {}) {
  const parts = String(text).split(/(\*\*[^*]+\*\*)/).filter(Boolean);
  return parts.map(t => {
    const bold = t.startsWith('**');
    return new TextRun({ text: bold ? t.slice(2, -2) : t, bold: bold || base.bold, font: base.font || SONG,
      size: base.size || BODY, color: base.color || BLACK });
  });
}

const children = [];
let fig = 0, tab = 0;
const headings = [];
const border = { style: BorderStyle.SINGLE, size: 4, color: BLACK };
const cellBorders = { top: border, bottom: border, left: border, right: border };

function para(text, opts = {}) {
  return new Paragraph({ children: runs(text, opts), alignment: opts.align || AlignmentType.JUSTIFIED,
    indent: opts.indent === undefined ? { firstLine: 420 } : opts.indent, spacing: { ...LINE, before: 0, after: 60 },
    keepNext: opts.keepNext });
}

function cell(text, width, header, merge) {
  const lines = String(text).split('\n');
  return new TableCell({ width: { size: width, type: WidthType.DXA }, borders: cellBorders,
    verticalAlign: VerticalAlign.CENTER, verticalMerge: merge,
    shading: header ? { type: ShadingType.CLEAR, fill: FILL, color: 'auto' } : undefined,
    margins: { top: 50, bottom: 50, left: 100, right: 100 },
    children: lines.map(l => new Paragraph({ alignment: header ? AlignmentType.CENTER : AlignmentType.LEFT,
      spacing: { line: 300, lineRule: LineRuleType.AUTO, before: 0, after: 0 },
      children: runs(l, { bold: header, size: 19, font: header ? HEI : SONG }) })) });
}

for (let i = 0; i < content.length; i++) {
  const [kind, a, b, c] = content[i];
  if (kind === 'h1') {
    headings.push({ level: 1, text: a });
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: runs(a, { font: HEI, size: 32, bold: false }),
      spacing: { before: children.length ? 480 : 120, after: 240, line: 360, lineRule: LineRuleType.AUTO }, keepNext: true }));
  } else if (kind === 'h2') {
    headings.push({ level: 2, text: a });
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(a, { font: HEI, size: 24, bold: false }),
      spacing: { before: 240, after: 120, line: 360, lineRule: LineRuleType.AUTO }, keepNext: true }));
  } else if (kind === 'p') {
    children.push(para(a));
  } else if (kind === 'note') {
    children.push(new Paragraph({ indent: { left: 420 }, spacing: { ...LINE, before: 60, after: 120 },
      children: [new TextRun({ text: '注：', font: HEI, size: 19, color: BLACK }), ...runs(a, { size: 19 })] }));
  } else if (kind === 'steps') {
    const start = b || 1;
    a.forEach((item, k) => {
      const lines = String(item).split('\n');
      lines.forEach((line, j) => {
        children.push(new Paragraph({ indent: { left: 840, hanging: 420 }, spacing: { ...LINE, before: 0, after: 40 },
          tabStops: [{ type: TabStopType.LEFT, position: 840 }],
          children: j === 0 ? [new TextRun({ text: `${start + k}.`, font: SONG, size: BODY }), new TextRun({ text: '\t', size: BODY }), ...runs(line)]
                            : runs(line) }));
      });
    });
  } else if (kind === 'bullets') {
    a.forEach(item => children.push(new Paragraph({ indent: { left: 840, hanging: 420 }, spacing: { ...LINE, before: 0, after: 40 },
      tabStops: [{ type: TabStopType.LEFT, position: 840 }],
      children: [new TextRun({ text: '•', font: SONG, size: BODY }), new TextRun({ text: '\t', size: BODY }), ...runs(item)] })));
  } else if (kind === 'code') {
    const box = { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 4 };
    a.forEach((line, k) => children.push(new Paragraph({ indent: { left: 420, right: 120 },
      shading: { type: ShadingType.CLEAR, fill: 'F5F5F5', color: 'auto' },
      border: Object.assign({}, k === 0 ? { top: box } : {}, { left: box }, k === a.length - 1 ? { bottom: box } : {}, { right: box }),
      spacing: { before: k === 0 ? 60 : 0, after: k === a.length - 1 ? 120 : 0, line: 276, lineRule: LineRuleType.AUTO },
      children: [new TextRun({ text: line, font: MONO, size: 17, color: BLACK })] })));
  } else if (kind === 'tablecap') {
    tab += 1;
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 160, after: 80 },
      children: runs(`表 ${tab}　${a}`, { font: HEI, size: 19 }) }));
  } else if (kind === 'table') {
    const pct = a, header = b, rows = c;
    const widths = pct.map(p => Math.round(CONTENT * p / 100));
    widths[widths.length - 1] += CONTENT - widths.reduce((s, x) => s + x, 0);
    // merge empty first-column cells into the row above (grouped rows)
    const trs = [new TableRow({ tableHeader: true, cantSplit: true, children: header.map((h, j) => cell(h, widths[j], true)) })];
    rows.forEach((r, ri) => {
      const next = rows[ri + 1];
      const grouped = r[0] === '' || (next && next[0] === '');
      const merge = !grouped ? undefined : (r[0] === '' ? VerticalMergeType.CONTINUE : VerticalMergeType.RESTART);
      trs.push(new TableRow({ cantSplit: true, children: r.map((t, j) => cell(t, widths[j], false, j === 0 ? merge : undefined)) }));
    });
    children.push(new Table({ width: { size: CONTENT, type: WidthType.DXA }, columnWidths: widths,
      layout: TableLayoutType.FIXED, rows: trs }));
    children.push(new Paragraph({ spacing: { before: 0, after: 120 }, children: [] }));
  } else if (kind === 'fig') {
    fig += 1;
    const file = path.join(IMG, a + '.jpg');
    const buf = fs.readFileSync(file);
    const w = buf.readUInt16BE ? null : null;
    const dims = require('child_process').execSync(`python3 -c "from PIL import Image;i=Image.open('${file}');print(i.size[0],i.size[1])"`).toString().trim().split(' ').map(Number);
    let width = Math.round(CONTENT_PX * (c || 100) / 100), height = Math.round(width * dims[1] / dims[0]);
    const MAXH = 600;
    if (height > MAXH) { width = Math.round(width * MAXH / height); height = MAXH; }
    const imgBorder = { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 1 };
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: 'jpg', data: buf, transformation: { width, height },
        altText: { title: `图 ${fig}`, description: b, name: a } })] }));
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 200 },
      children: runs(`图 ${fig}　${b}`, { font: HEI, size: 19 }) }));
  } else throw new Error('unknown block ' + kind);
}

// ---------------------------------------------------------------- cover --
const cover = [
  new Paragraph({ spacing: { before: 2600, after: 0 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: '密证 CredProof', font: HEI, size: 52, color: BLACK })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
    children: [new TextRun({ text: 'AI 生成安全补丁的可信验收与人机协同修复平台', font: SONG, size: 28, color: BLACK })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 2400 },
    border: { top: { style: BorderStyle.SINGLE, size: 8, color: BLACK, space: 12 } },
    children: [new TextRun({ text: '评委操作手册', font: HEI, size: 44, color: BLACK })] }),
  ...[['参赛队伍', 'DUIDUI队'], ['作品类别', '第五届中国研究生网络安全创新大赛 · 创意作品赛'], ['文档版本', 'V1.0'], ['发布日期', '2026 年 10 月']]
    .map(([k, v]) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
      children: [new TextRun({ text: `${k}：`, font: HEI, size: 24 }), new TextRun({ text: v, font: SONG, size: 24 })] })),
];

// ------------------------------------------------------------------ toc --
const tocParas = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 360 },
    children: [new TextRun({ text: '目　录', font: HEI, size: 32 })] }),
];
const tocPlaceholder = '@@TOC_ENTRIES@@';
tocParas.push(new Paragraph({ children: [new TextRun(tocPlaceholder)] }));

const header = new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
  border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: BLACK, space: 4 } },
  children: [new TextRun({ text: '密证 CredProof 评委操作手册', font: SONG, size: 18, color: BLACK })] })] });
const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
  new TextRun({ text: '第 ', font: SONG, size: 18 }), new TextRun({ children: [PageNumber.CURRENT], font: SONG, size: 18 }),
  new TextRun({ text: ' 页', font: SONG, size: 18 })] })] });
const page = { size: { width: PAGE_W, height: 16838 }, margin: { top: 1440, bottom: 1300, left: MARGIN_LR, right: MARGIN_LR, header: 760, footer: 700 } };

const doc = new Document({
  creator: 'DUIDUI队', lastModifiedBy: 'DUIDUI队', title: '密证 CredProof 评委操作手册', description: '评委操作手册',
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: SONG, size: BODY, color: BLACK } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: HEI, size: 32, bold: false, color: BLACK }, paragraph: { outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { font: HEI, size: 24, bold: false, color: BLACK }, paragraph: { outlineLevel: 1 } },
      { id: 'TOC1', name: 'toc 1', basedOn: 'Normal', next: 'Normal', run: { font: HEI, size: 21 },
        paragraph: { spacing: { before: 120, after: 40 }, tabStops: [{ type: TabStopType.RIGHT, position: CONTENT, leader: 'dot' }] } },
      { id: 'TOC2', name: 'toc 2', basedOn: 'Normal', next: 'Normal', run: { font: SONG, size: 21 },
        paragraph: { indent: { left: 420 }, spacing: { before: 0, after: 40 }, tabStops: [{ type: TabStopType.RIGHT, position: CONTENT, leader: 'dot' }] } },
    ],
  },
  sections: [
    { properties: { page }, children: cover },
    { properties: { page }, headers: { default: header }, footers: { default: footer }, children: tocParas },
    { properties: { page }, headers: { default: header }, footers: { default: footer }, children },
  ],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(out, buf);
  fs.writeFileSync(out + '.headings.json', JSON.stringify(headings));
  console.log('wrote', out, buf.length, 'figures', fig, 'tables', tab, 'headings', headings.length);
});
