# dev33：一次有上限的编码模型对照，已结束

**NOT_READY_FOR_HANDOFF / MODEL_COMPARISON_CLOSED_UNSUCCESSFUL**。

固定模型 `qwen2.5-coder:32b-instruct-q4_K_M`，manifest digest `b92d6a0bd47ee79114298de0177bf920c05a706d12633950b3936778492bef41`。Ollama 0.34.4，模型原生模板，CUDA0/本台RTX 5090。唯一非项目结构化预检成功；唯一正式页面任务只生成一次，产生一份不同候选、一次程序自动验收，结论 **UNKNOWN**，不是修复成功。

## 一页结论

| 事项 | 实际结果与依据 |
|---|---|
| 被测程序 | `a780b9e6543355c2108c1d41e43a8dccd7c2e0c1`；安装wheel构建源 `ad826dae2d43ee0c0ec636f59a48f9325bcd14df`，受影响12份程序文件相同。后续只增加证据/说明和派生脚本。[对应收据](closure/program-source-equivalence.json) |
| 模型/边界 | [正式服务身份](formal-page/structured-api-service.json)、[实际模板及参数](formal-page/model-show.json)、[CUDA日志](formal-page/device-evidence.json)、[Ollama网络/挂载探针](formal-page/service-boundary.json)。仅挂载选中manifest及5份引用blob，未开放整个模型目录；旧Qwen3保留。 |
| 唯一结构化预检 | 1次无项目代码请求，返回 `{"ok":true}`；37输入/9输出tokens，约10.4秒含加载。`/api/ps`报告模型显存22,125,425,458 bytes，16K上下文。[请求](structured-preflight/request.json) / [响应](structured-preflight/response.json) / [收据](structured-preflight/receipt.json) |
| 正式输入 | 原始assistant-original/p01，原规则/测试/组件1.0.0；[冻结](formal-page/freeze.json) / [实际请求脱敏件](model-trace/model-01-request.json)。无tools字段，无参考补丁；系统指令、工作包构造与上一轮保持一致，[等价依据](preparation/work-package-equivalence.json)。 |
| 真实计数 | 1次生成/1份usage、1份接受候选/1次自动验收、0格式纠正、0 native工具；4次程序RPC为取证、读取入口、读取测试、提交并自动验收。[机器记录](summary.json) / [程序轨迹](formal-page/program-trace.json) |
| 候选具体变化 | [原件](input-materials/original-tool.py) → [候选1](candidates/candidate-01.py)：增加 `credproof_access.read_text/get_json` 调用，保留正确的凭据变量名读取表达式，删除日志与返回中的凭据表达式。这些只是源码变化，不能称已经验证修好。 |
| 实际阻断 | 候选第1和30行含字面量Markdown围栏。Python在第1行 `SyntaxError`；pytest退出2、收集/执行均0，入口场景0，可信判决UNKNOWN。JSON格式有效，源码无效；不是超时、上下文不足、依赖安装或隔离启动失败。[完整验收](candidates/verification-01.json) / [最终报告](formal-page/final-report.json) |
| 其他静态问题 | 第26—27行引用未绑定的 `urllib`，并将要求保留的HTTPError改抛ValueError。这些路径没有执行，未倒填为动态FAIL；未剥除围栏或替模型修代码。[来源与分类](closure/conclusion.json) |
| 页面与结束 | 安装版HTTP页面→`web_repair`→`request_repair`→原隔离bounded_patch，页面记录对应本次真实模型、候选与UNKNOWN。[页面终态](formal-page/page-final.json) / [实际子进程来源](formal-page/installed-child-origin.json) / [启动记录](formal-page/launch.json)。程序已结束不等于修复完成。 |
| 导出与复检 | 未取得可信PASS，未制作成功bundle、未执行成功候选公开取件复检。旧失败bundle保留；不拿它或人工控制代替本轮结果。 |

## 预算、程序与模型分别统计

正式预算冻结为3次实质生成、1次格式纠正、最多4次模型请求、3候选/3验收，16,384上下文、2,048输出、512安全预留、120秒单请求、900秒任务。宿主独占持久化claim已消耗一次预检、一次正式任务；换目录/重启不恢复名额。[登记状态](registration-state/ledger.json)、[正式claim结果](registration-state/ledger.formal.claim.result.json)。

正式请求生产序列化为13,495 UTF-8 bytes；保守UTF8_WIRE_BYTES上界13,495，输入限制13,824，含输出和安全预留为16,055≤16,384；没有复用旧模型usage。服务实际返回3,314输入/363输出tokens。[预算](model-trace/model-01-input-budget.json)、[响应与usage](model-trace/model-01-response.json)。模型处理约17.52秒（服务加载约10.15秒）；repair约20.16秒，HTTP页面轮询约26.14秒，计时范围不同。

JSON通过原解析器，因此没有触发JSON格式纠正；自动验收收到UNKNOWN后按既有协议停止，剩余额度未使用。未修改提示词、剥除代码围栏、重新启动任务或尝试第二种权重。不能把剩余预算当作已生成次数，也不能据这一次无效源码结果给两模型作语义能力排名。

必要软件回归为55通过；另一次17项身份/页面回归与前者重叠5项，不能相加为72独立项，更不是安全案例或模型成功数。早期工具文件系统沙箱造成的28通过/22失败/5错误保留；重新获准读取同一测试后55通过。一个dashscope依赖弃用warning不涉及付费API调用。[原始范围及退出码](preparation/regression-provenance.json)。JUnit请使用 `*-structured.xml`，初次文本脱敏生成的不合法XML被保留并标为已替代派生件。四份无模型消息预算预检见[摘要](preparation/summary.json)，不计为正式模型推理。

## 取件与来源

- [固定模型薄适配](../../../../../agent_pilot/model_config.py)、[原生成接口](../../../../../agent_pilot/bounded_patch.py)、[边界/可信调度](../../../../../credproof_safety/agent.py)、[页面薄适配](../../../../../credproof_safety/web_repair.py)。
- [真实命令与退出码](closure/commands.json)、[最终安装收据](preparation/install-final-receipt.json)、[主进程来源](preparation/installed-program-origin-final.json)。新venv复用已准备第三方依赖，不宣称从外网重新解析全套依赖。
- [官方下载及完整校验](preparation/download-receipt.json)、[WSL全部blob复校验](preparation/native-model-install.json)、[同一blob下载续传说明](preparation/download-continuation.json)。下载准备与推理分开；未上传权重。
- [正式原始/派生映射](derivation-formal.json)及[补充脱敏映射](closure/derivation.json)、[请求及候选字节来源](closure/request-provenance.json)。保存请求JSON、重建生产HTTP序列化和公开脱敏件字节不同，不能共用哈希。只映射已知宿主前缀及合成值/缩略片段，普通源码保留，包括无效围栏。原件保留本台5090。
- `manifest-formal.json`为首次本地派生清单，随后补充了缩略片段脱敏；最终公开文件应按另附 `published-manifest.json` 的固定Git blob字节核对，不使用旧清单认定新字节相同。

旧模型上一轮3次相同输出、1候选/1次FAIL及错误getenv表达式仍在[dev32历史入口](../../20261009-component-assisted/public-evidence/README.md)，没有重跑或拼接。本轮新模型在源码中使用组件并保留正确读取表达式，但无可执行的合格候选，不能称修复增量成立或更强。

**本轮对照关闭。唯一后续决策：暂停这条自动生成效果优化路线，等待用户裁定后续资源或产品范围。** 不自动继续改提示词、换模型、重跑或启动5060。当前仍缺真实模型合格候选、同对象公开PASS复检及成功效果对应的最终入口证据。
