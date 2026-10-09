# 组件辅助的 LLM 受控修复工作流（dev32）

本轮采用同一本地 `qwen3-coder:30b` 的 `bounded_patch` 生成策略，增加 `component_assisted` 工作包。旧 Qwen-Agent 工具循环、失败记录和候选版保留。模型没有工具调用权，程序准备材料、应用授权入口修改并安排可信验收。

## 实际分工

| 工作 | 实现与依据 |
|---|---|
| 开发者确认业务与权限 | 原 `credproof.toml`、四项必要业务测试、独立正常返回及跳转场景保持；未提供参考补丁 |
| 程序生成运行时规则 | `credproof_access/contract.py:build_contract` 同时返回实际环境映射与公开契约；目录映射到 `/tmp/lab`，代码及 cwd 为 `/tmp/project`；端口每次重新分配 |
| 本项目通用组件 | `credproof_access.read_text/get_json`，版本 1.0.0；真实目录归属与初始 HTTP 目标限制；关闭自动跳转。组件不实现资料助手业务、不决定 PASS |
| LLM 业务修复 | 每轮收到当前入口、必要测试、运行时契约、API、真实反馈及余额；自行连接组件、保留业务、清除输出凭据 |
| 独立判断与交付 | 原 `check_project`、审计事件、模拟服务回执、逐 nodeid 与独立场景；导出携带同版组件，复检重新执行，不读取旧 PASS 充当新结论 |

## 组件 API 与权限

```python
from credproof_access import read_text, get_json
text = read_text(path)               # 一次文件操作示例
data = get_json(url, credential)     # 一次认证请求示例
```

`read_text` 对绝对/相对路径解析后检查祖先关系，拒绝跨目录、`..` 与符号链接越界，拒绝为 ValueError。`get_json` 检查协议、主机、有效端口及路径范围，拒绝初始目标为 ValueError；允许的跳转入口会真实收到请求，然后 HTTPError 中止跳转。组件不接收模型或业务请求提供的权限表。

可信 runner 在候选导入前，从只读最小挂载加载并核对组件版本/文件摘要，安装本次不可重复初始化的策略；项目同名模块不能覆盖该预加载组件。缺组件、版本不符或策略加载失败阻断执行，没有宿主执行或旧实现回退。导出记录组件、契约和策略摘要；新目录重新分配端口与合成凭据，执行同一语义规则。

这是可信执行器配合组件的工程约束，不是针对恶意 Python 内省/篡改的不可绕过沙箱。Python 审计、原生调用、子进程及 TOCTOU 的既有边界保留。模型即使导入组件，也必须通过全部独立检查。

## 运行与证据

- 准备检查：`python scripts/check-access-components.py <new-output>`，必须在本台5090既有 WSL/bubblewrap 环境；不调用模型。
- 消息预检：`python scripts/preflight-component-assisted.py <new-output>`；只是保存状态的协议构造，不执行候选。
- CLI：`python -m credproof_safety repair --strategy bounded_patch --config <registered-config> --output <new-report>`。
- 页面：当前登记 p01 通过 `web_repair → request_repair(strategy='bounded_patch')`；历史回放仍独立标识。
- 实际正式任务由 `scripts/run-component-page-task.py` 在新安装环境，通过真实 HTTP 页面 API 发起一次；预算：3次生成、最多1次格式纠正、4次请求、3候选/3验收、16K上下文、2048输出、120秒/请求、900秒任务。原生模型工具调用为0。
- [当前证据](acceptance/20261009-component-assisted/public-evidence/)记录组件检查、原件 FAIL、完整实际消息、预算与正式失败结果；历史不合并统计。

同时改变运行时说明和组件接入，不能据一次任务归因某个因素带来提升，也不能推出泛化成功率、独立盲测或人工时间收益。开源模型、Ollama、Qwen-Agent归属不变；本轮实际推理链为本地结构化生成，不声称模型自主安排全部工具。AI辅助参赛许可仍由参赛者确认。

## 本轮实际结果与决定

固定源码 `7011959e795f3bde442d3f4899ea5097ab42528a` 的新安装页面发起一次正式任务：3次生成，1份接受候选/1次原检查器FAIL，2次重复输出NO_CHANGE。候选没有接入上述组件，且将凭据值当环境变量名引发KeyError；必要业务及场景失败。组件的12项隔离测试通过不代表这份模型候选成功。完整计数、源码与报告见证据入口；同一失败候选公开取回后再次执行仍FAIL，未取得公开PASS。

保持NOT_READY_FOR_HANDOFF。唯一后续建议是由用户批准后，对同一工作包进行编码模型对照；本轮没有更换/下载模型或追加正式任务。页面/安装调度已执行，当前阻断是合格模型业务修复及同对象PASS复检，不能以程序回归数量代替。
