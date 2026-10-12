const { chromium } = require('playwright');
(async () => {
  const dir = process.argv[2];
  const b = await chromium.launch(); const p = await b.newPage({viewport:{width:1900,height:1110}, deviceScaleFactor:2.2});
  for (const lang of ['en','zh']) {
    await p.goto('file://' + dir + '/arch-' + lang + '.svg'); await p.waitForTimeout(600);
    await p.screenshot({path: dir + '/arch-' + lang + '.png', clip:{x:0,y:0,width:1900,height:1110}});
    await p.pdf({path: dir + '/arch-' + lang + '.pdf', width:'1900px', height:'1110px', printBackground:true, pageRanges:'1'});
  }
  await b.close();
})();
