# 2026-10-05 pytest necessary-case acceptance regression

本目录记录 `0.3.0-dev.9` 候选提交中对 pytest 必要用例判定的定向修正。它使用真实
CredProof 执行器、真实 pytest 插件回调和实际 `_verdict`，不是手工构造
`required_tests_completed` 字段。所有项目均为合成小型项目，没有调用模型和真实凭据。

## 运行环境与命令

- Windows Python：3.12.14 (AMD64)
- pytest：8.4.2（项目锁定环境）
- 命令：`python scripts/run-pytest-observer-regressions.py --output _runs/pytest-observer-regressions-v5`
- 结果由各例 `report.json` 的 `execution.pytest_observation` 自动汇总；原始报告和可运行 fixture 在 `pytest-cases/`。

## 逐例结果

| 案例 | pytest 观察 | 实际 verdict | 关键含义 |
| --- | --- | --- | --- |
| `normal_pass` | 1 collected / 1 executed / 1 passed | PASS | 必要用例真实执行并通过 |
| `partial_required_skip` | 2 / 1 / 1 passed / 1 skipped | UNKNOWN | 同一必要文件中仍有必要用例未执行，不能因退出码 0 放行 |
| `all_required_skip` | 1 / 0 / 0 passed / 1 skipped | UNKNOWN | 全部必要用例跳过 |
| `required_xfail` | 1 / 1 / 0 passed / 1 xfail | FAIL | 必要用例执行但没有通过；pytest 退出码仍为 0 |
| `missing_required` | 0 collected，必要路径缺失 | UNKNOWN | 未收集到必要用例 |
| `required_assertion_failure` | 1 / 1 / 1 failed | FAIL | 必要断言失败 |
| `optional_skip` | 必要 1 passed；可选 1 skipped | PASS | 只有配置中预先声明的可选路径可跳过 |

`optional_tests` 是可信配置的一部分，模型不能修改；导出的递归保护测试明确列为
可选包装检查，不能和必要业务用例混淆。必要测试以 nodeid 逐项记录 setup/call/teardown、
skip、xfail、xpass 和失败状态。

## 导出消费者回归

`exported/summary.json` 及同目录逐例 JSON 来自独立短路径消费者副本，使用正常
`python -m pytest` 收集和执行导出测试，不启动模型：

- `external_fixed`: 1/1，退出 0，`PASS`
- `reintroduced_defect`: 1/1，退出 1，`TEST_FAILURE`
- `unrelated_change`: 1/1，退出 0，`PASS`

`verification_status` 同时检查 JUnit 是否存在、测试是否实际收集、skip/error 和退出码，
不再把“全部 skip + 退出 0”当作成功。

## 外部既有记录

`external-dotenv-summary.json` 仅作为本轮观察语义变更后的定向重算：python-dotenv
固定副本的 before 为 FAIL、人工固定副本为 PASS、重新引入缺陷为 FAIL、无关变更为 PASS。
它不是新模型调用，也不改写历史 Agent 记录。

本目录中的报告仅支持声明的合成场景。隔离依赖 WSL/bubblewrap/rootfs 的检查仍按项目
README 说明；缺少隔离时不能降级到宿主机执行不可信代码。
