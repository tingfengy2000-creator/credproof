# 约定 R4：对照表、外部项目接入、AI 候选进入审阅链

基线：`feat/frontend-human-review-5060` @ `c86dd0b`。三部分互不依赖，可以分开提 PR。字段改动先改本文件。

| 部分 | 5090 负责 | 5060 负责 |
|---|---|---|
| A 真实对照表 | 生成 `docs/compare/comparison.json` 与说明，逐项核对原始记录 | “参考材料”中的对照表页面 |
| B 外部项目接入 | 在 Windows + WSL 实际接入 python-dotenv，生成 `docs/compare/onboarding-dotenv.json`、截图与说明 | 页面展示 |
| C AI 候选进入审阅链（P2） | 后端、现有项目页上的按钮与提示、测试、有模型机器上的验收 | 审 PR，必要时调整样式 |

## A. 真实对照表 `credproof.comparison/v1`

只用已冻结的数据：`docs/bench/bench-results.json`（51 份 AI 补丁 + 16 个锚点 + 21 份历史补丁）与已有外部案例记录。**不重跑、不新增模型调用。**

```json
{
  "schema": "credproof.comparison/v1",
  "generated_from": [{"path": "docs/bench/bench-results.json", "sha256": "…"}],
  "denominators": {"unsafe": 22, "good": 53, "note": "…分组依据与口径…"},
  "methods": [
    {"id": "ci", "label": "业务测试（CI 中的 pytest）",
     "observes": "测试断言是否通过", "does_not_observe": "测试没写到的文件、请求、凭据去向",
     "needs": "项目自带测试", "model_required": false,
     "accepted_unsafe": 0, "rejected_good": 0, "invalid": 0,
     "can_ci_do_this": "是：CredProof 也用同一 pytest；差别在运行时观察",
     "example_patch_id": "…"},
    {"id": "static", "...": "Gitleaks/Bandit/Semgrep 凭据规则"},
    {"id": "judge:qwen2.5-coder:32b-instruct-q4_K_M", "...": "…"},
    {"id": "judge:qwen3-coder:30b", "...": "…"},
    {"id": "credproof", "...": "…，注明“分组依据就是 CredProof 观察到的事实，所以本行按定义一致”"}
  ],
  "honest_limits": ["样本是合成小工具，不代表真实项目分布", "…"],
  "generator": "scripts/compare/build_comparison.py --check 可复算"
}
```

要求：每个数字能由生成脚本从冻结文件复算（`--check` 不一致即退出非零）；每种方法给一个可点开的真实补丁 ID；措辞不贬低其他工具，规范 CI 能做到的写明能做到；不写准确率、不写节省时间。

## B. 外部项目接入 `credproof.onboarding/v1`

对象：`examples/external/python-dotenv-v1.2.2`（固定上游版本）。用 **R4 之后的工作台** 实际操作：上传或授权项目 → 配置向导 → 冻结 → 检查 →（如有）修订 → 导出 → 复检。

```json
{
  "schema": "credproof.onboarding/v1",
  "project": {"name": "python-dotenv", "upstream": "https://github.com/theskumar/python-dotenv", "ref": "v1.2.2",
              "scope": "人工注入的目录越界适配；不是上游漏洞"},
  "environment": {"os": "Windows 11 + WSL Ubuntu-24.04", "python": "3.12.x", "model_calls": 0},
  "steps": [{"id": "prepare", "what_user_does": "…", "time_minutes": null, "artifact": "…", "result": "…"}],
  "config": {"toml_path": "…", "decisions": [{"field": "entry", "why": "…"}]},
  "results": [{"case": "before | after | reintroduced_defect | unrelated_change", "verdict": "FAIL", "failed_conditions": ["…"], "report": "…"}],
  "manual_judgement": ["哪些需要人判断"],
  "not_covered": ["…"],
  "screenshots": ["docs/compare/onboarding-dotenv/*.png"]
}
```

`time_minutes` 只有真实计时才填，否则为 null。失败、环境阻断都如实记录，不删除。

## C. AI 候选进入审阅链（P2）

只在 `--mode live` 且模型就绪时可用；其他模式按钮禁用并说明原因。

- `POST /api/review/<id>/propose`，请求体 `{"expected": {...同既有}}`，要求会话头；与 check 共用 `operation` 锁。
- 前提：当前版本有适用报告且 `technical_verdict == "FAIL"`；否则 409 `propose_requires_current_FAIL`。
- 模型只看到当前版本入口文件、冻结配置的公开字段和**脱敏**的失败条件/事实；看不到合成凭据、测试源码以外的宿主文件。沿用 `bounded_patch` 及其预算与格式接收器。
- 结果：成功时追加新版本 `source = "AI_CANDIDATE"`，`version.json` 增加 `model`（名称与摘要）、`request_sha256`、`response_sha256`、`strategy`；**不自动检查、不自动采纳**，技术结论为 UNKNOWN，直到用户点“运行检查”。模型拒绝、超时、格式不合格时不创建版本，返回 `{"status": "NO_CANDIDATE", "reason": "…"}`，并保存请求/响应收据。
- 审阅视图 `versions[]` 已能显示新来源；前端在“代码与修订”区加按钮“请本地模型提出候选”，版本链显示“AI 候选（本次现场生成）”。
- 验收：同一项目至少一次真实调用；无论候选 PASS 还是 FAIL 都如实记录，不重试挑选；报告里分开写“模型生成”与“开发者修订”的次数和结论。

## 共同规则

不推 main；不改冻结基线；受保护文件由对方审；不上传权重、rootfs、虚拟环境、真实凭据；交付物不出现账号、主机名、用户路径。
