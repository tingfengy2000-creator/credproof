# bounded_patch：一次有限候选生成验证

状态 **NOT_READY_FOR_HANDOFF**。原任务、安全要求、模型与隔离保持；本轮停止这一实现方向的追加尝试，没有运行第2轮、没有5060交接。

## 本轮改变了什么

程序准备授权源码/测试/规则/实际失败 → 本地模型通过 `/api/chat` 的 JSON Schema 生成 PATCH/STOP 数据 → 原宿主执行器校验并应用副本 → 原 `check_project` 自动验收 → 每轮用当前代码和最新反馈重新生成。实际请求没有 `tools`，没有旧循环 system/history；模型不再选择读取/取证工具。旧Qwen-Agent循环和v8原始失败保留。本次只能称 **LLM驱动的受控修复工作流**。

被测源码：`42592c9ff3625e1291d0569ef3f22727b37e7116`；后续提交只是公开材料和收据。实际 Ollama **0.34.4**；`qwen3-coder:30b`、GGUF/Q4_K_M，digest `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca`。CUDA0/5090及只读代码白名单、私有网络依据分别见 [实际服务信息](structured-api-service.json)、[GPU](device-evidence.json)、[边界探针](model-boundary.json)。模型/权重未变化，没有付费API调用。

## 三次生成，不能算三份合格补丁

| 生成 | 来源与实际动作 | 静态代码变化及执行结果 |
|---|---|---|
| 1 | [响应1](model-trace/model-01-response.json)，接受候选1、程序验收FAIL | 返回credential改成null；新增目录前缀与URL判断，但读取未提供的`CREDPROOF_ALLOWED_DIRS`，错误拒绝正常资料文件；仍有敏感日志、缺端口/重定向限制。实际正常文件和允许服务没有完成，不能宣称输出/网络已修好。 |
| 2 | [响应2](model-trace/model-02-response.json)，接受候选2、程序验收FAIL | 在候选1上新增未提供的`CREDPROOF_FORBIDDEN_DIRS`判断，没有修复正常路径误拒，也没有修好日志/重定向。两项正常业务测试再次失败。 |
| 3 | [响应3](model-trace/model-03-response.json)，宿主REJECTED/NO_CHANGE | 说明文字声称改进，但代码与候选2完全相同；不新增候选或验收。 |

实际统计：**3模型请求/3份usage、3生成、0格式纠正、0 native工具请求、3程序准备动作、3提交尝试、2接受候选、2自动验收FAIL**。任务25.791秒，`INCOMPLETE / STOPPED_GENERATION_BUDGET`；不是格式、输入预算或超时阻断。两次pytest均真实收集并执行4项，2通过2失败；这不是50%安全完成率。没有PASS、导出或新目录复检。

## 可核查的入口

1. [冻结](freeze.json)、[实际命令/退出码3](command-receipt.json)、[逐任务与失败分类](summary.json)。上限为3生成+1格式纠正/总请求4，16K上下文、2048输出、512预留、输入上界13824；单请求120秒、任务900秒。
2. [原件真实FAIL](initial-report.json)，[候选1源码](candidate-01.py)/[验收1](verification-01.json)，[候选2源码](candidate-02.py)/[验收2](verification-02.json)。真实返回、异常、文件和服务记录、逐nodeid pytest观察都在完整报告内。
3. [第二次实际请求](model-trace/model-02-request.json)和[第三次实际请求](model-trace/model-03-request.json)：分别携候选1/2正文与对应FAIL，没有从原件重新开始。[完整程序动作](program-trace.json)不是模型工具调用；模型reason不能覆盖真实验收或产生不存在的代码变化。
4. [无模型预检](protocol-preflight/summary.json)：原件、v8失败、v7候选2和格式纠正分支的保真/预算通过。方法是完整序列化UTF8字节保守上界，不冒充服务token；完整待发payload同目录。它不算模型或安全任务成功。
5. [软件回归](regression-receipt.json)、[输出](regression.txt)、[JUnit](regression.junit.xml)。STOP格式与真实代码分支存在性经过软件检查；本任务模型未选择STOP，不声称实测了模型STOP行为。
6. [完整清单](manifest.json)、[原件/公开件摘要映射](derivation-receipt.json)。公开文件为结构化脱敏UTF8/LF派生件，原件保留；清单要与固定Git blob字节核对。

## 失败归属与本轮决定

- **格式**：三份PATCH完整且严格合法，没有截断、未知字段、工具调用或格式纠正。
- **输入组织**：当前代码、必要测试、规则及反例在实际请求中；继承的反馈摘要没有带`raised.message`，也没有显式解释配置`data`与运行时`/tmp/lab/data`的映射。因此不能把全部失败归为模型能力不足，或声称运行时信息完整到没有任何改进余地。完整报告保留了这些信息。
- **代码语义**：模型猜测未提供的环境变量；`abspath`+字符串前缀没有可靠路径归属语义；URL判断遗漏端口并继续使用自动跳转；敏感日志保留。第二份未处理真实正常业务失败，第三份原样重复。这些都是实际模型输出，不是人工补丁。
- **运行/验收**：本地GPU和schema接口实际运行；两份候选在原隔离检查器中得到FAIL，没有环境执行错误。提前目录拒绝遮住网络/日志执行，未观察到这些通道不能当安全修复证据。

本轮明确停止追加生成。**后续只建议一项待用户批准的决策：使用经过验证的文件/HTTP访问安全组件辅助生成**，针对已经反复出现的路径归属与重定向语义困难，而不是再添加相同工具拒绝规则或随机重跑。这尚未实施或获批。当前缺口仍是登记任务的真实模型合格候选、同对象公开复检以及成功后对应安装/页面入口验证；没有降低交接条件。
