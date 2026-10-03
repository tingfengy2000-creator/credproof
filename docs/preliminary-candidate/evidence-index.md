# 证据索引

本页把评委看到的主张连接到可读源码和真实记录。页面、视频和说明书只精选展示；原始失败、未完成和完整批次仍保留在仓库。

| 展示主张 | 入口 | 应核对的事实 |
|---|---|---|
| 运行时凭据可进入日志或异常输出 | [h01材料](materials/h01/README.md)、[Twine来源](../external-scenario/twine/README.md) | 合成执行证据或公开上游 PR 说明问题来源；不是硬编码扫描结论 |
| h01 有限修复增量 | [h01记录](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/C-agent/result.json) | 固定启发式 A 未覆盖参数日志，C 候选保留认证并修复日志 |
| h03 反馈修正 | [h03记录](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/result.json) | 候选1真实值仍在；失败回执进入下一请求；候选2通过 |
| h07 正常保持 | [h07材料](materials/h07/README.md) | 无实际泄露证据时无候选补丁，原对象通过 |
| 模型不能自行批准补丁 | [贡献映射](contribution-map.md)、[源码讲解](source-walkthrough.md) | 权限、裁判、隔离和完成状态由程序控制 |
| 交付对象可复检 | [启动入口](startup-modes.md)、[完整批次表](manuscript.md) | 重新读取当前材料；旧报告适用性、历史完整性和新结果分开 |
| 外部接入不是泛化率 | [Twine完整材料](../external-scenario/twine-material-20261003/README.md) | 一个外部组件、七项条件、一次模型任务，单独报告 |

## 评委阅读路径

1. 看作品首页和[一页价值说明](value-and-innovation.md)，先理解使用者和问题时刻。
2. 看 h01，理解固定规则之外的有限候选增量。
3. 看 h03，理解失败证据如何改变后续候选；不要把它当作固定流程失败。
4. 看 h07，确认模型怀疑不会直接造成修改。
5. 点击一次材料复检，确认结果对应当前对象。
6. 最后查看说明书第三章的完整批次表，保留所有失败和未完成任务。

所有材料使用合成凭据或脱敏记录；历史回放、确定性复检和现场模型推理在界面与文档中分开标记。
