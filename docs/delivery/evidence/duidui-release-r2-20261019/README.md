# DUIDUI R2 运行包与正式 Word PDF

PR #24 已按指定 head `a6e966b16ef25f4796f6b352e01938e8fce7b312` 合并到 `release/duidui-delivery`，合并提交 **`cf0a7ac42e10577e915188be326822342e13af07`**。其包含 PR #23 的 `aa5bd615456e8db29609033d1968a81534ff1abd`，未修改 main、模型、检查器、规则或测试。

## 运行包

- 使用与上轮相同的官方 Windows embeddable Python 3.12.10 ZIP，其 SHA256 为 `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`。
- 根据用户新清单在仓库外创建 `forbid.json`；文件不入 Git 或运行包。扩展词清单及精确例外原样使用，规格摘要见 `release-verification.json`。
- 在干净合并提交上运行原 `scripts/delivery/build_release.py`，460 个源码成员加随包运行时，共 496 个文件；禁止词命中 **0**。补充抽取随包《项目简介.pdf》文字核对，亦为 0。
- 新 ZIP：`DUIDUI队-密证CredProof.zip`，**15,530,519 字节**。
- SHA256：`54e7f1390df35c0fb886ad31a048b468975ead453f5bc87b0f38c213c1728983`。
- 重新解压到含中文和空格的新目录；压缩包 CRC 及全部成员字节核对通过。在 Windows 资源管理器中实际双击该目录的 `start-credproof.cmd`，启动随包 Python，浏览器首页显示“只读回放：不执行代码，不调用模型”和“本机服务已连接”；浏览器错误日志为空。截图见 `windows-start-home.png`。
- 新增模型请求 **0**，候选执行 **0**。没有重跑上轮有效的资料助手动态试验。

构建命令（外部路径由操作者指定）：

```text
python scripts/delivery/build_release.py --output <新目录>/DUIDUI队-密证CredProof --python-zip <官方python-3.12.10-embed-amd64.zip> --forbid-file <仓库外forbid.json>
```

## 正式报告

Microsoft Word 原生打开合并版本的 `docs/report-v3/out/credproof-report.docx`，更新真实目录域、页码和分页，再原生导出 [`credproof-report.pdf`](../../../report-v3/out/credproof-report.pdf)。没有使用 WPS 或 LibreOffice 生成正式 PDF。

- Word 的版本、build、完整目录文本、标题对应页码与各节页面设置见 `word-export.json`。
- 最终 **52 页**，**49 项目录**逐一与 Word 和 PDF 标题所在页对应。
- 六个横向页为 **15、16、18、20、22、23**，已逐页查看。
- 逐页检查中修正一处格式：表 14 的题注、表头与首行保持在一起，不再让表头独占上一页。最终仅第 35、36 页 PNG 改变并重新检查；其余 50 页与已查看的渲染字节一致，见 `final-render-diff.json`。
- 除目录结果外的 **651 个非空正文段落逐字相同**；正文数据和声明未修改、未签署。
- 最终 PDF **3,310,150 字节**，小于 10MB；PDF 作者及 XMP 作者均为空，DOCX creator/lastModifiedBy 亦为空。
- PDF、可编辑 DOCX 的 SHA256 和完整核对结果见 `word-validation.json`。`docs/report-v3/README.md` 已改为指向这份正式 PDF，并纠正旧的预期页数。

正式报告单独交付，不被 `build_release.py` 白名单打入运行包；它保留原文献引用。运行包的禁止词结果不冒充对正式报告书目的删除或改写。

## 来源区分

运行包固定源码为合并提交 `cf0a7ac42e10577e915188be326822342e13af07`。后续提交仅保存 Word 更新后的 DOCX、正式 PDF、报告入口及本收据，不把后加材料提交当成包内源码，也不将 GitHub 自动源码 ZIP 与本次 Windows 运行包共用摘要。旧包、原 DOCX、首轮 Word 导出及原始记录均保留。
