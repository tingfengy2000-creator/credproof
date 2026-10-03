# 密证 CredProof：作品展示与受控修复工作台

本目录是无构建步骤的静态单页：`index.html`、`styles.css`、`app.js`。深蓝、青蓝与紫色的作品首页展示三个特点、主流程与典型案例，下方工作台呈现真实修复依据。原生 SVG 与 CSS 提供图形层次，不依赖 React、CDN、网络字体或第三方脚本。后端以同源标准库 HTTP 服务托管此目录，并实现 `/api/agent`。打开 HTML 文件只能看到真实的连接错误/未执行状态，不会载入模拟结果。

当前候选版 `0.2.0-preliminary.5` 的推荐顺序为：首页 → h01 有限修复增量 → h03 失败候选与反馈调整 → h07 正常保留 → 材料复检。所有精选案例标注历史回放，现场分析必须单独发起。原始 JSON、模型长文和研发历史收进展开区域；内容与判决来源不改变。深色首页与工作台统一呈现，分项状态分别取自实际证据。布局与组件沿用 preliminary.3，本版只改价值与分工文案。历史视觉检查见 [preliminary.3 检查](../../docs/preliminary-candidate/premium-checks.md)。

本目录没有模型、候选执行、文件上传、任意网络地址或任意命令输入。原工作区 `E:\比赛\密证_CredProof` 仅作只读参考，未修改。

## 接口约定

| 请求 | 输入 / 返回 |
| --- | --- |
| `GET /api/agent/bootstrap` | 返回下述 Bootstrap |
| `POST /api/agent/runs` | JSON `{case_id}`；返回 RunView，不接收用户判决 |
| `GET /api/agent/runs/{id}` | 返回 RunView；执行中约每 2 秒请求一次 |
| `POST /api/agent/runs/{id}/recheck` | JSON `{}`；返回含独立 `recheck` 的完整 RunView |
| `GET /api/agent/runs/{id}/export` | 返回实际文件内容；按 Content-Type 和安全文件名下载 |

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

代码视图支持方向键、Home/End，按钮和菜单可键盘操作，有跳至主区域链接及状态播报。遵循 reduced-motion；长代码在自身容器滚动，移动窄屏按单列重排。没有装饰性统计、虚构成功率或定时自动重跑。

preliminary.2 阶段已执行 `node --check agent_pilot/ui/app.js`；Web、对象绑定和真实历史展示的 20 项必要回归通过。浏览器实际检查首页、三例切换、补丁展开、返回新任务，以及一次 h07 确定性复检和材料下载。该复检得到 13 条件 PASS、历史材料 INTACT、旧报告适用；它不调用模型，也不改变历史实验成绩。原始记录、界面截图和检查范围见 [preliminary.2 展示检查](../../docs/preliminary-candidate/presentation-checks.md)。

## 启动本机后端

```text
python -m agent_pilot.launch --demo --port 8765
```

浏览器打开 `http://127.0.0.1:8765/`。后端仅绑定该 IPv4 回环地址，使用标准库，不需要安装 Web 框架。当前命令加载三个明确标注的精选回放。高级 `agent_pilot.web` 入口需要展示额外既有运行时，由可信操作者在启动时显式追加 `--history <当前仓库 runs 下的 case/C-agent 目录>`，可重复提供；HTTP 请求不能提交路径。

新建任务只接受登记的 case_id，使用固定 argv 通过 WSL 的 user/network namespace 启动现有 `agent_pilot.offline_run --reliability --agent-only`。启动网页本身不运行模型；只有点击开始且设施可用才创建独立的 `runs/ui/live-...` 记录。原始 supervisor stdout、stderr、退出码保留在该私有目录，不直接发送到浏览器。

健康接口只报告准备设施与保存门禁身份的只读观察，不代替新的隔离探针或模型验收。模型环境缺失、门禁未就绪或另一个操作占用时拒绝新任务。任务状态、最终协议验收和模型诊断分别保留。

当前判定器若仅提供整体结果，检查区只显示真实的“固定协议完整验收”，不会从整体 PASS 伪造安全、功能、边界三项通过。判定器提供 checks 后，前端将原样展示其逐项状态。
