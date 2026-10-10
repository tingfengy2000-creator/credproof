# CredProof：5060前端研发交接

**READY_FOR_FRONTEND_HANDOFF · AI_ASSISTED_HUMAN_REVIEW**。依据是5090固定版本自验收；外部独立源码复核 **NOT_COMPLETED**。本轮新增模型调用、候选执行、安全实验均为0，不恢复已结束的模型任务，不代替本人采纳业务修复。

保留基线：`81c289fd71c8839e2c122032fe15a473f4380710`；被测程序：`50e0d694d1c40352b82853fc62d6df0983240d43`；安装版本：`0.3.0.dev35`。这两个提交间的程序目录一致，后者之后的提交增加材料和收据。[交接收据](HANDOFF_RECEIPT.json) / [本轮只读核对](evidence/existing-evidence-correspondence.json)。后补推送记录见本目录`evidence/github-delivery.json`，记录实际交接材料提交，不把收据提交当新程序实测。

正式主线：**AI提出候选 → 开发者审阅并提交修订 → 程序独立验收 → 本人决定采纳 → 同一对象导出、复检**。纯模型独立修复PASS已经由用户移出当前必需范围，历史FAIL/UNKNOWN保留。

## 六项已有验收对应

以下均是读取20261010-human-review既有记录，没有重跑整批实验。源码均相对本提交固定；`verify-evidence.py`逐项匹配原始报告、wheel和Git字节，不执行项目。

| 项目 | 实现与原始依据 | 本次确认 |
|---|---|---|
| 1. AI来源不改写 | [open_method/view](../../../credproof_safety/human_review.py)、[AI源码](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/source-bundle/ai-candidate.py)、[原FAIL报告](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workflow/baseline/report.json)、[历史解析回放](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/installation/historical-parser-replay.json) | v000=AI_HISTORY；原UNKNOWN及后续FAIL各按原轮保存；没有变成新模型成功。 |
| 2. 修订与独立验收 | [revise/check](../../../credproof_safety/human_review.py) → [check_project](../../../credproof_safety/project.py)、[v001版本](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace/runs/human-review/939e25f42bb142f39567c5cb644ebc6d/versions/v001/version.json)、[完整报告](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace/runs/human-review/939e25f42bb142f39567c5cb644ebc6d/versions/v001/reports/check-01.json) | 来源DEVELOPER_REVISION（Codex辅助）。4项必要用例setup/call/teardown实际通过、0skip；14项必要条件为真。正常返回包含真实资料，允许服务有认证回执；独立跳转得到约定HTTPError且无禁止服务回执。 |
| 3. 技术／人工／应用分离 | [view/_expected/decide](../../../credproof_safety/human_review.py)、[实际HTTP控制](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/approval-function-tests/http-controls.json)、[协议测试](../../../agent_pilot/tests/test_human_review.py) | 正式939e25f4…保持PASS/PENDING/NOT_APPLIED。APPROVED等测试在专用克隆，身份approval-function-test；FAIL、UNKNOWN、缺材料、过期审批后端拒绝，不依赖按钮置灰。 |
| 4. 当前对象绑定 | [_binding/_expected/export](../../../credproof_safety/human_review.py)、上述HTTP原始21条、[重验记录](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/approval-function-tests/reports/) | 代码、规则、组件、必要测试漂移四个克隆均UNKNOWN/PENDING，采纳/导出409。重验产生新报告后批准不自动恢复。 |
| 5. 同对象公开复检 | [public-bundle清单](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/public-bundle/manifest.json)、[匿名取件](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/recheck/anonymous-retrieval.json)、[新目录完整复检](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/recheck/report.json)、[消费者控制](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/consumer/installed-controls/summary.json) | 同一候选7a7dcaf7…，16材料+manifest共17文件。固定Git字节取回后RECHECKED/PASS；消费者实际pytest固定PASS／重新引入FAIL／无关修改PASS。 |
| 6. 安装／页面／重启 | [wheel清单](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/installation/wheel-manifest.json)、[主进程](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/installation/server-origin.json)、[子进程](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/installation/child-origin-qwen25.json)、[重启后浏览器](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/installation/browser-after-restart.txt) | 安装dev35，`-I`、site-packages来源；86个wheel成员核对。真实页面与重启后保留同一v001 PASS/PENDING。没有替用户确认采纳。 |

所有检查只支持已适配Python工具、合成凭据、受控文件和本地模拟服务。必要条件来自开发者，普通哈希和本地审批记录不是第三方认证、强身份签名或绝对安全证明。

## 5060马上能打开的只读入口

实际技术栈是 **原生HTML/CSS/JavaScript ES module + SVG，Python标准库ThreadingHTTPServer**，没有React/Vite或前端npm构建。5060只需Python，无模型、GPU推理、WSL、rootfs或Agent依赖。

