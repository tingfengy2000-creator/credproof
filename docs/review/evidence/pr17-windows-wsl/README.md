# PR #17 — Windows + WSL 审查与验收

本轮模型调用 **0**。这是一轮产品工作区与既有隔离检查链路验证，不是新的模型修复实验。主线为 `feat/frontend-human-review-5060`，没有修改 `main`。

## 版本与范围

- PR #16 原提交：`caf50feff2f5375a71d7cce16a3a41b73a248fce`；先合并为 `0a707e4217cd99c3b02d34aa0fcfeb961bd49b5a`。
- PR #17 原提交：`f123ea7f3c53a48b9341b1c44219dda95cdb9411`。
- 本轮最终程序源码：`9f83f84d73c924b19742e42bd2f826c1dad3e057`。
- 实际写入浏览器流程运行于 `577baf7e5ccc6a4f16e5dcd0ff079f606cd48c28`。随后 `9f83f84` 只改独立只读入口、接口说明与测试，未改该流程执行代码。最终包的 306 份程序/数据文件逐字节相同，只有 `delivery.json` 中的源码提交更新，见[逐文件比较](receipts/package-byte-reuse.json)。最终包另行实际启动并完成浏览器检查。
- 后续仅加入本目录审查材料；源码 SHA、证据提交和合并 SHA 分开记录，避免把收据提交说成另一次实验。

## 三项实际修正

1. **ZIP 原始名字**：Windows 的 `ZipInfo.filename` 会先规范化反斜杠或截断 NUL。上传校验改用 `orig_filename`，再执行已有路径/权限限制。测试用真实畸形 ZIP 字节，覆盖反斜杠和 NUL，不在宿主执行上传代码。代码：[intake.py](../../../../agent_pilot/intake.py)、[定向回归](../../../../agent_pilot/tests/test_product_workspace.py)。保留[最初 Windows 失败](prior-failures/windows-raw-zip-failure.xml)。
2. **两个检查按钮重名**：项目审阅页保留 `project-check`；旧登记项目页改为 `registered-project-check`，同时改事件与状态更新，并加入全部 HTML ID 唯一性回归。两条真实页面链路均能进入检查。[app.js](../../../../agent_pilot/ui/app.js)、[边界结果](boundaries/summary.json)。
3. **严格只读入口遗漏列表 GET**：补 `/api/intake` 白名单；仍拒绝全部 POST，并补真实 HTTP 回归。保留[修前 18 项路由错误](prior-failures/readonly-missing-intake.json)，[修后全部路由 PASS](strict-readonly-final/summary.json)。代码：[view-readonly.py](../../../handoff/frontend-5060/view-readonly.py)。

## 受保护实现结论

| 项目 | 实际检查及依据 | 结果 |
|---|---|---|
| `ReviewWorkspace.open_project` | 冻结 v000 配置/测试/访问组件；`PROJECT_IMPORT` 无 AI 候选，`ai_code=null`；后续复用既有 revise/check/decide/export 对象绑定 | 通过 |
| 原 AI 历史审阅 | 旧 kind 缺省 `AI_HISTORY`；历史 v000 FAIL、v001 PASS/PENDING/NOT_APPLIED 保持。原 27 份材料加清单共 28 文件与 PR 原提交逐字节一致 | [冻结检查](receipts/frozen-byte-check.json)、[历史视图](product-final/review-AI_HISTORY-939e25f42bb142f39567c5cb644ebc6d.json) |
| 新写接口 | 上传/配置/开始/复检要求会话头；项目 ZIP 受大小、条数、路径、链接限制；不接受浏览器宿主路径或命令 | 无 session 403、过期对象 409、FAIL 不可采纳 409，[真实 HTTP 记录](boundaries/http.json) |
| `runner.available()` | Windows 返回就绪(WSL)；WSL 原生路径返回就绪；`Application.checker` 与之对应。此探测只证明材料存在，真实检查仍可能 UNKNOWN | [解释器、版本与材料探测](receipts/provenance.json)；真实执行另见下表 |
| 打包白名单 | 8 个 `examples/bench/*/project/credproof.toml` 全在最终 ZIP；无模型、rootfs、环境。官方 Python 3.12.10 ZIP 摘要校验 | [构建收据](delivery/cp17-9f83f84-receipt.json)、[包扫描](delivery/cp17-9f83f84-scan.json) |

