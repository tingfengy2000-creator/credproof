# dev32 组件辅助修复证据

本轮准备阶段完成。正式任务尚未运行，状态 NOT_READY_FOR_HANDOFF。后续只追加一次登记任务及结果，不改写历史。

- [最终组件隔离执行](component-controls-final/component-execution.json)：12个pytest用例实际执行，独立认证与跳转回执。
- [汇总与逐项断言](component-controls-final/summary.json)：不同目录名 documents/private、非默认凭据变量；只读组件导入路径与文件摘要。
- [组件已装但工具未改的原件](component-controls-final/unchanged-original-report.json)：仍为FAIL。
- 首次挂载在只读rootfs的 `/opt` 创建目录失败：[原记录](component-controls/component-execution.json)；修正到私有 `/tmp` 的只读最小挂载。没有宿主执行回退。
- [消息预检](preflight/summary.json)覆盖原件、两份保存失败候选与格式纠正；无新推理、无候选执行。使用现有UTF8 wire字节保守上界，不伪造服务token用量。
- [原始到公开派生映射](derivation-preparation.json) / [文件清单](manifest-preparation.json)。原件留本地；公开报告脱敏，源码语义保留。

组件与运行时说明一起改变，不作因果归因或泛化率比较。正式结论、固定源码和安装来源将在同一入口追加。
