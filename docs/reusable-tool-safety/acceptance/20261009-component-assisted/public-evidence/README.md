# dev32：运行时契约、访问组件与真实页面任务

状态 **NOT_READY_FOR_HANDOFF**。这是组件辅助的LLM受控修复工作流工程验证，未取得合格模型修复。被测源码 `7011959e795f3bde442d3f4899ea5097ab42528a`；准备提交 `d2812d57bcc9549ed30ac8a0a20ec40d837def9c` 发生预检阻断后未调用模型；`9bcc23087ca203cfb13dfe2b92bc9e185c7f380d` 固化本轮正式原始材料的公开派生件。后续仅交付、文档与Git字节派生，不冒充新推理。

## 一页结论

- 程序从实际目录、环境和本次模拟端口生成运行时契约；固定组件只提供受限文件读取和HTTP JSON请求，不代写资料助手业务，不输出验收结论。[方法与API](../../../component-assisted.md)
- 组件在既有WSL/bubblewrap隔离中12项实际测试通过；只安装组件、不修改原件，原件仍FAIL。原检查器保持独立，不以import组件替代安全/业务检查。
- 新安装页面显式派发bounded_patch/component_assisted；唯一正式任务为 **3次生成、3份usage、0原生模型工具、6次程序RPC（3准备＋3提交）、1份接受候选、1次自动FAIL、2次NO_CHANGE**。STOPPED_GENERATION_BUDGET。页面COMPLETED仅指进程结束，不是修复成功。
- [候选](candidates/candidate-01.py)删去显式敏感日志参数和返回credential字段，但把凭据值当环境变量名，KeyError再次暴露秘密；没有调用访问组件，原open/urlopen仍存在。正常/跳转场景提前失败，不能算边界保护成功。[静态与动态对照](source-review.json)
- 未取得可信PASS，不伪造成功导出或公开PASS复检。失败候选交付检查单列，不能当成功效果。

## 真实任务：完整输入、输出与判决

[逐任务计数](summary.json) / [冻结与页面任务](formal-page/) / [原件检查](formal-page/initial-report.json) / [候选完整验收](candidates/verification-01.json) / [最终报告](formal-page/final-report.json)

[全部3次实际请求、响应及预算](model-trace/)保留当前源码、测试、契约、API与FAIL；请求无tools。原始线上字节/摘要与脱敏派生字节分开记在[映射](derivation-formal.json)，不把公开文件大小当线上请求大小。模型服务实际CUDA0/5090、固定qwen3-coder:30b Q4_K_M，digest与设备证据见formal-page；作品本次没有调用付费API。

4项必要业务测试真实执行：1通过（无效输入），3失败（正常业务、输出与边界）；正常及跳转入口KeyError在真实文件/服务动作前发生。程序拒绝两次重复代码，模型reason不能改绿。

## 组件、协议与软件回归（均非模型效果）

- [最终12项组件执行](component-controls-final/component-execution.json)、[独立断言/回执](component-controls-final/summary.json)、[未改原件仍FAIL](component-controls-final/unchanged-original-report.json)。不同目录documents/private、非默认凭据变量、真实认证/跳转、禁止服务无请求；范围见逐项断言。
- [首次只读rootfs挂载失败](component-controls/component-execution.json)保留；修正为私有/tmp只读最小挂载，无宿主回退。
- [四份无模型预算预检](preflight/summary.json)：输入上界13398/12896/13206/13338，限制13824，输出2048＋预留512，总上下文16384。纯协议，不执行候选。正式三次输入上界13477/13192/13271，全部通过，无预算/超时/格式阻断。
- [软件回归收据](regressions/receipt.json)：初次93通过2失败（旧完整执行测试替身缺必要场景），仅补替身后95通过；原失败stdout/JUnit保留。安装预检路径修正后20项相关测试通过，见regressions/dev32-preflight-fix.*。一条dashscope弃用warning不代表调用云服务。

## 安装与页面来源

[wheel收据](install-receipt.json) / [安装后预检](install-preflight.json) / [实际子进程来源](formal-page/) / [额外导入来源核对](install-origin-probe.json) / [实际依赖](installed-requirements.txt) / [编码与脱敏补充](derivation-install-addendum.json)。wheel 373736 bytes、SHA256 `3bab6e34bc46600bf9654e51ad3ce13f93a4451ecfa9ac75a4ffc96cfe7ec894`；相关安装模块摘要与7011959源码一致。额外导入探针不是新页面推理。

[预模型启动阻断](pre-model-startup-block/)先保留，修正安装预检使用已安装runner后才登记实际任务。旧任务零推理；正式任务未追加重试。页面launch→安装web_repair→request_repair明确bounded_patch；浏览器只能登记ID，不能输入Shell/路径。

## 失败对象交付

[本地失败复检](failed-candidate-local-recheck.json)仍FAIL。[source bundle](failed-candidate-source-bundle/)仅是Git字节派生的输入档案：其中原本地清单可能对应CRLF，**不能直接当作公开可复检包**。可消费材料只使用随后派生的[LF公开bundle](failed-candidate-public-bundle/)，清单由固定Git blob生成，组件依赖随包。[固定47387c3匿名取件与新目录动态收据](public-retrieval/summary.json)：13份Raw文件与Git/完整清单逐字节一致；安装程序在新目录重新执行，仍为FAIL，旧报告适用且材料完整。必要测试1通过3失败；这不是UNKNOWN或读取旧FAIL充数，更不是成功修复。完整新报告与pytest逐nodeid事件见[recheck.json](public-retrieval/recheck.json)。

## 决策与边界

契约与组件同时改变，不作因果归因或泛化率主张。组件1.0.0仅经过所列范围测试，不是恶意Python不可绕过沙箱；TOCTOU、原生调用等既有边界保留。模型没有完成业务接入，组件单测与95项软件回归不能替代修复成功。

建议的唯一后续决策：由用户批准后，对同一冻结工作包做一次编码模型对照；本轮未更换、下载模型或追加推理。不再以追加一条提示词作为交付。开源归属及AI辅助参赛许可边界不变，后者仍由参赛者确认。