## 实际 Windows → WSL/bubblewrap 页面操作

使用可丢弃的数据工作区，`--demo --mode recheck`；候选只在既有 WSL/bubblewrap 环境执行。源码入口与原项目不被审批写回。

| 对象/动作 | 真实结果 | 原始资料 |
|---|---|---|
| 内置资料助手 v000 | FAIL；4 个必要业务用例执行，2 通过/2 失败；7 项必要条件未满足 | [完整原报告](review-objects/a8aba1a17b9b470abe12842bc95a9157/versions/v000/reports/z-2026-10-14T03-07-44.759070+00-00-ce30195bc38447f3aa78f9e528679085.json)、[截图](product-final/07-project-fail.png) |
| 提交已有开发者 v001 修订 | PASS；4/4 业务用例真正通过；14 项声明条件满足；独立正常返回/跳转等场景完成 | [完整报告](review-objects/a8aba1a17b9b470abe12842bc95a9157/versions/v001/reports/z-2026-10-14T03-07-47.443838+00-00-3fc8c5b8c40c454c8f2778d0388c36f0.json)、[PASS/PENDING/NOT_APPLIED 截图](product-final/08-project-pass.png) |
| 测试审批、SARIF、已采纳包导出 | APPROVED，`decision_is_test=true`，NOT_APPLIED；这是功能测试，不代替用户采纳 | [审阅完整视图](product-final/review-PROJECT-a8aba1a17b9b470abe12842bc95a9157.json)、[截图](product-final/09-project-approved.png) |
| 上传同一导出包、新目录复检 | PASS，4/4 必要用例，14 条件；同一入口摘要 `7a7dcaf75275c539ef217a1c6f5feafd8bf2d472b2a9a9188ecfcc46fcc22756`，相同项目树 `d323b459d2b9907555b71cabebd8297c3aef2c4b74919da9266e16dbfed58a3b` | [本次复检原报告](product-final/recheck-report-latest.json)、[截图](product-final/10-recheck.png) |
| 无配置小项目上传、向导配置、开始、检查 | FAIL；2/2 业务用例通过，实际返回/日志输出和越界跳转令 4 条件未满足。不是“上传成功即安全” | [样例](sample-upload/tool.py)、[完整报告](review-objects/1a64f06f9c9146399ea8bb327588b5c9/versions/v000/reports/z-2026-10-14T03-07-57.176651+00-00-4f3df69a5fb14dfab5aeb2af052bd94e.json)、[截图](product-final/13-sample-checked.png) |

[浏览器 summary.json](product-final/summary.json) 退出 **0**、零 JS 错误；[由原报告生成的逐例摘要](results.json)。上述手工修订来自已标识的 dev35 v001，不计作当前模型生成。

## view 与只读入口分开

- 最终 Windows ZIP 在**含中文与空格的路径**通过 `start-credproof.cmd --port 0` 启动，自带 Python 3.12.10 `-S`；view 启动未使用 `.venv`、WSL 或模型。不声称本次 Windows 主机完全没有其他 Python。
- [最终包浏览器检查](delivery-current-browser/summary.json) exit 0；[冻结人工审阅显示及禁用检查原因](delivery-current-view/summary.json)，[截图](delivery-current-view/human-review-view.png)：PASS/PENDING/NOT_APPLIED；检查按钮禁用，明确提示使用隔离验收入口。
- 独立 `view-readonly.py` [全路由检查](strict-readonly-final/summary.json) exit 0，所有访问为 GET、无 JS 错误；真实 HTTP 单测确认所有 POST 拒绝。普通 view 中允许的材料/审批操作不等同于这个严格只读服务。
- Windows Edge 实测版本 **155.0.4283.45**。字体检测可用 Microsoft YaHei；SimSun 检测为 false，不写成所有中文字体均已安装。

## 软件回归及命令

`[TEST_PYTHON]` 为已有 Python 3.12.14/pytest 8.4.2 环境；`[REVIEW_STATE]` 为不入 Git 的临时数据目录；`[WSL_RUNTIME]` 为集中配置的已审查运行时。路径映射不改变报告状态、失败原因或源码。

