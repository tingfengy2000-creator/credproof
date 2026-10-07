# 2026-10-07 p01 顺序与 GPU 证据

本目录公开的是本次真实 `assistant-original/p01` 运行的脱敏记录。模型收到的首个请求已经包含当前任务的 `tool.py`、`tests/test_business.py` 索引、规则摘要和初始失败证据；参考修复、fixed 副本和完整仓库没有放入模型边界。

`execution-result.json` 是实际模型控制器结果；`model-work/model-trace/model-01-request.json` 是发往 Ollama 的第一份请求；`candidates/` 与 `verifications/` 保留两份候选及两次可信验收。第一候选因为日志仍含凭据而 FAIL，第二候选通过全部必要检查。`bundle/` 和上层 `new-directory-recheck.json` 对应同一第二候选。

本次运行的 Ollama 日志显示 `CUDA0` 为 RTX 5090，31.8 GiB VRAM；旧版运行的 CPU/0 VRAM 记录仍保留在上一版材料中。本目录中两个以 `gpu-probe` 命名的前置目录是诊断尝试：其一被 bubblewrap 挂载错误阻断，其二因未允许 WSL 驱动挂载而在边界探针处阻断。`gpu-probe-20261007-c` 因 boundary-only 环境变量未透传而实际执行了正式 p01，已在 summary 中明确重分类，不能当作短探针。

所有凭据均为运行时合成值；公开内容只保留 `[SYNTHETIC_CREDENTIAL]` 或脱敏标记。
