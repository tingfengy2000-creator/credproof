# External Agent run v2: bounded feedback (2026-10-04)

这是在 v1 失败记录之后、只收紧模型可读材料和反馈大小的一次真实复测。仍使用
`python-dotenv` v1.2.2 固定上游快照，目录越界缺陷是独立副本中的人工注入，不能写成
上游漏洞或 CVE。

## 运行口径

- Qwen-Agent + Ollama + 本地 `qwen3-coder:30b`，未调用付费 API。
- WSL/bubblewrap 隔离预检通过；未使用宿主机任意 Shell 或公网。
- 最多 12 次模型调用、3 个候选，实际 12 次调用，服务端累计报告的 token 用量见
  [summary.json](summary.json)。
- 模型可见的规则、允许读取路径和压缩后的实际证据由执行器生成；自然语言不直接执行。

## 真实结果

模型先读取了实际违规证据，随后读取入口和小型适配测试。它提交的补丁只增加了“文件存在性”
检查，没有限制目录，也没有消除返回凭据；程序对这份补丁执行了三次真实验收，均未通过
`no_forbidden_file_read` 与 `no_credential_output`。模型重复提交同一候选，达到候选预算后
任务以 `INCOMPLETE` 结束。最终程序判定为 `FAIL`，不是成功修复。

完整候选和第一次复核见 [candidate-01.py](candidate-01.py) 与
[verification-01.json](verification-01.json)，本次机器可读摘要见 [summary.json](summary.json)。
`model-trace-result.json` 保留了模型停止原因和实际调用记录；完整绝对路径轨迹仍只保留在
开发机 `_runs/external-dotenv-agent-v6`。

## 这次复测说明什么

修正后的工具协议和预算控制已经能够把真实失败补丁挡在最终结果之外，也能把模型可读规则与
实际证据区分开。但在这个外部接入场景，Agent 仍没有形成合格目录边界修复；不能宣称
“外部项目自动修复已完成”。因此初赛主展示应使用已验证的 h01/h03 Agent 案例与
`20261004-external-dotenv-v4` 的模型无关外部检查，不能把本条失败记录藏掉或与成功记录拼接。
