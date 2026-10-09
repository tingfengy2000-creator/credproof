# 本轮收尾

- 模型来源：历史 qwen2.5-coder:32b-instruct-q4_K_M；任务 `live-c5e9217f868f4681a94bdda49c914e6e`，原被测源码 `a780b9e6543355c2108c1d41e43a8dccd7c2e0c1`。原任务 UNKNOWN 不变。
- 本轮实现：规则/准备/唯一检查脚本固定为 `56815b4548c09bd4d8ee995f8563e563ebd0158e`；原检查器及组件未变，安装dev33来源见 [收据](public-evidence/installed-origin.json)。后续证据/文档提交不冒充原模型被测版本。
- 实际计数：新增模型请求0，派生候选1，原 `check_project` 调用1；格式协议13项通过，不是13项安全样例。
- 归一化：仅移除唯一完整外层围栏13 bytes，内部源码不变；静态语法通过。
- 派生验收：FAIL；4项业务实际执行，3通过1失败；跳转场景实际执行但错误异常类型；pytest回溯凭据输出被检出。
- 安装版解析接入：未执行。FAIL停止条件已触发，安装版/页面原UNKNOWN保持；未追加模型、人工修复或第二次验收。
- PASS导出、匿名bundle取回复检、页面成功验证：未执行，没有PASS不得补齐。
- 原始响应/候选/UNKNOWN报告完整保留，摘要核对不变；[派生与原始摘要](public-evidence/derivation.json)区别列出。
- 公开证据准备第一次因主机名脱敏标记含XML特殊字符而解析失败；只修公开元数据的XML安全标记并重新导出，首次部分派生件本地保留。没有重新执行候选或模型，未改变任何检查结果。
- 状态：**NOT_READY_FOR_HANDOFF**；本轮已结束，不启动新实验或5060交接。当前缺口为生成源码异常处理及输出不满足原要求，而不是围栏仍阻止执行。

完整入口：[README](README.md)；[结果](public-evidence/summary.json)；[完整报告](public-evidence/report.json)。
