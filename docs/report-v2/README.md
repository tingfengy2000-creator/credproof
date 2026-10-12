# 作品报告 v2：AI 生成安全补丁的可信验收闸门

定位已由 tingfeng 批准：**密证 CredProof——AI生成安全补丁的可信验收与人机协同修复平台**。

| 文件 | 用途 |
|---|---|
| `manuscript.md` | 报告正文（唯一源），按官方模板章序 |
| `figures/figures.html` | 图 1–3、5 的源；`figures/make_comparison.py` 由数据生成图 5 |
| `data/build_ai_patch_dataset.py` | 汇总全部 21 份 AI 补丁的当时判定与复检记录，逐条核对原始证据文件，再跑 Bandit / Semgrep / Gitleaks（只读源码，不执行补丁） |
| `data/ai-patch-dataset.json` | 上述脚本的输出，报告第三章所有数字的来源 |
| `build.py` | 在官方模板上生成 DOCX（宋体小四、1.5 倍行距、封面与填写说明页保留、页脚“第 x 页 共 y 页”） |
| `build-preview.sh` | Linux 预览：两遍渲染并核对目录页码 |
| `out/credproof-report-v2-preview.{docx,pdf}` | 当前预览版（LibreOffice 渲染，字体为替代字体） |

## 最终 PDF

预览 PDF 在 Linux 上用替代字体渲染。正式提交请在 Windows 上用 Word 打开 `out/credproof-report-v2-preview.docx`，更新目录后导出 PDF（真实宋体）。导出后检查：页数、目录页码、图片清晰度、文件属性作者为空、大小不超过 10MB。

## 数据口径

- 21 份 = 仓库中全部带源码的唯一 AI 补丁（CRLF 统一为 LF 后按 SHA-256 去重）。排除 1 份去掉代码围栏的派生件和 1 份只差空白的副本。
- 判定取当时记录；有升级规则后的复检记录（#1、#7）时取复检结果。issue #2 请 5090 在同一套现行规则下统一复检，结果出来后以统一复检为准更新第三章。
- “实际泄露凭据”指运行中本次随机合成凭据确实出现在返回值、输出、日志或异常里，可在原始记录中逐条核对。
