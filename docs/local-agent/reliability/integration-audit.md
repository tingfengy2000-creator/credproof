# 本地 Agent 集成边界复核

核对时间：2026-09-29T09:54:38.433347+00:00。复核类型：**Codex 辅助的内部源码复核**，不称独立人工评审、第三方安全审计或认证。当前 HEAD 为 `b4cb91ef67ae2d14d6cc37f9e18cf6c23e36e8ea`；本次按以下工作区文件字节检查，包含主任务在真实运行完成后的分项投影修正，不能把修正追溯成历史实验所用代码。

| 文件 | 本次读取 SHA-256 |
|---|---|
| `agent_pilot/web.py` | `b4380be0627aa504aed8c20737d40877ba709ae5c24bc7e72726e7e83c3af404` |
| `agent_pilot/bundle.py` | `0dd94e02e5cf89d9ddd5de9a82b60eb8f918d2db206f235c5852fbe7263ec431` |
| `agent_pilot/reliability.py` | `5b64b5e2b9067cd57dd9f5f31a010c6d14a43ab2c394cdb1f3e315276a66d7dd` |
| `agent_pilot/ui/app.js` | `6eab63234442fbd827bfafb7743429267cf8a60ee8fa1cec19ec645902a16b3d` |

范围为 web/bundle/reliability 及相应 UI 展示路径；读取现有测试和边界文稿。没有运行模型、修复方法、候选代码、隔离探针或浏览器。只新增本说明，并按主任务追加授权在 `test_reliability.py` 增加一个纯单元回归；没有修改上述业务源码或实验记录。

## 发现与处理状态

### 1. UNKNOWN 试验被错误投影为分项 PASS：已修正，纯单测通过

原 `GovernedSession.verify` 仅凭 `checks_run == 13` 且无 `MATRIX_COVERAGE` 判断“完整”。若 13 个输入槽位都存在，但其中一条 transcript 由裁判判为 `UNKNOWN/INVALID_TRANSCRIPT`，整体仍为 UNKNOWN，安全、功能和覆盖分项却可能被投影成 PASS。这是展示证据充分性的实质错误，不能靠顶层 UNKNOWN 为分项绿标背书。

主任务已收紧 complete 条件：排除 UNKNOWN trial、整体 UNKNOWN、MATRIX_COVERAGE 与 INVALID_TRANSCRIPT。新增回归 `ReliabilityTests.test_unknown_trial_projection` 构造 **12 PASS + 1 UNKNOWN** 的人工聚合记录，要求 source profile 可 PASS，credential-channels、behavior、coverage 必须 UNKNOWN。该用例于 WSL Python 执行通过，`Ran 1 test ... OK`，exit 0：

```text
wsl --exec bash -lc 'cd /mnt/e/比赛/密证_CredProof-local-agent && /home/tingfeng/credproof-agent-runtime/venv/bin/python -B -m unittest agent_pilot.tests.test_reliability.ReliabilityTests.test_unknown_trial_projection -v'
```

该测试用 mock 替代底层 verify，只检验投影，**不是一次真实模型或隔离验证**。本复核未重新读取整轮实验核算 UNKNOWN 数量；主任务另负责实际实验汇总。旧记录保持原样，不应覆盖。

### 2. UI 可能省略早期、仅存在于工具参数的模型误报：待补展示或明确边界

`reliability.py` 的 verify 工具每次将 `session.assessment` 覆盖为当次 `initially_leaking/diagnosis`；最终报告中的 diagnosis 因而是最后一次。完整工具轨迹仍保存每次原始参数，这本身不丢审计数据。

当前 `web.model_notes` 提取保存的 assistant **content** 和 submit_patch **rationale**，但不提取早期 verify_patch 的诊断参数。如果模型先在 tool-only 的 verify_patch 中给出错误泄露判断，后又用同一工具改为正常，页面会显示最后诊断；更早的错误可能既没有普通 content，也没有 submit rationale，因此没有出现在“原始模型文字”区域。当前源码未提供能保证该种判断全部显示的路径；这是静态可达情形，不表示本复核已证明某一真实运行出现该遗漏。

最低补救是把 verify_patch 的诊断历史作为模型判断展示，保留调用顺序且不赋予程序事实地位；也可暂时明确页面只展示部分模型轨迹，统计时必须检视完整 tool_trace 和响应文件。**最后 initially_leaking=false、系统拒绝修改、最终原件 PASS，均不能据此记为“模型从未误报”。** 若作出完整轨迹展示或零误报结论，此项为阻断。

## 源码路径支持的结论

