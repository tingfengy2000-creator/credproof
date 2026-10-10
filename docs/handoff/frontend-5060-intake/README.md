# 5060 接收核对：前端交接 `5b3ff23e`

**结论：交接已接收，可以开始前端开发；同时发现 1 项受保护后端的跨平台问题，需要 5090 评审处理。** 本轮新增模型调用、候选执行、安全实验、真实审批、真实导出均为 **0**。没有修改任何受保护路径，也没有修改 `docs/handoff/frontend-5060/`。

- 接收分支：`feat/frontend-human-review-5060` @ `5b3ff23ee078d9070da5d61cf2bca93d17813465`（与 5090 通报一致）
- 冻结基线 `81c289fd…`、被测源码 `50e0d694…`：两个提交对象均已取得
- 5060 环境：Linux x86_64，Python 3.12.3，新建最小 venv，仅 `pip install --no-index --no-deps` 原 wheel
- 开发者：tingfeng 开发项目，部分 AI 辅助。5060 是 tingfeng 的第二个开发环境（前端与文档），不新增团队成员；AI 辅助开发参赛许可已由 tingfeng 确认。

## 核对结果

| 项目 | 结果 | 依据 |
|---|---|---|
| wheel SHA256 `ced6f433…` | 一致 | `sha256sum` |
| 收据列出的 6 个程序文件 + 3 个交接脚本哈希 | 全部一致 | `sha256sum` |
| `verify-evidence.py` 既有证据对应 | **PASS**（exit 0） | [evidence-match-linux.json](evidence/evidence-match-linux.json) |
| `test-readonly.py` 只读传输测试 | **4/5 通过，1 项 FAIL**（exit 1）；所有禁止操作调用均为 0 | [readonly-check-linux.json](evidence/readonly-check-linux.json) |
| 浏览器打开 `#human-review` → 读取已有修订 | 页面显示「程序 UNKNOWN · 人工 PENDING · 原仓库未应用」及原因 `final_validation_project_tree_mismatch` | [截图](evidence/readonly-ui-linux.png) / [页面文字](evidence/readonly-ui-linux.txt) |

前端行为本身是正确的：后端给出 UNKNOWN 时，页面如实显示 UNKNOWN 与原因，没有沿用旧 PASS。失败的测试是 `test_history_fields_without_model_or_isolation_probe`，它期望 `PASS/PENDING/NOT_APPLIED`，Linux 上得到 `UNKNOWN/PENDING/NOT_APPLIED`。

## 发现：项目树摘要依赖宿主操作系统

`credproof_safety/project.py:_digest_tree` 对 `sorted(root.rglob("*"))` 生成的**有序列表**求哈希。`WindowsPath` 排序不区分大小写，`PosixPath` 区分大小写。v001 项目有 `README.md` 和 `credproof.toml`：

| 排序方式 | 文件顺序 | 摘要 | 与报告 `d323b459…` |
|---|---|---|---|
| Linux 原生（区分大小写） | README.md, credproof.toml, tests/…, tool.py | `77b50130…` | 不一致 |
| Windows 原生（折叠大小写） | credproof.toml, README.md, tests/…, tool.py | `d323b459…` | **一致** |

复现：`python -I docs/handoff/frontend-5060-intake/tree-order-repro.py`（只读取快照字节，不执行项目代码）→ [tree-order-linux.json](evidence/tree-order-linux.json)

**影响：** 文件字节完全相同，但在 Linux/macOS 上，`view()` 判定报告不适用 → UNKNOWN。评审如果在非 Windows 机器上运行只读入口或公开复检，会看到正式对象「未验收」，与材料中写的 PASS 不符。这会直接动摇「同对象可复检」这一核心卖点。这是失败安全方向（不会误判 PASS），但会让结论无法跨平台复现。

**同类写法：** `scripts/derive-project-public-bundle.py:digest_tree` 实现相同。`agent.py:candidate_immutable_digest` 只在同一主机内前后比对，zip 写入顺序只影响条目顺序，判定不受影响。

**建议修复（受保护路径，由 5090 决定和验证）：** 显式使用与 Windows 现有顺序相同的排序键，保证已有 Windows 摘要不变，Linux/macOS 结果与之一致：

```python
def _tree_order(root):
    return lambda p: ([s.lower() for s in p.relative_to(root).parts], p.relative_to(root).as_posix())

for path in sorted(root.rglob("*"), key=_tree_order(root)):
```

第二个键只用于区分在 POSIX 上仅大小写不同的文件名，Windows 上不存在这种情况。修复后建议 5090 至少验证：正式对象 939e25f4 在 Windows 上摘要仍为 `d323b459…`；`test-readonly.py` 在 Linux 上 5/5；`derive-project-public-bundle.py` 同步修改；公开复检在同一对象上仍为 RECHECKED/PASS。如果不修复，交接 README 和比赛文档需要写明「复检需在 Windows 上进行」。

## 下一步（5060）

1. 等 5090 对上述问题给出处理意见；前端工作不依赖它，同时开始。
2. 前端重构只改 `agent_pilot/ui/index.html`、`styles.css`、`app.js` 及对应静态/UI 测试，每个 PR 附截图、只读测试结果与待 5090 动态验证项。
3. 已观察到的界面问题（后续 PR 处理）：首页长、信息密度高，审阅区三个独立状态不够醒目；多数操作按钮在只读模式下仅靠后端 405 拒绝，界面没有提前说明。
