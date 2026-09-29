// Local-only figure rendering. Writes only files beside this script.
const fs = require('node:fs');
const path = require('node:path');
// Supply local rendering dependencies; neither is a dependency of the CLI core.
// Example: CREDPROOF_PLAYWRIGHT=<module directory>, CREDPROOF_MERMAID=<mermaid.min.js>.
const {chromium} = require(process.env.CREDPROOF_PLAYWRIGHT || 'playwright');
const mermaidPath = process.env.CREDPROOF_MERMAID;
if (!mermaidPath) throw new Error('Set CREDPROOF_MERMAID to a locally installed mermaid.min.js');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1600, height: 1100}, deviceScaleFactor: 1});
    await page.setContent('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><body style="margin:0;background:white"></body></html>');
    await page.addScriptTag({path: mermaidPath});
    const source = fs.readFileSync(path.join(__dirname, 'mechanism.mmd'), 'utf8');
    const rendered = await page.evaluate(async source => {
      mermaid.initialize({startOnLoad: false, securityLevel: 'strict', theme: 'base', htmlLabels: false,
        themeVariables: {fontFamily: 'Microsoft YaHei,Segoe UI,sans-serif', fontSize: '18px',
          lineColor: '#8f9eae', clusterBkg: '#f8fafc', clusterBorder: '#dbe3ec',
          edgeLabelBackground: '#ffffff', primaryTextColor: '#17344b'},
        flowchart: {htmlLabels: false, useMaxWidth: false, wrappingWidth: 370, nodeSpacing: 32, rankSpacing: 35, curve: 'linear', padding: 17}});
      const {svg} = await mermaid.render('credproofMechanism', source);
      document.body.innerHTML = svg;
      await document.fonts.ready;
      const root = document.querySelector('svg');
      return {svg: new XMLSerializer().serializeToString(root), viewBox: root.getAttribute('viewBox')};
    }, source);
    const dims = rendered.viewBox.split(/[ ,]+/).map(Number);
    const width = Math.max(1440, Math.ceil(dims[2] + 88));
    const graphHeight = Math.ceil(dims[3]);
    const height = graphHeight + 246;
    const graph = rendered.svg.replace(/<svg\b([^>]*)>/, (_, attrs) =>
      `<svg ${attrs.replace(/\s(?:width|height|x|y)="[^"]*"/g, '')} x="${(width - dims[2])/2}" y="136" width="${dims[2]}" height="${dims[3]}">`);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <rect width="${width}" height="${height}" fill="#ffffff"/>
      <rect x="40" y="35" width="5" height="71" rx="2" fill="#1c8d79"/>
      <g font-family="Microsoft YaHei,Segoe UI,sans-serif">
      <text x="62" y="64" fill="#17344b" font-size="28" font-weight="700">密证 CredProof｜副本修复验收机制</text>
      <text x="62" y="98" fill="#50657c" font-size="17">验证“指定副本是否满足冻结条件”，并独立说明原工作区与暂存区的剩余风险</text>
      </g>${graph}
      <line x1="42" y1="${height-75}" x2="${width-42}" y2="${height-75}" stroke="#e1e7ee"/>
      <g font-family="Microsoft YaHei,Segoe UI,sans-serif" fill="#52667c" font-size="15">
      <text x="44" y="${height-47}">范围：已实现的离线合成机制试验；功能检查只接受受控夹具，不执行任意仓库脚本。</text>
      <text x="44" y="${height-22}">公开报告为脱敏视图；复检需要原始本地材料。局部哈希不是签名，PASS 不代表凭据有效性、撤销或事件闭环。</text>
      </g></svg>`;
    fs.writeFileSync(path.join(__dirname, 'mechanism.svg'), svg, 'utf8');
    await page.setViewportSize({width, height});
    await page.setContent('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><body style="margin:0;background:white">' + svg + '</body></html>');
    await page.evaluate(() => document.fonts.ready);
    await page.locator('body > svg').screenshot({path: path.join(__dirname, 'mechanism.png')});
    console.log(JSON.stringify({width,height,files:['mechanism.mmd','mechanism.svg','mechanism.png']}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
