# 初赛候选 0.2.0-preliminary.1 定向发布检查（2026-09-29）

本页保留上一候选版的真实检查与当时文稿尺寸。本版 `0.2.0-preliminary.2` 只更新展示与候选材料，新增检查见 [presentation-checks.md](presentation-checks.md)；不得将下述现场推理重新标记为本版新实验。旧 PDF 和包可在 `9528bc9dc2fdb3c055ecad05a273e031c7cb388e` 及上一候选归档中复查。

源码检查点：`0095e1c9f587aa9ebfad97539e77825aeb089190`。本轮从该提交 `git archive` 得到独立目录，未使用原工作区的 Python 模块、未调用付费 API。候选执行继续使用已准备的 WSL 隔离设施；模型权重、venv 与隔离根不随源码包分发。此处是有限发布验证，不更新历史八例的性能表。

命令：`python scripts/check-candidate.py --output <新的目录> --live-case h01`，实际退出 0。它要求完整本地推理环境，即使省略 `--live-case` 也会预检模型文件；单独复检证据包不需要模型。

| 检查 | 真实结果 |
|---|---|
| 定向程序回归 | bundle 19、运行配置 8、Web 19、历史展示一致性 1；共 47 项通过。这不是 47 个真实安全案例。 |
| h01 新现场任务 | 仅尝试 1 次，修复任务 5 次模型调用（启动预热与联调另有记录），约 30.23 秒（含启动和轮询）；COMPLETED_REPAIRED，13/13 条件 PASS。 |
| 新现场资源与离线边界 | 采样显存峰值 19,168 MiB；任务网络命名空间仅 loopback，前后外连探测失败；无付费 API。 |
| h01 / h03 / h07 历史材料 | 3 份页面重新验收通过；每份下载后移至独立目录，再用内置程序各执行 13 项检查，均 PASS。历史推理仍标为 REPLAY。 |
| 导出后额外修改专用副本 | 再导出 / 再复检均 HTTP 409；当前判决 UNKNOWN、旧复检不适用；此前 ZIP 摘要不变。 |
| 冻结检查 | 65 个源码、规则、配置文件运行前后摘要一致；未在执行过程中更改依赖。 |

完整逐命令输出、新模型请求/响应/工具回执及全部候选见 [release-check](../../experiments/preliminary-candidate/20260929T140358Z-release-check/)。[现场结果](../../experiments/preliminary-candidate/20260929T140358Z-release-check/live-release-observation.json)、[对象错位回归](../../experiments/preliminary-candidate/20260929T140358Z-release-check/changed-copy-result.json)、[冻结结果](../../experiments/preliminary-candidate/20260929T140358Z-release-check/source-freeze-result.json)分别保存。路径脱敏仅发生在公开日志副本，原始记录保留本地；修改字段与前后摘要见 [publication-note.json](../../experiments/preliminary-candidate/20260929T140358Z-release-check/publication-note.json)。模型运行没有因文档整理或编码处理被重跑。

另有两次真实隔离检查证明：清单内可选轨迹丢失会显示 DEGRADED，原报告适用性与当前 PASS 保持独立。[材料完整性检查](checks/bundle-integrity/20260929T135515Z/command-log.json)不计入新案例数量。先前 WSL Git 启动路径错误记录保留，该失败没有开始候选执行。

## 可以直接复检的三份材料

- [h01](materials/h01/README.md)：模型完成参数日志修复。
- [h03](materials/h03/README.md)：包含失败候选反馈与最终通过记录；历史第一补丁不会被删除。
- [h07](materials/h07/README.md)：原代码保持不变。

在任一材料目录执行：

```powershell
python -B -S -m agent_pilot.bundle recheck --bundle . --output ../a-new-recheck.json
```

每次使用新输出文件名；执行侧读取代码、核对材料并重新运行必要检查。PASS 只针对当前支持的接口与完整明文凭据检测。缺隔离时阻断，不在宿主运行候选。

## 界面与文稿

通过浏览器实际打开三张精选卡片，核对 h03 的 FAIL/PASS 两阶段、h07 空补丁，以及导出和重新验收操作。截图见 [h01](assets/h01-replay.png)、[h03](assets/h03-replay.png)、[h03 完整页面](assets/h03-full-page.png)。这些是历史记录的真实界面截图，不是新推理截图。本轮未生成视频文件。

候选 PDF 10 页、477,654 字节（小于 10 MB）；可编辑 DOCX、Markdown、SVG 与生成脚本同时保留。文稿逐页排版检查见 [render-validation.json](render-validation.json)。正式命名、身份字段、签署及 AI 参赛规则待队伍确认。

## 后续清单

本轮停止扩展：不增加新案例集、模型、页面或通用上传接口。后续仅在参赛者确认规则后整理正式命名与声明、录制讲稿对应视频，并按实际需要改善首次环境准备体验。自有代码分发许可待作者确认。所有原始失败仍保留，不声称工具泛化、模型零误报或外部验收已通过。
