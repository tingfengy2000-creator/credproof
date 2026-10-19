# 作品报告 v3（正式提交稿）

正文唯一来源：`manuscript.md`（官方模板章序；附录一 其他文档、附录二 参赛作品声明）。定位沿用 v2 已批准的“AI生成安全补丁的可信验收与人机协同修复平台”，数据换为 bench-v1、产品工作台、CI 与 R4 证据。

| 路径 | 内容 |
|---|---|
| `figs/f_*.py` + `svgkit.py` | 7 张专业图：架构、泳道流程、一层 DFD、用例、时序、14 条件↔五问、三状态 |
| `figs/charts.py` | 6 张数据图，**只读仓库冻结 JSON**（comparison.json、bench-results.json、onboarding-dotenv.json、ci-c/results.json、app.js 中 STORY_EVIDENCE） |
| `shots/` | 产品截图（裁剪自 docs/ui/product-v1、console-v1 已有真实截图） |
| `build.py` | 在官方模板上生成 DOCX：宋体小四、1.5 倍行距（含表格与代码）、黑体标题、封面与填写说明页保留、页脚“第 x 页 共 y 页”、`::: land` 横向插页 |
| `build-all.sh` | Linux 预览：两遍渲染，静态目录页码自动核对 |
| `out/credproof-report.docx` | 已在 Microsoft Word 更新目录的当前稿 |
| `out/credproof-report.pdf` | Microsoft Word 原生导出的正式 PDF；52 页，6 页横向插页，作者属性为空 |
| `out/credproof-report-preview.pdf` | 保留的 LibreOffice 替代字体预览；不作为正式分页依据 |

## 正式 PDF（Windows）

1. Word 打开 `out/credproof-report.docx`（真实宋体/黑体）。
2. 更新目录：目录是 Word 目录域（预填了 Linux 预览的页码）。右键目录 →“更新域”→“更新整个目录”，页码即按 Word 实际分页（Word 用真实宋体，页数会比预览少）。更新后确认目录字体仍为宋体小四，一级标题加粗与否不影响。
3. 另存为 PDF；以 Word 实际分页为准，不沿用 Linux 预览页码。2026-10-19 的正式导出为 52 页、3,310,150 字节；49 项目录页码逐项对应，横向插页为第 15、16、18、20、22、23 页，文件属性作者为空，大小小于 10MB。表 14 的题注、表头和首行保持在一起，避免表头孤页。正文和声明文字未改。
4. 附录二声明需参赛者签字（可打印签字后扫描替换该页，或按大赛要求另交）。

本次 Word 分页、逐页检查和运行包核验记录见 [`../delivery/evidence/duidui-release-r2-20261019/README.md`](../delivery/evidence/duidui-release-r2-20261019/README.md)。重新运行生成脚本后，需再次使用 Word 更新目录并导出，不可直接沿用本次 PDF 收据。

重新生成数据图：`python docs/report-v3/figs/charts.py`。重新生成示意图：`python figs/f_xxx.py` 后在装有 playwright 的目录运行 `node render.mjs <src> <out> <前缀>`。
