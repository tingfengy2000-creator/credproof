# 密证 CredProof：AI 补丁验收控制台

本目录是无构建步骤的静态单页：`index.html`、`styles.css`、`app.js`。界面为“左侧导航 + 主区”的验收控制台，面向需要决定“AI 补丁能不能合入”的开发负责人与安全负责人。不依赖 React、CDN、网络字体或第三方脚本；CSP 下不使用内联样式与内联脚本。后端以同源标准库 HTTP 服务托管此目录。

导航与路由（哈希路由，可直接分享链接）：

| 路由 | 页面 | 数据来源 |
| --- | --- | --- |
| `#overview` | 验收概览：放行矩阵（业务测试、静态扫描、两个大模型裁判与 CredProof 对同一批对象的结论）、关键发现、8 个评测目标、历史补丁复检 | `GET /api/bench` |
| `#patches?origin=&verdict=&target=&model=&disagree=1` | 补丁记录：可筛选的台账 | `GET /api/bench` |
| `#patch/<id>` | 补丁详情：印章式结论、五种方法对照、运行证据、14 项条件、差异与完整代码、裁判理由 | `GET /api/bench/patches/<id>` |
| `#report/<id>` | 可打印的《补丁验收报告》（浏览器打印或存为 PDF） | 同上 |
| `#pipeline`（别名 `#ci`） | 流水线闸门：两条演示 PR 在 GitHub 托管 Ubuntu 24.04 上的实际红/绿结果、代码扫描告警事实、接入方式（targets、容器命令、退出码、三种输出）和运行环境验收 | `GET /api/integration` |
| `#human-review` | 人工审阅：程序判定 / 人工决定 / 原仓库三个独立状态与版本链 | `/api/review/*` |
| `#workbench` | 案例回放（原工作台，全部原有元素 ID 保留） | `/api/agent/*` |
| `#project-entry` | 接入项目：四步接入、登记项目的无模型检查与回归测试导出 | `/api/project/*` |
| `#method` | 工作原理与三种结论的定义 | 静态 |

旧锚点 `#cases`、`#projects`、`#mechanism` 自动映射到新路由。评测数据只在 `bootstrap.bench_available` 为真时读取；概览中所有数字都由结果文件现场计算，不写死在页面里。分组依据是 CredProof 观测到的具体事实，因此页面只陈述“其他方法放过了有具体违规事实的对象”，不把 CredProof 一行当作准确率。

本目录没有模型、候选执行、文件上传、任意网络地址或任意命令输入。原工作区 `E:\比赛\密证_CredProof` 仅作只读参考，未修改。

## 接口约定

| 请求 | 输入 / 返回 |
| --- | --- |
| `GET /api/agent/bootstrap` | 返回下述 Bootstrap |
| `POST /api/agent/runs` | JSON `{case_id}`；返回 RunView，不接收用户判决 |
| `GET /api/agent/runs/{id}` | 返回 RunView；执行中约每 2 秒请求一次 |
| `POST /api/agent/runs/{id}/recheck` | JSON `{}`；返回含独立 `recheck` 的完整 RunView |
| `GET /api/agent/runs/{id}/export` | 返回实际文件内容；按 Content-Type 和安全文件名下载 |
| `GET /api/bench` | bench-results/v1 摘要与逐对象结论（不含代码和差异）；未加载时 409 |
| `GET /api/bench/patches/{id}` | 单个对象的代码、差异、运行证据与裁判理由 |
| `GET /api/integration` | credproof.ci-demo/v1：由 `scripts/integration/build_ci_demo.py` 从 `docs/integration/evidence/ci-c` 派生的流水线演示数据；工作区内固定文件，不接受请求路径；不存在时 404 |

