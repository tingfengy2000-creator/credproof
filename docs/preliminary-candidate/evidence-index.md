# 案例证据索引

本文是复查入口，主展示保留简洁；链接均指向已有文件，不是新增实验。原八例批次为 `20260929t095000z-holdout8`，源码 `b4cb91ef67ae2d14d6cc37f9e18cf6c23e36e8ea`。Twine 为 `20261003-live-01` 单次外部任务，执行冻结提交 `64b091f104772ac8eab63ad94b1b28fb61ddb0da`。

## Twine 真实问题与窄组件接入

[来源与许可证](../external-scenario/twine/source.json) · [上游修复 PR 1240](https://github.com/pypa/twine/pull/1240) · [固定需求](../external-scenario/twine/requirements.json)。修复前 `4038f7bdfdad05697510a3f9657bd4fdc7c12d4b`，修复后 `ae1d03bf1f6943c3ffd65597044ccac6294b065e`。不是原生 AI 工具，不是新漏洞、上游采纳或企业部署，不替代官方升级。

| 环节 | 实际动作与依据 | 结果与材料 |
|---|---|---|
| 用户问题 | 配置格式错误令 configparser traceback 携带敏感行进入 stderr；[原件记录](../external-scenario/twine-material-20261003/before.json) | 三类错误输入泄露；两类正常及缺仓库/缺文件四项通过 |
| 已有处理 | 上游新增配置异常转换；[已修版本记录](../external-scenario/twine-material-20261003/upstream-fixed.json) | 七项通过；官方修复本身能够处理问题 |
| 候选1 | [代码](../external-scenario/twine-material-20261003/candidate-1.py)新增 MissingSectionHeaderError 与 ParsingError 两个 handler | 合法语法；超出“至多一个 handler”范围，执行前拒绝，未测其泄露行为 |
| 候选2 | [代码](../external-scenario/twine-material-20261003/candidate-2.py)改为元组异常类型 | 合法语法；类型不在固定轮廓内，执行前拒绝，不能写成仍泄露 |
| 候选3 | [代码](../external-scenario/twine-material-20261003/candidate-3.py)单一 configparser.Error 转换为安全 InvalidConfiguration | [七条件逐项结果](../external-scenario/twine-material-20261003/verification-1.json) PASS |
| 交付 | [完整模型轨迹](../external-scenario/twine-material-20261003/result.json)与[可复检材料](../external-scenario/twine-material-20261003/README.md) | 五调用三候选，全部保留；新目录复检仍执行必要条件 |

七项条件依次为 bare-token、no-section-password、section-bare-token（错误配置不暴露值且仍为领域错误）；valid-pypi、valid-custom（URL、用户名、内部凭据保持）；missing-repository、missing-file（既有错误处理保持）。它们属于一个外部组件，不是七个独立漏洞。新增表达式、原 AST 保留等预设边界见 [external_twine.boundary](../../agent_pilot/external_twine.py)。

## h01 有限候选增量

| 用户问题与原方法 | 我们的动作 | 程序依据与交付 |
|---|---|---|
| 凭据从环境变量进入 helper 的 supplied 参数，再进入日志。A 的局部赋值污点传播不建实参到形参关系，日志识别也未覆盖链式 logger 调用；A 最终仍泄露 | C 新建 redacted 日志值；authenticate(supplied, resource) 保持真实实参 | 十三项条件通过，完成修复任务；仅对本项目启发式有有限增量 |

[固定规则源码](../../agent_pilot/fixed.py) · [A 完整结果](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/A-fixed/result.json) · [C 原件](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/C-agent/original.py) · [C 候选](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/C-agent/candidate-1.py) · [C 结果](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/C-agent/result.json) · [可移交材料](materials/h01/README.md)。未对成熟数据流分析或所有扫描器作此结论。

## h03 脱敏前缀不等于移除秘密

| 用户问题与原方法 | 我们的实际动作 | 程序依据与交付 |
|---|---|---|
| 服务异常经字典进入日志；同轮 A 首补丁已通过 | 候选1将 credential= 替换为 credential=[REDACTED]，后面的值仍存在 | [首次验收](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/verify-1-validation.json)有两个日志泄露反例 |
| 一次看似脱敏的候选仍不合格 | 失败回执进入 [第六次请求](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/model/model-06-request.json) 的 messages[11]；第二候选保留 operation，details 改为固定安全文本 | [第二次验收](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/verify-2-validation.json)十三条件 PASS，交付候选2 |

[首候选](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/candidate-1.py) · [第二候选](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/candidate-2.py) · [完整工具轨迹](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/result.json) · [A 结果](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/A-fixed/result.json)。程序按真实合成值检测；不是因出现字面词 credential。单例不证明反馈普遍领先。D 在 h01/h03 各三份无反馈候选均未修好，但仅最大输出额度相同，非精确等算力对照。

## 正常保留与对象复检

| 需要区分的事实 | 现有依据 | 可以得出的结论 |
|---|---|---|
| h07 模型疑点 / 程序确认 / 修改 | [h07 原始结果](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h07/C-agent/result.json)，零候选，原件十三条件通过 | 正常代码保持，不是“危险补丁遭拒”，也不是模型普遍零误报 |
| 无证据提案由程序阻断 | 同批 [h05 A-fixed](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/A-fixed/result.json)的拒绝记录；[authority/submit](../../agent_pilot/reliability.py) | 这是固定启发式误提案被拦截，不能记为模型无误报 |
| 当前代码变化后旧结论不能沿用 | [对象绑定回归](../../agent_pilot/tests/test_web_material_binding.py)及[既有实际变化记录](../../experiments/preliminary-candidate/20260929T140358Z-release-check/changed-copy-result.json) | 对象漂移需重新核验；不等于变化本身必然使补丁失败 |
| 缺可选轨迹与当前复检分离 | [缺轨迹实测](checks/bundle-integrity/20260929T135515Z/missing-optional-trace-recheck.json)、[完整性代码](../../agent_pilot/bundle.py) | 显示 DEGRADED，不冒充证据齐全；新判决仍按实际执行 |
| 新目录移交 | [preliminary.4 的实际包后复检](delivery-receipts/preliminary-4/README.md) | 无模型复检可行；同机 WSL 环境，非跨机证明 |

## 完整口径及已知方法

[八例完整记录](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/results.json) · [已有官方资料与原论文核查](../preliminary/01_related_work_and_template.md) · [方法代码](../../agent_pilot/reliability.py)。A/B/C 问题修复 3/4、1/4、4/4；完整任务 7/8、4/8、6/8。未完成、原始疑点和失败都保留。扫描器已有能力不写成缺陷，规范 CI 与本方法有重合；未对现成修复 Agent 作产品排名。

## 增强候选版项目接入现场记录

本轮没有新模型任务。页面在启动时登记的两个合成项目上调用同一后端：问题版本 [返回 FAIL](../../experiments/reusable-tool-safety/20261005-enhanced-candidate-v2/project-entry-check-preliminary8.json)，人工预置修复示例 [返回 PASS](../../experiments/reusable-tool-safety/20261005-enhanced-candidate-v2/project-entry-check-preliminary8.json)。导出响应的 [字节与 SHA-256 收据](../../experiments/reusable-tool-safety/20261005-enhanced-candidate-v2/project-entry-export-preliminary8.json)对应 2,226 字节 ZIP；导出测试的 [逐副本结构化记录](../../experiments/reusable-tool-safety/20261005-enhanced-candidate-v2/exported-regression-v6/summary.json)要求固定/无关副本各有一个真实通过目标，缺陷副本有一个真实断言失败并生成 FAIL 报告。
