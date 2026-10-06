# 说明书构建与核验

候选文件为 `credproof-manuscript-candidate.docx` 和同名 PDF。它们保留官方填写说明页，正文匿名；提交日期待填。正式上传的队长字段、文件命名及参赛资格由队伍本人确认，当前文件名仅用于候选材料管理。

正文来源 `manuscript.md`，摘要与展示口径见 `summary.md`。本次对应 `0.2.0-preliminary.9` 增强候选整合：保留官方版式、旧批次统计和三个主故事，补充三类安全检查、项目接入、导出报告校验和通俗讲解。旧 PDF 可从旧候选 ZIP 或 Git 版本读取。原官方报告模板与 SHA256 来源见 `template-requirements.md`。构建使用 `assets/official-template.docx`，这是原 DOC 经 WPS 转换后保留的参考副本；原始 `.doc` 未改动。

在项目根目录，以配备 python-docx、lxml、pypdf、pypdfium2、Pillow 的 Python 执行。当前已验证的解释器为 Codex bundled runtime，文档转换使用本机已安装的 WPS Office 12.1.0.28485 COM 接口 `kwps.Application`。

```powershell
$reportPython = 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $reportPython docs/preliminary-candidate/draw-mechanism.py
& $reportPython docs/preliminary-candidate/build-report.py --mechanism docs/preliminary-candidate/assets/mechanism.png --overview docs/preliminary-candidate/assets/external-delivery-h01.png --trace docs/preliminary-candidate/assets/external-delivery-h03-fail.png --recheck docs/preliminary-candidate/assets/external-delivery-recheck.png
& docs/preliminary-candidate/export-report.ps1
& $reportPython docs/preliminary-candidate/finalize-report.py
```

`build-report.py` 保留模板封面与填写说明，更新正文、目录字段、图表和页码；`export-report.ps1` 隐藏打开 WPS，刷新目录和页码并导出 PDF；`finalize-report.py` 删除 WPS 再次写入的作者等元数据，并生成逐页 PNG。该环境无可用 bundled LibreOffice，因此使用已获授权的 WPS 导出加 PDFium 渲染路径，没有安装新办公软件。

每次修改或重新导出后，都必须重新执行清理与渲染，并逐页打开 `working/render-final/page-01.png` 等检查。脚本只产生待检记录，不会自动声称视觉验收完成。生成物、抽取文本和哈希写在 `working/`，该目录为内部核验材料。`render-validation.json` 记录交付版实际核验结果。

文档构建不执行模型、候选代码或业务实验。本章历史成绩始终引用同一轮 `20260929t095000z-holdout8`，当前有限发布检查由主流程另记，不回填历史成绩。