```typescript
type Verdict = 'PASS' | 'FAIL' | 'UNKNOWN';
type Check = {id: string; label?: string; status: Verdict; reason?: string};
type Validation = {
  verdict: Verdict; reasons?: string[]; checks?: Check[];
  checked_at?: string; checked_at_utc?: string;
};
type Bootstrap = {
  cases: Array<{
    id: string; title: string; description: string;
    source_code: string; source_sha256?: string; rules: string[];
  }>;
  runtime: {ready: boolean; model_label?: string; reasons?: string[]};
  history?: Array<{id: string; label?: string; case_id: string; created_at?: string}>;
};
type RunView = {
  id: string; case_id: string; mode: 'LIVE' | 'REPLAY';
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'STOPPED' | 'ERROR';
  task_status?: 'COMPLETED_REPAIRED' | 'COMPLETED_UNCHANGED' | 'INCOMPLETE' | 'UNKNOWN' | 'FAILED';
  phase?: string; stop_reason?: string;
  started_at?: string; updated_at?: string;
  model?: {
    status?: string; calls?: number; diagnosis?: string; initially_leaking?: boolean;
    raw_notes?: Array<{source: string; text: string; display_truncated: boolean}>;
    proposals?: Array<{rationale: string; status: string; reason?: string; candidate_id?: string}>;
    denied_proposal_count?: number;
  };
  diagnosis?: {
    model_suspicion: string | null;
    confirmed: 'CONFIRMED_LEAK' | 'NO_LEAK_OBSERVED' | 'UNKNOWN';
    repair_authorized: boolean;
  };
  tool_calls?: number; unknown_count?: number;
  source_code: string; source_sha256?: string;
  candidate_code?: string | null; candidate_sha256?: string;
  diff?: string | null;
  evidence?: Array<{
    id: string; hypothesis?: string; observation: unknown;
    verdict?: Verdict; source_sha256?: string;
    collected_at?: string; tool?: string;
  }>;
  validation: Validation | null;
  recheck?: {
    status: string; checked_at?: string; validation: Validation;
    candidate_sha256?: string; prior_report_applicable?: boolean;
  };
  limitations?: string[]; remaining_uncertainty?: string[];
};
```

返回错误时可以使用 `{detail:{message}}`、`{message}` 或 `{error}`。非 2xx 响应不会被当作成功。接口字段不完整或整体判决枚举未知时，界面停止采用新结果，并标明留下的是上次取得的记录。

## 展示语义

- 模型诊断、原始风险确认、修复授权、候选验收各自显示。`NO_LEAK_OBSERVED` 显示为“未观察到泄露”，不改写成“绝对安全”。
- 没有最终诊断时，仍展示实际保存的 assistant 文字和提案理由，并标记拒绝数量；原始疑点不补造成诊断布尔值，不代替程序确认。大段原文展示截短时明确标识，完整原文仍留在本地记录。
- 未取得字段显示未知或“—”；未运行显示未验收；不会根据模型回答、按钮名称、任务结束或整体 PASS 生成逐项通过记录。
- `validation` 是首次/原验收，`recheck` 是新的固定程序复检；复检不覆盖首次结果，不调用模型。先前报告适用性与新判决分开显示。
- 历史选择必定启用醒目的回放提示，即使服务端返回 mode 为 LIVE；页面会保留原任务 ID 与执行时间。回放状态不能点击新建任务，须先返回新任务。
- 案例菜单只使用 Bootstrap 白名单。创建请求只包含 case_id；代码、规则及差异均来自服务端。候选代码不会在浏览器中执行。
- 证据按实际返回条目渲染。模型及工具数据必须先由后端脱敏；前端不能替代可信脱敏边界。所有数据经文本转义后展示，不能注入 HTML。
- 请求失败暂停轮询，保留旧数据但显示状态未确认。90 秒 HTTP 超时只结束请求，不声称终止后端任务；提示刷新后确认，避免直接重试创建。

## 操作与可访问性

路由、筛选、代码页签和人工审阅页签都可键盘操作：代码视图支持方向键和 Home/End，有“跳到主要内容”链接和状态播报。遵循 reduced-motion；长代码在自身容器内滚动；窄屏（≤860px）改为单列，表格在自身容器内横向滚动，页面本身不横向滚动。深色模式跟随系统。`#report/<id>` 的打印样式只输出报告本身（A4，页边距 18mm/16mm）。

