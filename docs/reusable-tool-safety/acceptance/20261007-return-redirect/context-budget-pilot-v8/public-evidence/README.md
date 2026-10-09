# v8：失败候选后的受限修订任务

状态：`NOT_READY_FOR_HANDOFF`。本轮只运行一次新的模型任务，未得到合格候选；不启动 5060 交接。

## 本轮关闭和未关闭的事项

v7 第 7—9 次实际请求已包含候选正文、FAIL、业务要求、读取配对和主机状态，见 [逐请求诊断](../../context-budget-pilot-v7/public-evidence/revision-stage-diagnosis/)。本轮不再把失败归因于源码被压缩器丢失。

当前执行器把自动 FAIL 后的修订阶段限制为提出不同补丁或停止：当前源码、规则、测试、失败反馈由程序提供；重新取同对象证据/读取会明确拒绝，两次无进展动作后停止。反馈提供禁止文件尝试、禁止服务回执及认证信息、场景不符和必要业务测试的实际事实，没有提供参考补丁。实现见仓库根目录 `credproof_safety/agent.py` 的 `_model_actionable_failures`、`_model_work_feedback`、`_phase_rejection` 和执行器；模型工作摘要与完整审计报告分开保存。

这证明修订阶段控制实际执行，不证明模型已经完成修订。本次模型收到 FAIL 后仍请求读取、取证，没有提交第二份实质性修改。

## 阅读顺序

1. [冻结记录](freeze.json)、[实际命令及退出码](command-receipt.json)、[逐任务汇总](summary.json)。实际被测源码：`d352e97088a56719a7495c206fa86680355ed8ca`。本目录随后添加的公开证据与文档不属于模型运行前的源码提交。
2. [候选 1 完整源码](candidate-01.py)、[原问题报告](initial-report.json)、[候选实际验收](verification-01.json)。候选只移除了日志中的凭据，仍返回凭据，文件与跳转边界未修好。业务、安全条件均未全部满足。
3. [实际第 4 次请求](model-trace/model-04-request.json) / [响应](model-trace/model-04-response.json)，以及 [第 5 次请求](model-trace/model-05-request.json) / [响应](model-trace/model-05-response.json)。可检查模型实际看到的候选、具体失败、状态和收到拒绝后的行为。[实际请求内容核查](actual-request-inspection.json) 对两份实际请求逐项核对候选、测试、FAIL、反例、调用配对和余额。[完整工具轨迹](tool-trace.json) 保留原调用 ID、真实状态和原因。
4. [当前协议预检](protocol-preflight-final/summary.json)：6 个现有真实历史状态与当前协议派生分支全部通过，0 推理、0 候选执行；输入保守上界分别为 4,870 / 13,874 / 14,071 / 14,353 / 14,353 / 14,560，限制 14,848。方法为 `UTF8_WIRE_BYTES` 上界，不是服务实测 token。对应待发 payload 在同目录。此前较大反馈的 [失败预检](protocol-preflight/summary.json) 原样保留。
5. [软件定向回归](regression-receipt.json)、[stdout/stderr](regression.txt)、[JUnit](regression.junit.xml)。这是消息、权限、场景与 bundle 软件回归，不是新增安全样本或模型能力成绩。
6. [GPU 依据](device-evidence.json)、[边界探针](model-boundary.json)、[派生说明与原件摘要](derivation-receipt.json)、[文件清单](manifest.json)。

## 真实结果与预算

| 项目 | 实际值 |
|---|---:|
| 模型请求 / 响应 / usage | 5 / 5 / 5 |
| 模型工具请求 | 6 |
| 接受候选 / 程序自动验收 | 1 / 1 |
| 合格候选 / 导出 / 新目录复检 | 0 / 0 / 0 |
| 任务终态 | INCOMPLETE / STOPPED_NO_PROGRESS |

剩余工具 6 次、候选 2 份、验收 2 次、模型请求 7 次。本次不是预算耗尽或请求超时。候选验收为 FAIL；后续 `read_code` 为 `revision_source_already_current`，再取证为 `no_progress_revision_action`（原因为 `revision_evidence_already_current`）。未追加模型运行。

固定上限：模型 12、工具 12、候选 3、程序验收 3、格式纠正 1、单请求 120 秒、任务 900 秒；16K 上下文与输出/安全预留保持不变。实际推理日志为 CUDA0 / RTX 5090、49/49 层卸载；模型、执行与网络白名单保持既有隔离。此前一次宿主权限下无法访问 WSL 的 [准备阻断](pre-model-blocked.json) 为 0 推理，单独保留，不算模型失败。

## 证据边界

公开 JSON 是结构化脱敏派生件；只替换确切本机路径前缀和合成值，源码、状态、原因及调用关系保留。原始与公开摘要/字节分别记录，公开大小不冒称原始发送大小。当前候选尚无 PASS，因此没有同对象公开 bundle 复检、也没有本轮最终安装/页面修复成功收据。旧已闭合的对象绑定、发布字节和解释器选择保持原证据，不重开。仍缺当前模型的合格修复以及随后同对象复检；阶段拦截成功不能替代这项效果。