- **HTTP 权限边界有限且明确。** 只绑定 127.0.0.1；校验 Host/Origin/Sec-Fetch-Site；创建接口仅接收登记 case_id，拒绝路径、代码、判决与多余字段。调用子进程使用固定 argv，不经 shell 拼接用户输入。静态文件和运行 ID 路由固定。`confined` 拒绝链接/目录联接，材料导出再次检查。没有发现通过已定义 HTTP 输入绕过登记范围的路径。
- **UI 错误不会自动变成功。** 非 2xx、不可解析响应、未知顶层判决会触发错误横幅、暂停轮询、把保留内容标为上次状态；任务结束、程序验收、模型判断分开。缺少最后结果时保持未验收；非零子进程退出不作为成功。此结论来自代码阅读，未代替实际浏览器验收。
- **修改许可由程序决定。** 所有方法使用相同的 source/rules/conditions 证据约束。未确认禁止通道中的完整凭据泄露时，submit 在写候选前拒绝；合法认证实参不属于禁止通道。候选的观察不能冒充原件证据。模型没有写原件、改裁判、改规则或选择任意执行目标的工具权限。
- **完成绑定当前选择对象。** check 对比选定候选 ID、源与规则绑定，验证旧候选不能完成新候选。必要检查 UNKNOWN 不产生完成。C 的可信 callback 停止后续模型/工具调度；B/D 只有模型正常 COMPLETED 且 JSON 可解析才采纳提案并检查。独立 final PASS 不把预算退出升级为完成；复验不是 PASS 时撤销先前完成标签。
- **导出不是验收。** `export_bundle` 要求源、候选与规则哈希匹配，按白名单复制材料；拒绝识别到的 private trial envelope，脱敏合成凭据。导出时不运行模型或候选，包内说明不把打包成功当验证成功。
- **fresh 复检不信旧 PASS。** `recheck_bundle` 固定使用已加载的可信 judge，先检查 profile，然后重新执行固定 13 条矩阵；矩阵不从 report/configuration 选择。旧报告改成 PASS 无法替代重新执行。缺设施或不可用材料为 UNKNOWN；出现明确反例为 FAIL。候选改变可以让旧报告失效同时获得新的结果；复检中的材料漂移降为 UNKNOWN。fresh 结果不会回写历史任务完成状态。
- **模型误报与系统保护必须分开统计。** 授权门同时约束 A/B/C/D，有助于限制对正常代码的实质修改，但这不是模型诊断正确率。被拒提案也不自动等于误报：例如只差末尾换行的提案必须按原始理由与实质行为分析。初始三条件共享给各方法，不能记作 C 独立发现；D 与 C 仅最大输出预算相同，实际调用、输入/输出与运行时间不是精确匹配。

## 可接受的已披露限制

1. 固定需求、裁判、隔离设施和本地操作者受信任。哈希是变化检测，不是签名、来源认证或抗可信组件被整体替换的证明；任意第三方包须先独立确认 verifier。CLI 接受操作者明确给定的本地路径，HTTP 不开放任意路径或 ZIP 上传执行。
2. “便携复检”指不需要原 checkout 和 Qwen 依赖，仍依赖指定且已准备/通过探针的 WSL/Linux 隔离设施，并非下载即在任意电脑可运行。缺少设施不能回退宿主执行。
3. 只支持已审查的有限 Python 小工具、合成运行时完整凭据的直接匹配；不覆盖编码、部分泄露、隐蔽通道或任意恶意程序。候选与采集 harness 共进程的 oracle 限制仍然存在，宿主隔离不等于该 oracle 对任意 Python 对抗代码不可伪造。
4. web 的运行设施 ready 只是只读存在性和已存 gate 身份观察；不等于本次模型/隔离验收。网络请求超时不代表任务已被杀死；服务端操作锁保持串行。该锁是本服务实例内的锁，不声称约束另行手动启动的 CLI。
5. UI 历史记录与复检绑定明确的源/候选身份和时间，不是持续监控。页面只接收服务端既有材料；不负责任意用户仓库、真实账户凭据有效性或远端撤销。
6. 本轮原始案例、保留模板与源码均有 AI 辅助构造。工程留出结果不得包装为与开发者无关的人工盲测；来源和 AI 参与说明仍须保留。

本次没有发现可通过现有受限工具直接绕过修改授权或把旧候选验证冒充当前候选完成的实际路径；这是有限源码复核结论，不是无漏洞证明。剩余 UI 判断历史遗漏应按上文处理，完整原始记录应继续作为最终统计依据。

## Integration correction after this read-only audit

The UI now retains every verify_patch diagnosis (including repeated and earlier true values), controlled-test hypothesis and proposal rationale. Ten web boundary/control tests passed. The final label is not used as the count of all earlier false alarms. UNKNOWN component projection is corrected with a dedicated unit regression; frozen holdout results are not rewritten.
