# CredProof 0.1.0-review.1 研发评审入口

这是**研发评审 Pre-release**，不是比赛终版，也不表示作品或外部审查已经通过。请从本页进入源码与证据；历史设计文档不代表所有功能已实现。本页、链接目标和发布 ZIP 应取同一标签 `v0.1.0-review.1` 或对应完整提交，不能混用 main。

## 1. 先明确完成度和争议

| 状态 | 本版实际内容 |
|---|---|
| 已实现 | Python CLI、真实 worktree/index 分开只读、单处受限赋值的副本修复、五项检查、逐项证据绑定、PASS/FAIL/UNKNOWN、脱敏记录及材料复检 |
| 有历史实测记录 | Gitleaks 8.28.0 下 16 个开发案例 × 3 次重复；完整 48 条记录含 A/B/B-fresh/C/C-no-binding、独立断言、错误字段和剩余风险。另有三段演示原始公开 JSON |
| 本次发布复现 | 从标签源码构建 ZIP，再在无项目 `.git` 的独立目录创建新虚拟环境运行；实际命令、退出码、stdout/stderr 见 Release 附件 `reproduction.json`。失败不能用预期值代替 |
| 未完成 | **B-strong、独立模板留出评测、真实前端/API、React 工程/锁文件、FastAPI 服务、模型接入、通用凭据或任意项目修复、跨平台发布验证** |
| 仍有争议 | 精确允许编辑能否泛化；额外收益是否超过规范 CI；开发可见案例的偏差；正确但写法不同的补丁通过率。本轮不借发布来补造这些结论 |

实现版本字符串仍为 `0.1.0-pilot`；`0.1.0-review.1` 是本次评审快照版本，见 [review-version.json](../../review-version.json)。核心、检测适配器、历史实验协议和实验脚本未为这次发布改变算法或标签。

## 2. 推荐阅读顺序

