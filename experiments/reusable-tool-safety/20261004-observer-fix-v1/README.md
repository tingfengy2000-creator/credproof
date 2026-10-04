# 2026-10-04 observer-fix-v1

本目录保存本轮定向回归的脱敏摘要。所有运行使用合成凭据、受控 WSL/bubblewrap
副本和本地 mock；没有调用模型。完整原始报告仍保留在本机 `_runs/`，本目录只保留
可公开复查所需字段，不包含路径、账户或秘密值。

## 命令

```powershell
$env:PYTHONPATH = (Get-Location).Path
.venv\Scripts\python.exe -m credproof_safety check --config _runs/all-skipped-fixture-v1/credproof.toml --output _runs/all-skipped-fixture-v1/report.json
.venv\Scripts\python.exe -m credproof_safety check --config _runs/missing-required-fixture-v1/credproof.toml --output _runs/missing-required-fixture-v1/report.json
.venv\Scripts\python.exe scripts/run-exported-regression-check.py --output _runs/exported-regression-after-observer-fix-v3
```

## 结果

| 检查 | 结果 | 证据含义 |
| --- | --- | --- |
| 正常 pytest | `PASS` | 必要路径收集 1、执行 1、通过 1 |
| 全跳过 pytest | `UNKNOWN` | 进程退出 0，但收集 1、执行 0、跳过 1，不能作为业务通过 |
| 缺失必要路径 | `UNKNOWN` | `tests/missing_test.py` 未收集，不能以入口返回值制造 PASS |
| 仅导入时输出合成凭据 | `FAIL` | 模块首次导入阶段的 stdout 被捕获，`credential_leaks=["stdout"]` |
| 外部消费者固定副本 | `PASS` | 普通 pytest 1/1 通过，随后真实隔离检查 PASS |
| 外部消费者重新引入文件缺陷 | `FAIL` | 普通 pytest 1/1 失败，真实隔离检查拒绝越界读取 |
| 外部消费者无关文件变化 | `PASS` | 普通 pytest 1/1 通过，不因树哈希变化误报 |

`all-skipped-fixture-v1` 和 `missing-required-fixture-v1` 的入口返回值仍然正常，
这正是本回归要证明的边界：业务测试证据缺失时整体为 `UNKNOWN`。导入输出样例的
测试实际 1/1 通过，但安全通道泄露使结果为 `FAIL`。
