# dev35：AI辅助修复＋程序独立验收＋人工采纳

正式定位：**密证 CredProof——面向Python工具的AI辅助安全修复与证据验收工作台**。

本轮运行时模型调用 **0**。历史AI候选仍为FAIL；开发者通过已安装页面提交新修订，来源为“开发者修订，Codex辅助”。技术检查PASS不会自动采纳；正式对象保持PENDING，原仓库和index未应用。纯模型独立修复PASS经用户批准移出当前必需范围，登记OWNER_APPROVED_SCOPE_CHANGE，历史自动效果没有变成已实现。

## 阅读顺序与版本

1. [当前修订源码](public-evidence/source-bundle/candidate.py)、[AI原件](public-evidence/source-bundle/ai-candidate.py)、[精确差异](public-evidence/source-bundle/revision.diff)。
2. [原AI完整FAIL](public-evidence/workflow/baseline/report.json)、[新修订完整报告](public-evidence/workspace/runs/human-review/939e25f42bb142f39567c5cb644ebc6d/versions/v001/reports/check-01.json)。
3. [真实HTTP审批控制](public-evidence/approval-function-tests/http-controls.json)、[独立消费者结果](public-evidence/consumer/installed-controls/summary.json)。
4. [固定Git字节公开bundle](public-evidence/public-bundle/manifest.json)，后续取件/复检收据在本目录追加。`source-bundle`仅为派生输入，不作为Git换行后可直接复检的成品。
5. [正式说明书PDF](../../../preliminary-candidate/credproof-human-review-dev35.pdf)、[可编辑DOCX](../../../preliminary-candidate/credproof-human-review-dev35.docx)、[正文](../../../preliminary-candidate/manuscript.md)、[讲稿](../../../preliminary-candidate/demo-script.md)、[QA](../../../preliminary-candidate/qa.md)。

实际程序/wheel源码：`50e0d694d1c40352b82853fc62d6df0983240d43`；首次完整材料提交：`9c7419fa055b78de7358fb46c31e99b20c39c099`。后续仅材料、取件和收据提交不冒充新的模型任务。版本`0.3.0.dev35`，范围`AI_ASSISTED_HUMAN_REVIEW`。

## 用户动作、实现与实际证据

| 动作/条件 | 实现位置 | 本轮依据 |
|---|---|---|
| 读AI候选、原始失败、相邻差异 | `human_review.py:open_method/view`；`web.py`审阅API；`ui/app.js`审阅区 | 真实浏览器从dev34记录导入v000；FAIL/测试拒绝/诊断导出 |
| 开发者提交授权入口的新副本 | `human_review.py:revise/_binding` | v001关联v000，DEVELOPER_REVISION；测试/规则/组件均冻结 |
| 原可信检查，不能由人改判决 | `human_review.py:check`→`project.py:check_project` | 4收集/4执行/4通过/0跳过；14必要条件为真，独立正常返回/跳转场景执行 |
| PASS与采纳分离 | `human_review.py:decide/_expected` | 正式PASS/PENDING；专用副本测试身份APPROVED/REJECTED，不代表用户本人 |
| 错误版本/旧页面/材料漂移拒绝 | 同上、`export` | 真HTTP409；代码、配置、组件、缺必要测试四种专用副本UNKNOWN/PENDING，批准及已采纳导出被拒 |
| 重验不恢复批准 | `check/view`与报告摘要 | 测试APPROVED后重新执行原检查，仍PASS但PENDING，决策历史保留 |
| 同对象导出再执行 | `human_review.py:export`→`project_bundle.py` | 固定Git字节派生、匿名全清单取件、新目录原检查；收据追加，不信任保存PASS |
| 导出检查真正发现现有缺陷 | `scripts/run-exported-regression-check.py --installed` | 正常pytest发现1项：固定0、再次引入缺陷1、无关变化0；内部PASS/FAIL/PASS |

上表源码根目录为`credproof_safety/`，界面源码为`agent_pilot/`。核心协议测试：[42项日志](public-evidence/protocol/protocol-final-pytest.txt) / [JUnit](public-evidence/protocol/protocol-final-junit.xml)。协议测试包含替身报告，单独于真实隔离检查统计，不当作漏洞案例或模型成功。