```powershell
$env:CREDPROOF_REQUIRE_SARIF_SCHEMA='1'
[TEST_PYTHON] -m pytest agent_pilot/tests credproof_safety/tests tests -q --junitxml=[REVIEW_STATE]/software-current.xml
# 297 passed, 17 skipped, 1 warning; exit 0
node --check agent_pilot/ui/app.js
node agent_pilot/tests/test_ui_project_verdict.js
# exit 0 / PASS

$env:CREDPROOF_RUNTIME_ROOT='[WSL_RUNTIME]'
[TEST_PYTHON] -m agent_pilot.launch --workspace [DISPOSABLE_WORKSPACE] --demo --mode recheck --port 0
node docs/ui/product-v1/check-product.mjs --base <打印的实际地址> --out [REVIEW_STATE]/product-final --sample [SAMPLE_WITHOUT_CONFIG] --fixed <冻结dev35-v001/tool.py>
# browser exit 0; sample contains synthetic-only code

node docs/ui/console-v1/check-console.mjs --base <view或严格只读服务实际地址> --out <新证据目录>
# corresponding summaries linked above
```

- [最终 Windows JUnit](receipts/software-current.xml)、[实际 stdout](receipts/software-current.stdout.txt)：297 通过、17 跳过。15 项需固定 Gitleaks 二进制而本次未配置，2 项仅 Linux；这些未计为通过。
- [WSL 定向 JUnit](receipts/wsl-unit-readonly.xml)：25 通过，exit 0；Python 3.12.3。范围为 product workspace 与旧 human review。
- [Windows 只读修正定向 JUnit](receipts/readonly-fixed-unit.xml)：25 通过；此前 [PR16 软件 JUnit](receipts/pr16-software.xml) 5 通过，[浏览器记录](pr16-browser/summary.json) exit 0。
- 1 项 warning 来自已安装 DashScope 的 Assistants API 弃用提醒，导入依赖不代表调用云服务或模型。`qwen_agent` 依赖模块本次未排除。
- [当前 wheel 安装来源](receipts/provenance.json) 使用 `python -I`，从 site-packages 导入，核心文件摘要与最终源码一致；[wheel 摘要](delivery/wheel-identity.json)。wheel 仅用于本地安装验证，评委分发为白名单运行 ZIP。

## 运行包与公开材料

[下载 cp17-9f83f84.zip](https://github.com/user-attachments/files/33439551/cp17-9f83f84.zip)

- **11,740,057 bytes**；SHA-256 **`30fb9386885dc104e1749ca21ce6ab49a178d9a278f909daf19d5054f22082ef`**。
- 附带官方 Python ZIP SHA-256 `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`。包内源码 `9f83f84...`，非后补收据 SHA；没有覆盖旧包。
- [匿名附件取件收据](delivery/anonymous-download.json)：未发送 Authorization/Cookie，实际取回 **11,740,057 bytes**，ZIP CRC、源码标识、8 个配置及 SHA-256 均匹配。
- [固定证据提交的匿名 Raw 正文及字节核验](delivery/github-raw-byte-check.json)：`4deb83648ce50caad0893bacbf13dae39b5701ae` 的 README、核心源码和原报告等 9 文件与 Git blob 完全一致；本条及取件收据为后补文档，不改变被测程序。
- [原始与公开派生文件摘要](publication-manifest.json)：原件本地保留，公开只替换精确已知主机路径/hostname 和合成凭据完整值，JSON 正文与源码保留。截图未改动。
- [公开文本扫描](receipts/publication-scan.json) 有 **1 个受控测试字面量命中**：旧失败 JUnit 中 ZIP 拒绝测试输入 `C:/x.py`，不是作者路径，保留其证据语义。评委运行 ZIP 扫描命中为 **0**；不把二者口径混用。

## 尚未覆盖与停止条件

- 本轮没有新模型推理；P2“本地模型候选进入相同审阅链”尚未实现/验收，不使用开发者修订替代。
- 没有重跑 8 目标或 21 历史补丁评测，不改冻结 bench 契约与历史结论。
- 一个过长输出目录名触发 Windows `WinError 206`，保留失败副本，未改全局长路径策略。换用短目录名后构建成功且中文/空格保留；建议短解压根目录。
- 本记录是 Windows+WSL 的有限自测与代码审查，不是第三方全系统认证。PR #17 仅合并到指定前端主线；不自动开展 P2。
