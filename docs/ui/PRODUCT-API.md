# 产品工作区接口约定（P1）

本文件先于实现确定，前端只按这里的字段工作；字段变化必须先改本文件。

## 1. 用户真实流程

| 步骤 | 页面 | 接口 | 是否执行代码 |
|---|---|---|---|
| 0 看懂产品 | `#home` 真实案例 | 无（静态内容，数据取自已保存记录） | 否 |
| 1 确认环境 | `#environment` | `GET /api/workspace/status` | 否（只读文件观察） |
| 2 接入项目 | `#new` 选择来源 | `POST /api/intake/upload`、`POST /api/intake/example` | 否 |
| 3 填写配置 | `#new/<intake>` 配置向导 | `GET /api/intake/<id>`、`POST /api/intake/<id>/config` | 否（只做静态解析和配置校验） |
| 4 建立审阅对象 | 同上，“冻结配置并开始” | `POST /api/intake/<id>/start` → 审阅 ID | 否 |
| 5 隔离检查 | `#project/<review>` | 既有 `POST /api/review/<id>/check` | 是，只在隔离沙箱内 |
| 6 开发者修订 | 同上 | 既有 `POST /api/review/<id>/revise` | 否（修订后需重新检查） |
| 7 人工决定 | 同上 | 既有 `POST /api/review/<id>/decide` | 否 |
| 8 导出、接入 CI | 同上 | 既有 `POST /api/review/<id>/export`；新增 `GET /api/review/<id>/report.{json,sarif,junit,md}` | 否 |
| 9 别人复检 | `#recheck` | `POST /api/recheck/upload` | 是，只在隔离沙箱内 |

AI 候选（P2）使用第 5.2 节接口；仅现场模式且模型边界就绪、当前对象具有适用 FAIL 报告时可请求。

## 2. 通用约束

- 只监听 127.0.0.1；沿用既有 Host、Origin、Sec-Fetch-Site 检查。
- 所有新增的写操作都要求 `X-CredProof-Review-Session` 与启动时生成的会话值一致。
- 浏览器从不提交路径、命令或判决。项目内容只能以压缩包字节上传，或从服务端登记的示例/授权项目复制。
- 错误统一为 `{"error": "<机器可读代码或中文说明>"}`，HTTP 4xx；不返回宿主路径。
- 只读入口（`scripts/delivery/view_readonly.py`）只放行新增的 `GET /api/workspace/status`、`GET /api/reviews`、`GET /api/intake`、`GET /api/intake/examples`；它们只读已有状态，所有 POST 仍拒绝。状态查询可以探测操作者配置的运行时材料是否存在，不执行项目或模型。
- 项目自带有效 `credproof.toml` 时，草稿逐字节沿用原文件（`config_origin = "existing"`）；用户保存表单后才改为向导生成（`"form"`）。

## 3. 环境状态

`GET /api/workspace/status`

```json
{
  "schema": "credproof.workspace-status/v1",
  "access_mode": "view | recheck | live",
  "checker": {"ready": true, "detail": "reviewed rootfs, bubblewrap and Python site packages present (native Linux)"},
  "model": {"ready": false, "label": "…", "reasons": ["…"]},
  "can_check": true,
  "can_use_model": false,
  "reasons": ["只读回放模式不执行检查。"],
  "limits": {"upload_bytes": 16777216, "files": 2000, "file_bytes": 4194304, "expanded_bytes": 67108864}
}
```

`checker.ready` 来自 `credproof_safety.runner.available()`：只检查隔离材料是否存在，不运行项目代码。`can_check = access_mode != "view" and checker.ready`。即使显示可检查，检查本身仍可能因沙箱建不起来返回 UNKNOWN。

## 3.1 列表

- `GET /api/reviews` → `{"reviews": [{"id", "label", "kind", "created_at", "version_id", "versions", "version_source", "technical_verdict", "decision", "decision_is_test", "checked_at", "material_ok", "error?"}]}`：每个审阅对象当前状态，按创建时间倒序，最多 100 个。
- `GET /api/intake` → `{"intakes": [{"id", "label", "source", "status", "created_at", "review_id", "valid"}]}`：接入草稿与已开始的记录。

## 4. 接入（intake）

一个接入记录 = 一份只读源副本 + 一份配置草稿。草稿可以反复修改；“开始”时复制源副本并写入配置，生成审阅对象，之后配置、测试和访问组件冻结。

### 4.1 来源

