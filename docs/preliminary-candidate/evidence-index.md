# 案例证据索引

主展示顺序是当前资料助手检查 → python-dotenv 外部组件与持续复检 → 历史 h03。精选案例不替代完整批次。

## 资料助手与导出复检

项目接入记录见 `experiments/reusable-tool-safety/20261005-enhanced-candidate-v2/project-entry-check-preliminary8.json`。导出消费者逐副本记录见 `experiments/reusable-tool-safety/20261005-enhanced-candidate-v2/exported-regression-v6/summary.json`：固定副本 PASS、重新引入缺陷 FAIL、无关变化 PASS；均不调用模型。

## python-dotenv 外部组件

来源、提交和许可证见 `experiments/reusable-tool-safety/20261004-external-dotenv-observer-v2/summary.json`。上游 114 项加适配 3 项，共 117 项。初始注入版 116 pass/1 fail；修复版 117 pass、安全 PASS；重新引入缺陷版 117 pass、pytest 退出 0，但安全 FAIL。它是人工注入，不是上游漏洞或 CVE。

## h01

见 `experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/C-agent/`。固定启发式遗漏了参数进入日志的有限结构，候选保留认证实参并改为脱敏日志。

## h03

首候选、二候选和验证见 `experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/`。首候选仍保留真实值，程序 FAIL；失败反馈进入下一次请求，二候选通过。

## h07 与完整口径

见 `.../comparison/h07/C-agent/`。无当前泄露证据时保持原代码。完整八例 A/B/C 问题修复 3/4、1/4、4/4，完整任务 7/8、4/8、6/8；失败和未完成保留。
