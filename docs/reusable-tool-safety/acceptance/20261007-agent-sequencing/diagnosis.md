# 诊断与本轮结论

## 原运行的实际原因

旧页面批次的模型服务日志显示 `library=cpu` 和 `total_vram=0 B`，所以 120 秒超时不能归因于输入预算耗尽，也不能说模型使用了 5090。另一个事实是第4次请求在输入预算检查通过后等待 120 秒超时，`server_cancel_confirmed=false`；它是客户端停止状态，不是服务端已确认停止。

本轮在同一隔离边界补入只读 WSL 驱动挂载和 CUDA runtime 库路径，并显式选择 `cuda_v12`。正式 p01 日志显示 `CUDA0 / NVIDIA GeForce RTX 5090 / 31.8 GiB`，因此本轮实际推理已使用 GPU。该日志只证明本台5090的本次运行，不推断其他机器速度或可用性。

## 顺序修正

第一个请求现在携带由任务副本生成的有限文件索引、入口、测试和规则上下文；宿主端按请求序号保留同一响应中的请求顺序，并在执行器侧实施阶段门槛。没有证据不能读取；没有读取声明源码不能提交；没有接受候选不能验收。`verify_patch` 在空候选时返回 `NO_ACCEPTED_CANDIDATE`，不调用 `check_project`。

## 一次正式效果运行

`assistant-original/p01` 实际 6 次模型请求、6 份 usage、7 次工具请求，接受 candidate-01 和 candidate-02，分别验收 FAIL 和 PASS。candidate-01 的失败原因是 `no_credential_output`；candidate-02 通过安全与业务检查。没有把原件 FAIL 当作补丁失败，也没有用人工补丁代替模型候选。candidate-02 导出为当前 project-bundle，并在新目录无模型复检 PASS。

该结果只支持一个固定合成任务的受限证据。旧批次、p02–p06、历史回放和两次阻断诊断均未并入本次成功统计。