本版（PR #8）在 Linux 上做过的检查：`node --check agent_pilot/ui/app.js`、`node agent_pilot/tests/test_ui_project_verdict.js`；`test_web`、`test_web_bench`、`test_presentation`、`test_human_review` 共 27 项；只读入口与 `--demo --mode view` 下用 Playwright 逐页截图（无 JS 错误、只读入口无 POST），390px 宽度、深色模式、打印 PDF。Windows 维护套件 255 项由 5090 在 PR #8 审查中运行通过。浏览器页面、字体与 recheck/live 按钮链路以 5090 的 Windows 实测为准。截图见 `docs/ui/console-v1/`，可复现的浏览器检查脚本见 `docs/ui/console-v1/check-console.mjs`。

## 启动本机后端

三种模式共用同一入口 `python -m agent_pilot.launch`，后端只绑定 `127.0.0.1`，使用标准库，不需要 Web 框架。浏览器打开 `http://127.0.0.1:<端口>/`（默认 8765）。

| 模式 | Windows 快捷方式 | 命令 | 能做什么 |
| --- | --- | --- | --- |
| view（默认） | `start-credproof.cmd` | `python -m agent_pilot.launch --demo --mode view` | 查看历史与评测结果（概览、补丁记录、验收报告、案例回放）。不启动模型，不检查 WSL，不执行任何代码：重新验收、项目检查和人工审阅的“重新验收”返回 409；人工审阅的保存修订、记录决定、导出，以及接入项目的回归测试导出仍可用，它们只写记录或打包文件、不执行代码，修订后的版本在 recheck 模式验收前保持“证据不足” |
| recheck | `start-recheck.cmd` | `python -m agent_pilot.launch --demo --mode recheck` | 在此基础上执行代码：案例重新验收、人工审阅的重新验收、接入项目的无模型检查，全部在 WSL/bubblewrap 隔离环境中进行，隔离不可用时拒绝而不在主机上降级执行。不启动模型 |
| live | `start-live.cmd` | `python -m agent_pilot.launch --demo --mode live` | 在 recheck 基础上允许“开始分析与修复”调用本地模型；需要 qwen-agent 与已就绪的本地模型 |

可选参数：

- `--bench-results <文件>`：评测结果文件（bench-results/v1）。带 `--demo` 且仓库内存在 `docs/bench/bench-results.json` 时自动加载；都没有时概览页显示“没有加载评测数据”。
- `--project-config <credproof.toml>`：操作者在启动时授权一个已适配项目；网页不接受路径。
- `--history <runs 下的 case/C-agent 目录>`：显式追加既有运行记录，可重复；HTTP 请求不能提交路径。

只读交接入口 `docs/handoff/frontend-5060/view-readonly.py --bench-results docs/bench/bench-results.json` 只放行 GET，用于在没有隔离环境的机器上查看。

### live 模式的执行边界

点击“开始分析与修复”时，服务端只接受登记的 `case_id`，先读取运行时观察（`config/local-runtime.json` 或 `CREDPROOF_CONFIG` 指定的文件），隔离和模型均就绪才继续。随后用**已核验的安装解释器**启动子进程：

```text
<program_python> -I -m credproof_safety.web_repair --project-id <登记项目> --case-id <case_id> --config <服务端选定的配置> --output runs/ui/live-.../
```

`program_python` 来自环境变量 `CREDPROOF_INSTALLED_PYTHON` 或运行时配置中的 `program_python`，必须是存在的绝对路径；未配置时拒绝任务，不回退到源码目录或历史 `_runs` 中的旧包。`web_repair` 调用与命令行相同的 `request_repair`，模型在其进程边界内运行；历史 `agent_pilot.offline_run` 入口不再由网页调用。启动网页本身不运行模型；原始 stdout、stderr 和退出码保留在私有记录目录，不直接发送到浏览器。

健康接口只报告准备设施与门禁身份的只读观察，不代替新的隔离探针或模型验收。环境缺失、门禁未就绪或另一个操作占用时拒绝新任务。任务状态、最终验收和模型诊断分别保留；判定器只给整体结果时，检查区不会伪造逐项通过。
