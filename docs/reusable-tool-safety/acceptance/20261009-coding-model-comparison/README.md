# dev33：单次编码模型对照（已结束）

**NOT_READY_FOR_HANDOFF / MODEL_COMPARISON_CLOSED_UNSUCCESSFUL**。

[最终收尾记录](closeout.md)：身份、真实计数、完成/未执行步骤及明确阻断；本轮已停止，没有新增推理或5060交接。

[一页结论与全部证据](public-evidence/README.md)。固定 qwen2.5-coder:32b-instruct-q4_K_M，真实被测源码 `a780b9e6543355c2108c1d41e43a8dccd7c2e0c1`；安装程序构建源 `ad826dae2d43ee0c0ec636f59a48f9325bcd14df`，12份受影响程序文件相同。后续证据提交不代表又一次模型任务。

一次非项目结构化预检通过；唯一正式安装页面任务为1次生成、1份不同/接受候选、1次自动验收UNKNOWN。JSON有效但代码含Markdown围栏，导致SyntaxError、pytest收集/执行0，按既有UNKNOWN分支停止。没有模型修复PASS、成功导出或公开PASS复检。未修改候选、未追加第二任务。

[硬上限登记](registration.json) / [真实计数与结束原因](public-evidence/closure/conclusion.json) / [实际请求](public-evidence/model-trace/model-01-request.json) / [实际响应](public-evidence/model-trace/model-01-response.json) / [候选](public-evidence/candidates/candidate-01.py) / [完整验收](public-evidence/candidates/verification-01.json)。

本轮只新增固定模型身份、manifest挂载及版本记录；同一原始p01、组件API、系统指令、工作包构造、测试与判决保持。官方来源：[固定模型标签](https://ollama.com/library/qwen2.5-coder:32b-instruct-q4_K_M)、[结构化输出接口](https://docs.ollama.com/capabilities/structured-outputs)。

本轮已关闭：暂停自动生成效果优化，等待用户裁定后续资源或产品范围。不自动启动5060。

公开证据提交 `c79dc14b4cacb071274b452b48945675f1823123`；清单提交 `4a6d14eca01dd1db38cb48514d44f4dbab2912bb` 已匿名取回100份正文并逐字节核对。[匿名取件收据](github-publication.json)在取件后追加，未改变被测程序或模型成绩。
