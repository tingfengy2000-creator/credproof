# 作品报告 v3（正式提交稿）

正文唯一来源：`manuscript.md`（官方模板章序；附录一 其他文档、附录二 参赛作品声明）。定位沿用 v2 已批准的“AI生成安全补丁的可信验收与人机协同修复平台”，数据换为 bench-v1、产品工作台、CI 与 R4 证据。

| 路径 | 内容 |
|---|---|
| `figs/f_*.py` + `svgkit.py` | 7 张专业图：架构、泳道流程、一层 DFD、用例、时序、14 条件↔五问、三状态 |
| `figs/charts.py` | 6 张数据图，**只读仓库冻结 JSON**（comparison.json、bench-results.json、onboarding-dotenv.json、ci-c/results.json、app.js 中 STORY_EVIDENCE） |
| `shots/` | 产品截图（裁剪自 docs/ui/product-v1、console-v1 已有真实截图） |
| `build.py` | 在官方模板上生成 DOCX：宋体小四、1.5 倍行距（含表格与代码）、黑体标题、封面与填写说明页保留、页脚“第 x 页 共 y 页”、`::: land` 横向插页 |
| `build-all.sh` | Linux 预览：两遍渲染，静态目录页码自动核对 |
| `out/credproof-report.docx` | 当前稿；`out/credproof-report-preview.pdf` 为 LibreOffice 替代字体预览 |

## 正式 PDF（Windows）

1. Word 打开 `out/credproof-report.docx`（真实宋体/黑体）。
2. 检查目录页码：目录为静态文字，按 Linux 预览分页写入；Word 分页若有偏移，以 Word 中标题实际页码手工改目录数字，或在 Linux 重跑 `build-all.sh` 前先调整内容。
3. 另存为 PDF；核对：页数约 74、横向插页 6 处正常、图片清晰、文件属性作者为空、大小 ≤10MB（预览约 4.8MB）。
4. 附录二声明需参赛者签字（可打印签字后扫描替换该页，或按大赛要求另交）。

重新生成数据图：`python docs/report-v3/figs/charts.py`。重新生成示意图：`python figs/f_xxx.py` 后在装有 playwright 的目录运行 `node render.mjs <src> <out> <前缀>`。
