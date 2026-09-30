# 候选 0.2.0-preliminary.2：展示与交付检查

日期：2026-09-30。起点为 `9528bc9dc2fdb3c055ecad05a273e031c7cb388e`；本版更新单页视觉、信息结构和参赛表达，不增加模型、案例或实验轮次。**本轮没有新模型推理。**

## 已完成的检查

| 项目 | 实际结果与依据 |
|---|---|
| 页面语法与必要回归 | `node --check agent_pilot/ui/app.js` 退出 0；`python -B -m unittest agent_pilot.tests.test_web agent_pilot.tests.test_web_material_binding agent_pilot.tests.test_presentation -v` 共 20 项通过。[命令与退出码](checks/presentation-20260930/command-results.json)。这些是程序回归，不是 20 个安全案例。 |
| 实际浏览器操作 | 首页、三个典型案例、两份 h03 差异、h07 空差异、导出、复检及返回新任务均已操作；浏览器无已捕获的 warning/error。[操作记录](checks/presentation-20260930/browser-checks.json)。 |
| 新的确定性复检 | 仅点击一次 h07“重新验收”，取得 13 个场景条件 PASS、旧报告仍适用、材料完整性 INTACT；不调用模型，不更新历史任务成绩。[原始复检 JSON](checks/presentation-20260930/h07-fresh-recheck.json)。另有 source_profile 检查，页面折叠区共 14 条记录，不是 14 个独立案例。 |
| 折叠后内容可读 | 原模型文本、工具证据、候选差异、运行身份仍可展开；新增复检明细展开后可读到 trial_13。[实际 DOM](checks/presentation-20260930/browser-recheck-dom.txt)。 |
| 判决逻辑与历史保持 | `agent_pilot` 除 `ui` 外相对起点无变化；`experiments` 与三份既有自包含复检材料无变化。[检查命令](checks/presentation-20260930/final-source-check.json)。 |
| 旧包保护 | 上版候选包和完整研发包均复算大小及 SHA-256，与前次记录一致。[保护记录](checks/presentation-20260930/package-protection.json)。 |
| 文稿与图片 | 名称、核心价值、三个特点与三个案例一致；DOCX/PDF 的实际页数、体积和逐页检查见 [render-validation.json](render-validation.json)。 |

20 项回归之后只将复检逐项表折叠为 details，未改变检查内容或任何后端逻辑；最终脚本再次通过语法检查，并完成实际展开验证。两次检查的源码摘要各自保留，不将其混为同一字节版本。

## 本轮真实截图

[首页](assets/showcase-home.png)、[作品总览](assets/showcase-overview.png)、[典型案例入口](assets/showcase-cases.png)、[h01](assets/showcase-h01.png)、[h03 两阶段](assets/showcase-h03.png)、[h03 展开的差异](assets/showcase-h03-diffs.png)、[h07](assets/showcase-h07.png)、[新复检](assets/showcase-recheck.png)。均为实际浏览器截取，保留回放或复检身份；不是生成图片或新的 Agent 推理结果。

一分钟提纲、三分钟脚本和录屏分镜见 [展示指南](presentation-guide.md)。**本轮未生成视频文件。**

## 使用与统计口径

`python -m agent_pilot.launch --demo` 从本版代码树启动。历史展示无需 GPU；确定性复检需要既有可信隔离环境；现场新推理还需要已准备的本地模型。当前仅声明已验证的 Windows + WSL 组合。

正式测试表继续引用 `20260929t095000z-holdout8`：A/B/C 的问题修复为 3/4、1/4、4/4，最终对象 PASS 为 7/8、5/8、8/8，完整任务为 7/8、4/8、6/8。后续已知案例复测、上一候选版一次 h01 现场运行与本次 h07 程序复检均不合并进该表。

## 候选包与收口

候选包沿用 `scripts/build-review.py`，从最终固定提交生成，版本为 `0.2.0-preliminary.2`；[包含范围](package-include-prefixes.json)保留原八例完整记录及必要失败证据。ZIP、manifest、SHA-256 和干净解包启动记录在独立交付目录生成，不回写提交 SHA，不覆盖旧包。旧完整研发包继续保留。

后续按实际参赛需要完善录屏、首次环境准备和扩展接口。上一版 Linux 全量测试中的 WindowsPath 模拟错误、完整研发包深路径解压限制仍保留为已知事项，本版不声称已经修复。身份、正式命名、原创声明、AI 辅助开发许可及自有代码分发许可由本人和指导教师确认；开源归属和 AI 参与记录另行管理。
