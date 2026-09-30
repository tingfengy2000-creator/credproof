# 候选 0.2.0-preliminary.3：视觉与操作检查

日期：2026-09-30。起点为 `3a0d73500a030590668083765df2232da16a4312`。本版只升级既有单页的视觉、信息层级与候选材料，不更换模型、不增加安全案例、不重跑性能实验。**本轮没有新模型推理。**

## 展示变化

首页采用深色背景、青蓝与蓝紫点缀、放大的品牌标题和机制主视觉；三个特点、三个典型案例与工作区沿同一阅读路径展开。工作区分别展示泄露确认、候选生成、安全验收、业务行为和材料复检；模型文字、原始工具输出与详细身份置于折叠区。历史回放始终带 REPLAY 标识。

三个故事保持独立：h01 是有限修复增量；h03 是第一份候选失败后实际反馈进入第二次修改；h07 是合法认证与脱敏输出、未提交补丁、保持原代码。正式统计仍引用原同一批八例，不从三个精选案例推断总体成绩。

## 检查依据

- 原有 HTTP、材料绑定与历史展示回归：20 项通过，退出码 0。[实际命令与计时](checks/premium-20260930/web-regression.json)、[原始输出](checks/premium-20260930/web-regression.stderr.txt)。这些是程序回归，不是 20 个安全案例；不运行模型或候选代码。
- 最终前端 `node --check agent_pilot/ui/app.js` 退出 0；[语法检查及三文件摘要](checks/premium-20260930/ui-syntax.json)。
- 实际浏览器完成首页、三例切换、两份 h03 补丁展开、h07 空差异、导出及返回新任务。未捕获 warning/error。[操作与截图清单](checks/premium-20260930/browser-checks.json)。
- 新增一次 h07 确定性复检，时间 `2026-09-30T10:22:13.906077+00:00`，13 项必要条件 PASS，历史材料 INTACT，旧报告适用。它不调用模型，不回填旧批成绩。[实际复检 JSON](checks/premium-20260930/h07-fresh-recheck.json)、[界面所用分项来源](checks/premium-20260930/h07-result-states.json)、[展开后的 DOM](checks/premium-20260930/browser-recheck-dom.txt)。14 条依据包含 13 条 trial 和 1 条 source_profile，不是 14 个安全案例。
- 五项状态分别来自程序诊断、实际候选阶段或内容身份、禁止通道与源边界、业务检查和独立复检。h07 不因存在 `final-candidate.py` 被计为新补丁。h03 保留第一份失败及同批 A 已成功的结论；[h01 DOM](checks/premium-20260930/browser-h01-dom.txt)、[h03 DOM](checks/premium-20260930/browser-h03-dom.txt)、[h07 DOM](checks/premium-20260930/browser-h07-dom.txt)可查。
- 旧三个 ZIP 已复算大小与 SHA-256，与既有记录一致。[保护记录](checks/premium-20260930/package-protection.json)。
- 后端、实验与三份既有自包含材料相对起点无变化，main 未修改。[源码保护记录](checks/premium-20260930/source-protection.json)。报告实际页数、体积和逐页渲染检查见 [render-validation.json](render-validation.json)。

## 新版真实截图

[首页](assets/premium-home.png)、[特点与机制](assets/premium-overview.png)、[案例卡](assets/premium-cases.png)、[h01](assets/premium-h01.png)、[h03](assets/premium-h03.png)、[h03 关键代码差异](assets/premium-h03-diffs.png)、[h07](assets/premium-h07.png)、[独立复检](assets/premium-recheck.png)。图像为浏览器原始截图，不是拼图或模拟结果；关键差异截图不包含两份完整代码，完整内容可展开或读取原记录。

## 环境与材料口径

启动方式仍为 `python -m agent_pilot.launch --demo`。查看真实历史无需 GPU；重新验收需要已准备的可信隔离设施；新模型推理还需要已准备的本地模型。只声明已有 Windows + WSL 环境，不宣称跨机器或全平台验收。

候选包从最终固定 Git 提交生成，沿用 `scripts/build-review.py` 和 [包含范围](package-include-prefixes.json)。旧包、历史截图、逐案例记录与三份自包含复检材料保留。新截图和当前报告独立更新；旧版 PDF 可从旧候选包复查。本轮未生成视频。

原八例批次 A/B/C 问题修复为 3/4、1/4、4/4，最终对象 PASS 为 7/8、5/8、8/8，完整任务为 7/8、4/8、6/8。全部失败与未完成仍保留；新页面检查不回填历史成绩。身份、最终命名、AI 辅助开发许可及参赛声明仍由本人和指导教师确认。
