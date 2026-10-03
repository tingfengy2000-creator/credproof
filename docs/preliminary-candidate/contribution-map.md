# 贡献与证据映射

本表把“主张”限制在已经实现和已记录的范围内。开源模型、Agent 框架、推理服务、隔离工具和上游组件均按来源归属，不计为本项目原创算法。

| 具体困难 | 本项目设计 | 自行实现的部分 | 相比明确基线多做的一步 | 案例与证据 | 适用边界 |
|---|---|---|---|---|---|
| 模型提出的修复可能只处理表面文本，不能说明问题是否真的消失 | 先执行受控触发，再把脱敏证据和失败回执反馈到候选生成 | `agent_pilot/reliability.py` 的 `GovernedSession.initialize`、`run_method`；`model_client.py` 的本地会话记录 | 相比一次性模型修复，允许在当前候选的真实检查结果返回后再调整一次 | h03 候选1保留真实值，失败回执进入下一请求，候选2改为固定安全错误信息并通过；[h03 原始候选与请求](evidence-index.md) | 只证明一次真实反馈调整，不证明普遍优于一次性模型 |
| 模型建议不能自行获得写入和“通过”权限；安全修复也可能破坏业务行为 | 当前副本、允许范围、禁止通道和必要业务条件由执行侧固定 | `reliability.py` 的 `authority`、`submit`、`check`；`judge.py` 的 `validate_source`、`judge_trial`；`isolation.py` 的 `run_isolated` | 相比“模型说已修复”或仅复扫，程序同时检查泄露、认证调用、成功响应、拒绝、服务异常和修改边界 | h01 认证保持而参数日志被修好；h07 无证据时原对象保持；Twine 前两候选被边界拒绝、第三候选通过七项条件 | 只覆盖固定的受控 Python 接口和检查矩阵，不能替代通用语义等价证明 |
| 绿色报告可能对应错误副本，后来修改后仍被沿用 | 导出和复检绑定原件、当前候选、规则及记录，重新执行必要检查 | `agent_pilot/web.py` 的 `_material`、`_require_current_material`；`agent_pilot/bundle.py` 的 `recheck_bundle`、`_historical_integrity` | 相比保存一个 PASS 字段，重新核对对象适用性、历史完整性和当前结果，并在变化后拒绝旧缓存复用 | 对象变化定向回归；h01/h03/h07 与 Twine 均有可移交材料和独立复检入口 | 普通哈希只检测相对清单的变化，不是第三方认证或不可伪造证明 |

## 三类角色的边界

- **人工**：确认授权范围、输入输出契约、禁止输出通道、必要业务条件和最终参赛/发布决定。
- **固定程序**：生成初始受控证据，校验工具协议、路径和权限，执行隔离运行，判定安全与业务条件，绑定材料并控制任务结束。
- **本地模型**：阅读已授权代码和脱敏观察，提出触发假设，选择结构化工具并生成候选补丁；不能修改裁判、需求或隔离设施，也不能直接指定 PASS。

## 证据索引

| 主张 | 代码 | 记录 |
|---|---|---|
| h01 有限修复增量 | `agent_pilot/reliability.py`、`agent_pilot/judge.py` | `experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/C-agent/result.json`、`docs/preliminary-candidate/materials/h01/` |
| h03 反馈调整 | `agent_pilot/reliability.py`、`agent_pilot/model_client.py` | `experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/result.json`、`candidate-1.py`、`candidate-2.py`、`model/model-06-request.json` |
| h07 无证据不改 | `agent_pilot/reliability.py`、`agent_pilot/judge.py` | `experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h07/C-agent/result.json`、`docs/preliminary-candidate/materials/h07/` |
| Twine 外部组件 | `agent_pilot/external_twine.py` | `docs/external-scenario/twine/README.md`、`docs/external-scenario/twine-material-20261003/` |
| 对象绑定和复检 | `agent_pilot/web.py`、`agent_pilot/bundle.py` | `agent_pilot/tests/test_web_material_binding.py`、`agent_pilot/tests/test_bundle.py`、`docs/preliminary-candidate/delivery-receipts/preliminary-4/` |

原八例完整口径仍以 `manuscript.md` 第三章为准：问题例合格修复 A/B/C 为 3/4、1/4、4/4；最终对象通过为 7/8、5/8、8/8；完整任务为 7/8、4/8、6/8。精选案例不替代完整批次，Twine 不并入分母。

所有可点击的候选、请求、检查结果和来源统一见[证据索引](evidence-index.md)。现成工具能力沿用[已有官方核查](../preliminary/01_related_work_and_template.md)，不把未实测写成缺陷。