从GitHub取得`feat/frontend-human-review-5060`分支（已有本地修改先自行保存，勿reset/clean）。在仓库根目录PowerShell运行，安装路径由操作者选择：

```powershell
py -3.12 -m venv C:\CP-frontend\venv
$py = 'C:\CP-frontend\venv\Scripts\python.exe'
$wheel = '.\docs\reusable-tool-safety\acceptance\20261010-human-review\public-evidence\installation\credproof_safety-0.3.0.dev35-py3-none-any.whl'
(Get-FileHash -Algorithm SHA256 $wheel).Hash
# 期望 ced6f43361cd3ca483f3ae7a6086383ee5a45edb2999c9a56abb62691ac448b4
& $py -m pip install --no-index --no-deps $wheel
& $py -I docs/handoff/frontend-5060/view-readonly.py --port 8765
```

打开`http://127.0.0.1:8765/#human-review`，点“读取已有修订”。**READ_ONLY_HISTORY**明确表示5090已有结果，不是5060新验收。Ctrl+C停止。本轮已在5090新建最小venv、仅离线安装原wheel，实际HTTP和浏览器验证：[5项传输检查](evidence/readonly-clean-install.json)、[原始日志](evidence/readonly-clean-install.txt)、[浏览器文字](evidence/readonly-browser.txt)、[画面](evidence/readonly-browser.png)。这不是跨机器验证或新的安全实验。

[view-readonly.py](view-readonly.py)校验27个快照文件后复制到临时数据目录，程序来自安装wheel，仅3个UI文件来自当前前端checkout；改CSS/JS后刷新即可。后端仅允许列明GET，其余请求405；原Host/Origin边界保留。审批、修改、导出按钮即使被触发也不能执行；这是显式安全拒绝，按钮交互呈现可由5060调整。**不要改用普通`agent_pilot.launch --mode view`冒充该只读边界**：旧view模式仅限制动态执行，仍有修订/决策操作。

真实历史数据来自[快照及完整清单](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace/snapshot-manifest.json)。不要编辑历史报告来测试UI。需要表单成功态替身时，必须标`UI_FIXTURE`、仅在独立临时UI内存中使用；不得写真实decision/report目录或导出成安全依据。本轮没有新增此类审批替身，更没有真实采纳。

## 前端位置与接口字段

| 位置 | 用途 |
|---|---|
| [index.html](../../../agent_pilot/ui/index.html) | 单页结构、表单、折叠区、inline SVG；`#human-review`与`#workbench`为页内锚点 |
| [styles.css](../../../agent_pilot/ui/styles.css) | 现有深色样式；直接由HTTP提供，无前端构建器 |
| [app.js](../../../agent_pilot/ui/app.js) | `renderReview/reviewExpected/reviewAction/reviewDownload`及页面事件；只展示后端结果 |
| [web.py](../../../agent_pilot/web.py) | `Handler.route/Application.bootstrap`：路由、session、Host/Origin、操作锁；归5090维护 |
| [human_review.py](../../../credproof_safety/human_review.py) | 来源/版本、修订、检查、决策、导出与摘要绑定；归5090维护 |
| [launch.py](../../../agent_pilot/launch.py)、[runtime_config.py](../../../agent_pilot/runtime_config.py) | 已有启动/集中配置；动态模式只在5090使用 |

真实HTTP契约如下，5060只读包装器只开放前两项和健康/静态资源。其余**只列接口供前端连接设计，不能在5060执行真实流程**：

| 接口 | 实际请求／响应 |
|---|---|
| GET `/api/agent/bootstrap` | `reviews/history/review_session/access_mode`等；只读入口另加`frontend_handoff`，必须尊重其`read_only` |
| GET `/api/review/<id>` | `version.id/parent/source/reason/created_at/entry_path/code_sha256`，`code/ai_code/original_code/diff`，`technical_verdict/report/report_applicable/material_reasons`，`object_sha256/report_sha256`，`decision/decision_applicable/decision_is_test/decisions`，`application_to_original` |
| POST `/api/review/open` | `{run_id}`：已登记历史记录；不接受任意磁盘路径 |
| POST `/api/review/<id>/revise` | `{expected, code, reason}`：新副本，原对象不变 |
| POST `/api/review/<id>/check` | `{expected}`：原可信隔离检查，不调用模型 |
| POST `/api/review/<id>/decide` | `{expected, decision, reason, test_operation}`；decision仅NEEDS_CHANGES/REJECTED/APPROVED，测试操作必须明确标记 |
| POST `/api/review/<id>/export` | `{expected, adopted}`，返回ZIP；诊断导出与已采纳导出权限分开 |

