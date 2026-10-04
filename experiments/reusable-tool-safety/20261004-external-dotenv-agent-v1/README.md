# External Agent run: python-dotenv adapter (2026-10-04)

这是一次真实的本地模型修复运行记录，不是回放，也不是成功案例。被测项目是
`python-dotenv` v1.2.2 的固定上游快照；目录越界读取缺陷由本项目在独立副本中人工注入，
不能表述为上游漏洞、CVE 或企业部署问题。

## 运行条件

- Qwen-Agent + Ollama + 本地 `qwen3-coder:30b`；本次未调用付费 API。
- WSL/bubblewrap 隔离预检为 `ready`，模型没有宿主机任意 Shell 或公网权限。
- 模型调用 3 次，累计服务端报告 2,671 tokens，约 56.1 秒。
- 工具顺序：`read_code` → `get_evidence` → `submit_patch` → `verify_patch`。

## 实际结果

初始 `get_evidence` 真实确认了两个问题：禁止文件读取和凭据返回。模型提交了一个候选补丁，
但程序验收将其判为 `FAIL`，失败项为 `entry_completed`。补丁猜测了与当前实验契约不一致的
固定目录，使用简单 `startswith` 判定路径，并把入口原本应保留的正常行为改成 `ValueError`。
因此它没有因为“看起来脱敏”就被接受。候选代码见 [candidate-01.py](candidate-01.py)，
程序复核材料见 [verification-01.json](verification-01.json)，机器可读摘要见
[summary.json](summary.json)。

模型随后因保守输入预算结束，任务状态为 `INCOMPLETE`。这次运行没有第二个候选，不能写成
“Agent 修复成功”，也不能把固定流程的外部项目 `after=PASS` 与本次模型运行拼成一次成功。

完整原始轨迹仍保留在开发机未跟踪目录 `_runs/external-dotenv-agent-v4`，本目录只发布脱敏后的
摘要、候选补丁和验证结果，避免绝对路径、运行时身份信息和无关缓存进入评审材料。

## 评审含义

这条记录支持的结论是：模型能够读取代码、读取真实违规证据并提交结构化候选；程序能够拒绝
未保留业务行为或不满足规则的候选。它不能证明外部项目的自动修复已经可靠，也不能替代
`20261004-external-dotenv-v4` 中不调用模型的受控检查与复检结果。