1. [本页的证据映射](#3-结论到具体证据)与[案例 CSV](cases/case-index.csv)：先辨别实际支持的结论。
2. [core.py](../../credproof/core.py)、[scanner.py](../../credproof/scanner.py)、[CLI](../../credproof/__main__.py)：审核对象、范围、义务、判决和复检。
3. [回归测试](../../tests/test_core.py)、[演示脚本](../../scripts/demo.py)：正反例、原件保护和不执行任意代码的实现。
4. [机器可读协议](../../experiments/protocol.json)、[实验 runner](../../experiments/pilot.py)、[协议说明](../preliminary/02_experiment_protocol.md)：独立 oracle、同范围比较、故障注入与 B-fresh。
5. [历史实验汇总](../../experiments/results/20260929T014733Z_00c48b93/summary.md)、[完整原始结果 JSON](../../experiments/results/20260929T014733Z_00c48b93/results.json)、[完整逐案例索引](case-index.md)：不能只读成功案例。
6. [初赛收敛设计](../preliminary/00_positioning_and_plan.md)、[相关工作](../preliminary/01_related_work_and_template.md)、[结果解读与讲稿](../preliminary/03_results_and_demo.md)、[主图](../preliminary/diagrams/mechanism.png)。

原始 `results.json` 约 1.1 MB；若 GitHub 页面省略大文件，请取 Raw，或使用每例三个重复均保留的 [拆分 JSON](case-index.md)。拆分由 [export-review-evidence.py](../../scripts/export-review-evidence.py) 从原记录提取，文件含原始 SHA-256 和零起始 trial 索引；没有重跑、改判决或丢字段。CSV 仅导航，不能代替完整记录。

## 3. 结论到具体证据

下表的测试函数都在 [tests/test_core.py](../../tests/test_core.py)。部分测试与 pilot 是同机制不同变更，不把它们冒充同一实验样例。

| 贡献或结论 | 源码路径及函数 | 对应测试函数 | 逐案例依据 |
|---|---|---|---|
| 真实读取两来源、原件不写回 | `credproof/core.py`：`_capture`、`freeze`、`_remaining` | `test_planned_edit_passes_without_modifying_originals`、`test_index_and_worktree_capture_different_real_content` | [good-basic](cases/good-basic.json)、[index-residual-local-pass](cases/index-residual-local-pass.json) |
| 正确修复可通过，零告警但功能破坏被拒绝 | `core.py`：`_planned`、`_function`、`collect`、`assess` | `test_planned_edit_passes_without_modifying_originals`；演示脚本含独立期望断言 | [good-basic](cases/good-basic.json)、[constant-zero-alert](cases/constant-zero-alert.json) |
| **B 接受、C 拒绝的正常案例**来自允许编辑限制 | `core.py`：`collect` 内 `changes`、`assess` | `test_extra_change_invalidates_old_evidence_and_fresh_check_fails` 修改附属常量；`test_recheck_ignores_deleted_or_forged_saved_verdicts` 含 notes 修改 | [unrelated-change](cases/unrelated-change.json)，原 trials **7/23/39**；C 的 `allowed_changes.reason=outside_frozen_edit` |
| 每项回执不能跨对象/范围/规则拼接 | `core.py`：`_binding`、`assess` | `test_scope_rules_and_cross_contract_receipts_are_not_interchangeable` | 下表六个异常；注意单 scan 的范围/规则拼接以 pilot 为精确证据 |
| 缺义务不是成功；旧通过不能用于新对象 | `core.py`：`collect`、`assess` | `test_missing_required_obligation_cannot_become_pass`、`test_extra_change_invalidates_old_evidence_and_fresh_check_fails` | [function-not-checked](cases/function-not-checked.json)、[stale-pass-replay](cases/stale-pass-replay.json) |
| 复检重新执行，而非显示保存的 PASS | `core.py`：`recheck`；`__main__.py`：`main` | `test_recheck_ignores_deleted_or_forged_saved_verdicts` | [历史演示新检查](evidence/demo-20260929t014345z/04-rechecked-drift-report.json)；发布复现另执行 CLI |
| 副本 PASS、原 index 残留、撤销未知可以同时成立 | `core.py`：`_remaining`；`pilot.py`：`run_trial` 的独立来源断言 | `test_planned_edit_passes_without_modifying_originals`、`test_current_source_change_is_reported_without_overriding_local_acceptance` | [index-residual-local-pass](cases/index-residual-local-pass.json) 的 `remaining_risks`、`remaining_risks_match_oracle` |
| 残留/脱敏/任意代码边界 | `core.py`：`_removal`、`_redact`、`_function` | `test_decoded_residual_and_comment_residual_fail_without_public_plaintext`、`test_unknown_function_profile_and_hostile_file_are_never_executed` | 主要为回归测试证据，不混入 16 例统计 |

六个证据异常的原因分别如下。**补丁不合格**与**证据不足/过期**分开计数。

| 案例及三轮原 trial 索引（零起始） | C 为什么 UNKNOWN | B / B-fresh |
|---|---|---|
| [scope-omission](cases/scope-omission.json)：8/24/40 | 全部检查的实际范围漏 notes.txt，scope 绑定不适用 | PASS / 重采完整证据后 PASS |
| [function-not-checked](cases/function-not-checked.json)：9/25/41 | 功能检查未执行，缺必要证据 | UNKNOWN / 补查后 PASS |
| [stale-pass-replay](cases/stale-pass-replay.json)：12/28/44 | 采证后修改了候选行为，五项旧 candidate 绑定失效 | PASS / 重新测试后 FAIL |
| [cross-object-evidence](cases/cross-object-evidence.json)：13/29/45 | 只有 scan 回执来自另一 contract | PASS / 本身正确的当前副本 PASS |
| [cross-scope-evidence](cases/cross-scope-evidence.json)：14/30/46 | 只有 scan 回执来自窄范围 | PASS / 当前完整范围 PASS |
| [cross-rule-evidence](cases/cross-rule-evidence.json)：15/31/47 | 只有 scan 回执来自另一配置摘要；donor **仅加注释、检测语义未变** | PASS / 当前正确配置 PASS |

模式定位：A=仅 scan；B=scan/syntax/function 的给定回执聚合；C=五项义务加逐项绑定；C-no-binding=移除逐项绑定，但仍保留公共 `_load` 契约/原件检查，**不是去掉所有完整性保护**。B-fresh 在 `pilot.py:run_trial` 重新采集完整当前范围，然后调用 B，并按新的独立 oracle 评价；它不是 `assess` 的第五个 mode。B-strong 未实现。正常同范围十例中，B 比 C 多接受的只有 `unrelated_change`；不能推导超过约束相同的完整 CI。

## 4. 干净环境复现（Windows）

需要自行安装 Python（历史实验为 3.12.14，先前 CLI 为 3.14.7）与 Git，并使二者在 PATH。**不需要本机原环境、GitHub 登录、Token、GPU、云模型、Node 或原仓库 `.git`。** Python 代码只用标准库，没有遗漏的 pip 依赖/锁文件。第一次需要公开网络下载 Gitleaks 8.28.0；下载器保留许可证并核对官方同 release 的 checksum。

从 Release 下载 ZIP 与 `manifest.json`、`sha256sums.txt`，先用 `Get-FileHash <实际ZIP文件名> -Algorithm SHA256` 比较外部校验，再解压，进入含 `credproof/`、`scripts/` 的根目录。以下命令在该目录执行：

```powershell
python scripts/verify-review.py
python -m venv .venv
.\.venv\Scripts\python.exe scripts/get_gitleaks.py
.\.venv\Scripts\python.exe scripts/run-review-checks.py
```

先验证清单，再创建 `.venv`/`.tools`/`runs`；严格清单验证会拒绝新增文件，不能把生成文件混成原始快照。`run-review-checks.py` 会留存全新记录并执行：Git/扫描器版本检查、10 项回归、三段演示、旧证据复核（预期退出 2）、漂移后重新验收（退出 1）、新正确副本复检（退出 0）、16 案例 × 3 次新复现。任何意外退出码或测试 skip 都失败；控制台打印记录位置。需要显式更新依赖，不提供静默模拟替代。

可独立运行的原有入口：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/demo.py
.\.venv\Scripts\python.exe experiments/pilot.py --gitleaks .tools/gitleaks-8.28.0/gitleaks.exe --output runs/reproduced-pilot --repeats 3
```

演示末行给出新生成的 bundle 路径。它故意停在额外修改后，以下 recheck 应 **FAIL/退出1**；这不是启动失败：

```powershell
.\.venv\Scripts\python.exe -m credproof recheck --bundle "<演示打印的bundle路径>"
```

该命令会重新读材料、执行检查并生成 `public/check-*/report.json`、`evidence.json` 和 `contract-view.json`。`validate-evidence` 仅判断已有回执适用性，不能称为重新采证。`freeze` 退出 0 只表示生成副本，不能称为验收 PASS。完整 CLI 参数见 `python -m credproof --help`；顶层 `--gitleaks/--config` 必须放在子命令之前。

**真实界面：未实现，因此没有可验收的前端构建/启动命令。** 若只想阅读保留的历史模拟原型，可运行 `python -m http.server 8800 --bind 127.0.0.1 --directory docs/plan-v2` 并打开 `http://127.0.0.1:8800/prototype/index.html`，它不接真实数据，不计入功能复现。主机制图可直接读 PNG/SVG，无需本地渲染脚本或其可选依赖。

仅声明已实际验证的 Windows 环境，其他平台未验收。符号链接测试依赖系统权限；如果出现 skip，应报告未完成，不说全部通过。

## 5. 数据、历史与发布完整性

- 16 个案例全部开发可见，三个源模板参与开发，**不存在独立留出**。三次重复只测稳定性，仍是 16 个独立定义的案例，不是 48 个独立模板。
- 原历史结果、协议和汇总按原始字节保留，记录了当时的源码 SHA 和提交。拆分文件覆盖全部记录；生成脚本校验重组后与源 JSON 结构完全相同。
- [历史演示记录](evidence/demo-20260929t014345z/source-provenance.json)复制九份原公开 JSON，记录 SHA；没有重新生成。原 `story.json` 含本机旧路径，未发布；改用包内脚本，不反向编造日志。
- 过去的 10 项测试在工具会话有通过报告，但没有单独归档的 JUnit/完整 stdout 文件；本次独立复现会新建实际命令记录，不能冒称它是旧日志。
- 不发布主项目 `.git`、原始 before/private witness、缓存、`.tools`、虚拟环境、Token 或真实 `.env`。所有凭据形状都是不可认证的合成 `CP_SYNTH_`；样例 Git 仓库与暂存状态由 `demo.py` 和 `pilot.py` 重新创建。随机 run ID/HMAC、对象摘要和耗时不要求跨次字节相同。
- 仅凭公开历史 JSON 无法对原本机旧 bundle 直接执行 recheck；它可以审计历史统计。外部执行脚本生成**新受控材料**来复现机制判决，这个限制不隐瞒。
- 打包工具 [build-review.py](../../scripts/build-review.py) 从指定 Git 提交字节生成，不复制任意工作区。包内附加 manifest/发布元数据与外部 manifest 一致；清单不递归计算自身哈希，ZIP 校验在外部 `sha256sums.txt`。
- 最终 SHA/生成时间/文件校验/构建环境写入发布元数据，避免把同一提交 SHA 写回自身引起循环。发布后的匿名获取记录是路径可用性检查，**不等于 ChatGPT 已读取或已验收**。

## 6. 尚未通过的验收与归属

B-strong、独立留出、更多语义等价正确补丁、真实凭据检测效果、大项目开销、真实前端、其他操作系统都仍缺证据。范围最多 32 个 UTF-8 文件、每个 128 KiB；修改仅一处受限赋值，受控功能也仅支持闭合语法。过期/错绑回执会 UNKNOWN，原值撤销仍 UNKNOWN，历史未扫描；不输出事件已经解决的结论。

普通摘要和本地 HMAC 不是密码学证明、签名或第三方认证，不能阻止控制全部本机材料的人一起伪造。报告复检须获得匹配材料。检测器复用 Gitleaks、读取复用 Git；新增工程机制与案例、文稿使用 Codex 辅助完成。详见 [归属说明](../../THIRD_PARTY_NOTICES.md)。本版只公开评审相关内容，不制作比赛终版包或匿名申报材料。