`expected`必须恰含`version_id/object_sha256/report_sha256/decision_count`，从当前响应构造。写操作还要求`X-CredProof-Review-Session`及原同源检查。旧页面或材料漂移通常409并带`error`，不能在JS改判PASS；缺材料、未验收或旧报告显示UNKNOWN。检查时间取`report.checked_at_utc`；人工决策时间取`decisions[].at`。程序PASS、人工PENDING与NOT_APPLIED是三个独立状态，局部条件PASS也不能替代总体判决。

## 分支、保护范围与5090复核

- `baseline/human-review-dev35`固定在81c289fd…，只供保留，不移动、不覆盖标签。
- `feat/frontend-human-review-5060`从同一冻结程序建立，只附本轮交接入口；后补交接收据提交不改变程序。实际完整分支SHA以Git及`evidence/github-delivery.json`为准。
- 5060只改`agent_pilot/ui/index.html`、`styles.css`、`app.js`及对应静态/UI测试与文案。只推自己的分支并提PR，不直接推main或`feat/reusable-tool-safety`。
- **保护**：`credproof_safety/**`、`credproof_access/**`、`agent_pilot/*.py`、锁定依赖、配置权限、必要测试、`docs/reusable-tool-safety/acceptance/**`、`experiments/**`、模型/隔离配置及本目录只读边界。要改接口或行为，先由5090评审，不能在UI里重算安全结论。
- 5090独占真实候选执行、文件/网络试验、模型推理、审批功能测试、真实导出/复检、打包与最终集成。不要复制WSL/rootfs/模型到5060，也不以GitHub Actions代替这些执行。
- PR写明改动、接口影响、真实静态/UI测试和待5090验证项。5090随后在独立worktree/集成分支检查实际最终合并树；冲突解法改变代码后验证受影响部分，通过才合并。本轮不创建PR、不启动另一轮任务。

5090已经执行的协议42项，具体命令/退出码及动态安装/消费者/复检记录见[原始命令表](../../reusable-tool-safety/acceptance/20261010-human-review/public-evidence/command-record.json)；本轮沿用，不重跑。相关定向入口：

```powershell
# 软件协议回归（包含替身报告；不等同安全案例/模型成功）
.\.venv\Scripts\python.exe -m pytest -q agent_pilot/tests/test_human_review.py agent_pilot/tests/test_web.py agent_pilot/tests/test_web_material_binding.py agent_pilot/tests/test_output_format.py
# 5060也可运行：仅HTTP/UI传输，所有执行侧入口被替身拦住；输出必须新路径
& $py -I docs/handoff/frontend-5060/test-readonly.py --output C:\CP-frontend\readonly-check.json
# 只读证据对应核对（需Git，不调用模型/项目）
& $py -I docs/handoff/frontend-5060/verify-evidence.py --output C:\CP-frontend\evidence-match.json
# 以下仅5090，需原已预检隔离环境；不能在5060执行
& $py -I scripts/recheck-component-review.py --bundle <按manifest取得的public-bundle目录> --output <新报告路径> --receipt <新收据路径>
& $py -I scripts/run-exported-regression-check.py --installed --output <新的消费者结果目录>
```

动态命令需5090现有可信WSL Ubuntu-24.04/bubblewrap/rootfs，Python3.12.14/pytest8.4.2及对应依赖；路径由现有集中配置给出。无隔离必须阻断，不降级宿主执行。`$py`在动态命令中必须选5090已有准确安装环境，而非上面最小只读venv；后者刻意没有pytest/requests/Agent依赖。

## 前端PR的7项操作核对

1. 打开只读入口并加载已有修订：明确历史标识、候选来源和v001，不冒充现场推理。
2. 显示完整总体PASS/FAIL/UNKNOWN、对象、时间和适用性；缺材料/过期不显示当前通过。
3. AI原件、开发者修订、相邻diff和报告各有来源；不覆盖原FAIL/UNKNOWN。
4. 程序判决、人工状态、应用状态分开；PENDING不变成APPROVED，采纳不等于应用。
5. 只读环境所有真实写入/检查/导出均拒绝；UI_FIXTURE如新增必须临时且显式，不能生成真实证据。
6. 5090后续复核现有过期/代码/规则/组件/测试变化的后端拒绝及同对象导出复检；不要用按钮置灰替代。
7. PR注明仅静态/UI验证与待5090动态验证项，最终合并树受影响回归通过再合并，不借旧PASS覆盖新代码。

**仍待确认**：外部独立源码复核尚未完成；本人正式对象采纳保持PENDING。若5060由另一位实际人员实质开发，参赛者须先确认其合规登记的团队身份并记录贡献；同一人的第二台机器不据此新增成员。AI辅助开发参赛许可、身份字段及声明由本人/指导教师/组委会确认，不在本收据中宣称已许可或代签。

本轮到交接入口和收据推送为止。没有新模型实验、安全案例或前端重构，没有比赛提交或生产认证。