- `POST /api/intake/upload`：`Content-Type: application/zip`，请求体是 zip 字节。浏览器选文件夹时由前端在本地打包为不压缩 zip。限制：上传 ≤16 MiB，展开 ≤64 MiB，≤2000 个文件，单文件 ≤4 MiB；拒绝绝对路径、`..`、反斜杠、盘符、控制字符、符号链接、加密条目；忽略 `.git/ .venv/ __pycache__/ .credproof/ __MACOSX/ node_modules/` 与 `*.pyc`；只有一个顶层目录时去掉这一层。可选请求头 `X-CredProof-Label`（URL 编码，≤80 字）作显示名。
- `GET /api/intake/examples` → `{"examples": [{"id", "label", "description", "kind": "example | authorized"}]}`。内置：资料助手（问题版本）、8 个对照评测目标（漏洞原版）；另含启动参数 `--project-config` 授权的项目。
- `POST /api/intake/example`，`{"example_id": "<id>"}`。

三者都返回 4.2 的接入视图，HTTP 201。

### 4.2 接入视图

`GET /api/intake/<id>`（id 为 32 位小写十六进制）

```json
{
  "schema": "credproof.intake/v1",
  "id": "…", "label": "资料助手（问题版本）", "source": "upload | example | authorized",
  "created_at": "…", "status": "DRAFT | STARTED",
  "review_id": null,
  "tree_sha256": "…",
  "files": [{"path": "tool.py", "bytes": 1253}],
  "detected": {
    "python_files": ["tool.py"],
    "test_paths": ["tests"],
    "entry_candidates": [{"module": "tool", "callable": "run", "params": 1}],
    "credential_env_candidates": ["CREDPROOF_TEST_CREDENTIAL"],
    "existing_config": {"present": true, "valid": true, "error": null}
  },
  "config": { "…": "见 4.3" },
  "config_origin": "existing | form",
  "toml": "schema = \"credproof.project-safety/v1\"\n…",
  "valid": true,
  "errors": [],
  "warnings": ["必要测试路径 tests 下没有 test_*.py"],
  "placeholders": {"__CREDPROOF_ALLOWED_FILE__": "允许目录中的资料文件", "…": "…"}
}
```

`detected` 只用 `ast` 静态解析，不导入、不执行上传代码。`errors` 来自 `credproof_safety.config.load_config` 对草稿的真实校验；`warnings` 不阻止开始。

### 4.3 配置草稿（结构化字段）

`POST /api/intake/<id>/config`，`{"config": {...}}`，返回 4.2。

```json
{
  "tests": ["tests"],
  "optional_tests": [],
  "source_scope": ["*.py", "**/*.py"],
  "entry": {"module": "tool", "callable": "run",
            "scenarios": [{"name": "normal", "request": {"path": "__CREDPROOF_ALLOWED_FILE__"},
                           "expected_error": null, "require_network": false}]},
  "allowed_dir": "data",
  "forbidden_dir": "secrets",
  "require_allowed_file_read": true,
  "service": {"enabled": true, "path_prefix": "/api", "require_credential": true},
  "credential_env": "CREDPROOF_TEST_CREDENTIAL",
  "timeout_seconds": 30
}
```

服务端把字段写成 `credproof.toml`（`mutable_scope` 固定为入口文件本身，与审阅链“只允许修改入口”的规则一致；顶层 `request`/`expected_error` 取第 1 个场景），再用 `load_config` 校验。`request` 只允许字符串、整数、浮点、布尔、数组、对象，深度 ≤4，序列化后 ≤4 KiB；不允许 null。场景 1–8 个，名称唯一。

### 4.4 开始审阅

`POST /api/intake/<id>/start`，`{"label": "可选显示名"}`。要求 `valid = true` 且状态为 DRAFT。返回 `{"intake": <4.2>, "review": <审阅视图>}`。审阅视图的 `meta.kind = "PROJECT"`，第 0 版来源 `PROJECT_IMPORT`，`ai_code = null`。同一接入只能开始一次；要换配置，重新接入。

## 5. 审阅视图新增字段

既有 `GET /api/review/<id>` 增加：

- `meta.kind`：`AI_HISTORY`（旧记录，缺省）或 `PROJECT`。
- `evidence`：由当前适用报告派生的五个问题，报告不适用时为 `null`。