## 安装与实际操作

已验证环境：本台Windows、Python3.12.14、pytest8.4.2、WSL Ubuntu-24.04及既有bubblewrap/rootfs。无模型查看、修订不要求GPU；动态检查要求已有隔离环境，本轮实际均在5090进行，没有跨机器验证。缺隔离明确阻断，不在宿主执行候选。

从本固定提交取件，先核对[wheel清单](public-evidence/installation/wheel-manifest.json)。新数据目录与安装目录分开。以下PowerShell路径均由操作者选择，不能沿用作者路径：

```powershell
python -m venv C:\CP-review\venv
$py = 'C:\CP-review\venv\Scripts\python.exe'
& $py -m pip install pytest==8.4.2 requests==2.34.2
& $py -m pip install --no-deps .\docs\reusable-tool-safety\acceptance\20261010-human-review\public-evidence\installation\credproof_safety-0.3.0.dev35-py3-none-any.whl
& $py -I scripts/prepare-human-review-demo.py --snapshot docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace --workspace C:\CP-review\data
& $py -I -m agent_pilot.launch --workspace C:\CP-review\data --mode view --port 8765
# 已有经预检的隔离环境时，换成 --mode recheck；Ctrl+C停止。
```

打开`http://127.0.0.1:8765/#human-review`，读取已保存工作→查看AI原件/当前修订/报告→输入完整授权入口及理由→提交新修订→重新验收→人工拒绝或确认采纳→导出。演示快照是明确标注的历史材料，没有新模型推理。正式v001可由本人真实审阅；请勿把审批功能测试当本人签字。

运行时位置仍由现有`config/local-runtime.json`或`CREDPROOF_CONFIG`指定，键为`wsl_distribution/wsl_user/runtime_root/program_python`；`runtime_root`须现有可信目录。现场AI建议另需已准备的模型边界和Agent依赖，当前选择使用`CREDPROOF_MODEL_PROFILE=qwen25`，依赖补充见安装收据；本轮只解析历史响应，没有新推理或恢复旧实验预算。

复检公开bundle（不调用模型，但需隔离）：

```powershell
& $py -I scripts/recheck-component-review.py --bundle <已按清单取得的public-bundle目录> --output C:\CP-review\recheck.json --receipt C:\CP-review\recheck-receipt.json
```

必须读新报告里的verdict、pytest逐用例和场景完成状态，命令退出0不等于PASS。

## 来源、材料和边界

原AI候选来自[dev34一次反馈修订](../20261010-feedback-revision/README.md)，保留原UNKNOWN、去围栏后FAIL及该次FAIL。当前人工修订补回os并移除错误的HTTPError转换，直接使用既有read_text/get_json，保留真实资料读取、授权认证、非法输入和跳转异常约定，不返回凭据，不把固定业务结果当修复。

所有人工决策追加保存，绑定原基线/当前对象/配置/测试/依赖/报告。本机记录不是强身份签名或第三方认证；导出不自动应用代码。正式对象仍待本人真实审阅，测试克隆明确标记`approval-function-test`。

公开脱敏只替换列明的本机前缀，不广泛删除代码。[首批派生映射](public-evidence/derivation.json)、[补充映射](public-evidence/supplement-derivation.json)分别记录原始/派生摘要；原件留本地不改写。可移走工作区中的项目/组件字节原样保存，JSON前缀脱敏会改变报告SHA，旧决策不静默重新绑定；长报告文件名仅在快照中映射为check-01.json。格式接收器通用receipt中的source字段描述解析步骤，当前来源以版本DEVELOPER_REVISION及human-review.json为准，不能据此算AI生成。

首次消费者安装缺py.py的环境失败保留于[原始目录](public-evidence/consumer/initial-environment-failure/)，补齐后使用安装版子进程重新执行；不删失败或将环境阻断当安全检出。历史八例、Twine、python-dotenv结果保持各自版本和分母，不并入当前人工修订效果。

本人待办仅为：真实审阅与决定是否采纳、队伍身份/最终命名/声明签署，以及向指导教师/组委会确认AI辅助开发许可。本轮不代签、不提交赛事、不启动5060；结束状态见本目录closeout.md。