```json
{
  "verdict": "FAIL", "classification": "ACTUAL_VIOLATION | NO_OBSERVED_VIOLATION | INCOMPLETE | OUTER_SANDBOX_BLOCKED",
  "unknown_reason": null,
  "questions": [
    {"id": "business", "state": "ok | bad | missing | unknown", "facts": {"tests_required": 4, "tests_executed": 4, "tests_passed": 2, "allowed_reads": 4, "allowed_auth_requests": 5, "entry_error": null}},
    {"id": "files", "state": "…", "facts": {"allowed_dir": "data", "forbidden_reads": 1, "out_of_scope_reads": 0, "forbidden_paths": ["secrets/secret.txt"]}},
    {"id": "requests", "state": "…", "facts": {"allowed": 5, "forbidden": 1, "unauthorized_connections": 1, "paths": [{"service": "forbidden", "path": "/secret", "authorization": true}]}},
    {"id": "credential", "state": "…", "facts": {"output_channels": ["stdout", "logs", "return"], "sent_to_forbidden": 1}},
    {"id": "adoption", "state": "…", "facts": {"technical": "FAIL", "decision": "PENDING", "application": "NOT_APPLIED"}}
  ],
  "failed_conditions": ["pytest", "…"],
  "duration_ms": 8123.4
}
```

`state` 含义：`ok` 观察到应有行为且无违规；`bad` 观察到违规；`missing` 无违规但应有行为没有发生；`unknown` 证据不完整。凭据只给通道名称，不给值。

### 5.1 报告下载

`GET /api/review/<id>/report.json | report.sarif | report.junit | report.md`：当前版本适用报告的派生格式（与 `credproof-safety check --sarif/--junit/--summary` 同一实现）。没有适用报告时 409。只读，不需要会话头。

### 5.2 请求本地模型候选（P2）

`POST /api/review/<id>/propose`，只允许 `{"expected": {"version_id", "object_sha256", "report_sha256", "decision_count"}}`，沿用会话头、Host/Origin 校验和共同 operation 锁。只在 live 且当前配置的模型/隔离材料就绪时可用，否则 409 `live_model_boundary_required`。缺适用 FAIL 报告为 409 `propose_requires_current_FAIL`，过期绑定为 409。

每次操作最多 **1 个模型请求、1 个候选、0 次格式重试、0 次自动检查**；16K 上下文、2048 输出、512 安全预留、单请求120秒、总900秒，预算不满足明确拒绝。使用当前明确配置的固定模型，不下载或回退。输入只由冻结入口、必要测试、公开配置/组件约定和脱敏当前失败事实构造；模型在既有只读白名单/私有网络边界中运行，无原生工具或任意执行。

返回 `{"status":"CANDIDATE","review":<新审阅视图>,"model_requests":1,...}` 或 `{"status":"NO_CANDIDATE","reason":"...","review":<原视图>,...}`。STOP、超时、格式不合格或 NO_CHANGE 不新增版本。原始请求/响应、输入预算、模型边界、使用量及接收格式收据留在该审阅对象的 `proposals/<opaque-id>`。

有效的不同源码仅写入新版本入口，来源 `AI_CANDIDATE`；版本记录固定模型名称/digest、请求/响应文件 SHA-256、策略和提议 ID。技术结论 UNKNOWN、人工 PENDING、NOT_APPLIED；**不自动检查、采纳或写回**。用户需另点“运行检查”，任何模型 reason 都不能决定 PASS。推理后再核对当前绑定，材料变化时不创建新版本。

## 6. 复检导出包

`POST /api/recheck/upload`，`Content-Type: application/zip`，请求体为“导出已采纳修复”或“导出诊断材料”下载的 zip。服务端解压到新的临时目录（同 4.1 限制），调用 `credproof_safety.project_bundle.recheck_project_bundle`，返回：

```json
{"schema": "credproof.project-recheck/v1", "status": "RECHECKED | BLOCKED", "validation": {"verdict": "PASS"},
 "prior_report_applicable": true, "prior_report_reasons": [], "project_tree_sha256": "…",
 "human_review": {"kind": "ADOPTED_REPAIR", "decision": "APPROVED", "decision_is_test": false},
 "evidence": {"…": "同第 5 节"}}
```

`view` 模式返回 409。诊断包没有 `manifest.json` 时返回 `status = BLOCKED`、`MATERIAL_UNAVAILABLE`，不当作通过。

## 7. 不做的事

- 不把通过的修订写回用户原项目；导出后由开发者自己应用。
- 不在宿主机降级执行；隔离不可用时检查结果为 UNKNOWN。
- 不保存或展示合成凭据的值。
- 页面上的“五个问题”只是对报告字段的归纳；判定仍以 14 项必要条件为准。
