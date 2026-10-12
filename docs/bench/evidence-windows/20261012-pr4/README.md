# PR #4 Windows 复验与 bench-v1 运行交付

本入口对应 [PR #4](https://github.com/tingfengy2000-creator/credproof/pull/4) 与 [issue #5](https://github.com/tingfengy2000-creator/credproof/issues/5)。本批已结束；可供外部审查，未合并 PR、未改变 main、未开始新的交接或模型实验。

## 版本与阅读顺序

- PR 原始固定源码：`8e9dd7bdd8395fabfa488c37a985b50b308864d2`。
- Windows 目标/历史复验源码：`05583667605118358b4f9b56fb0dd4be2b1abcc7`；详情见 [provenance.json](provenance.json)。执行检查的 `runner.py/project.py/config.py` 与 PR 原始版本字节相同。
- 正式模型运行和清洁安装源码：**`ad3771cd7182863310f04e7325276cf2cd405017`**，包版本 **0.3.0.dev37**。
- 后加的汇总脚本、说明与收据不是新的推理；程序运行与材料提交分开记录。
- 先读 [review.md](review.md)，再读 [逐提案/调用核账](accounting.json)、[整合只读数据](bench-results-no-static.json)、[实际运行完成记录](model-run/completion.json)。
- [全部新生成源码、请求/响应、验收、裁判](../../../../experiments/bench-v1/20261012-5090-bench-v1/)；每份补丁目录有 `request.json/response.json/extraction.json/patch.py/check.json/check.report.json`。

## 真实结果：三组分开

| 批次 | 实际执行 | 结果 |
|---|---|---|
| 8 个冻结目标 | 问题版、参考修复、无关修改，共 24 次隔离检查 | 8/8 VALID；问题版全部 FAIL；修复与无关修改全部 PASS；5 个问题版业务测试通过 |
| 历史 21 份补丁 | 21 次检查；另有 5 个独立控制 | 20 FAIL、1 UNKNOWN、0 PASS；业务通过 2；控制 FAIL/PASS/PASS/FAIL/PASS |
| 本次生成 | 8 目标 × 2 模型 × 3 种子 = 48 个初始采样槽；仅 3 个不通过槽执行一次反馈 | 51 份提案、24 份不同 LF 源码；45 PASS、6 FAIL、0 UNKNOWN；无提取失败、无重试 |

Qwen2.5：24 份提案 PASS。Qwen3：21 PASS、6 FAIL；6 个 FAIL 是 b07 的三个种子及其反馈轮。**提案、不同源码、采样槽和独立目标是不同分母。** 历史失败没有拼入新模型成绩。6 个 FAIL 提案对应 b07 同一种缺陷，不是 6 个独立漏洞。

两位裁判各检查 51 份新补丁 + 16 个固定锚点，共 **134 次调用**。Qwen2.5 的 ACCEPT/REJECT/INVALID 为 46/14/7，Qwen3 为 65/1/1。完整原文均保留，不追加格式纠正。仅看新补丁，两位裁判都接受 6/6 有实际越界回执的失败补丁。现有业务 pytest 也接受这 6 份；这比较的是**当前业务测试**，加入相同安全检查的规范 CI 可以复用本项目机制。

关键反例：[b07 Qwen3 s1 r0](../../../../experiments/bench-v1/20261012-5090-bench-v1/patches/b07-webhook-relay__qwen3-coder-30b__s1__r0/)。源码有 `_NoRedirect`，实际 `run` 却调用 `urlopen(relay)`，没有使用禁跳转的 opener。2 项业务测试通过，禁止模拟服务实际收到一次请求且 `credential_ok=true`，程序判 FAIL。反馈轮仍 FAIL，没有筛掉或人工修成 PASS。

`bench-results-no-static.json` 由冻结 `build_results.py` 生成，含新提案/历史/锚点三个独立分区；本轮未重新执行静态扫描，`static=null`，不得解读为扫描无告警。冻结汇总器的 `rejected_good` 计数包含 INVALID：Qwen2.5 对合格新提案的 15 个未放行中，9 个 REJECT、6 个 INVALID；不能都称为明确误判。

## 命令与原始证据

均在本台 RTX 5090 / Windows 11 / Python 3.12.14 完成，实际候选在既有 WSL Ubuntu-24.04/bubblewrap 中执行。WSL Python 3.12.3，Ollama 0.34.4。不是第二台机器验证。

```powershell
# $py 指本机可信的 Python 3.12 环境；TEMP/TMP/CREDPROOF_RUNTIME_TEMP 指可挂载的临时目录。
& $py -I scripts/bench/review_capture.py validate_targets --output <new-validation>
& $py -I scripts/bench/review_capture.py recheck_history --output <new-history>
# 以下启动器只桥接传输；内部执行未修改的 generate.py 与 judge.py。
& $py -I scripts/bench/run_isolated.py --run <new-run> --evidence <new-evidence> --private-work <new-private-work>
```

这些是复现说明，**不要在已有运行目录重启采样**；每批要求新目录。无需推理即可读取已有材料。

- [8 目标逐例](target-validation/records.json)、[24 份完整报告和命令/stdout/stderr](target-validation-execution/command.json)。
- [21 历史补丁与控制](history/records.json)、[完整报告/真实命令](history-execution/command.json)；原始报告也保存在 `history/*.report.json`。
- [正式登记及源码/提示词摘要](model-run/registration.json)、[生成命令](model-run/generation-command.json)、[裁判命令](model-run/judge-command.json)、[生成输出](model-run/generation-stdout.txt)、[裁判输出](model-run/judge-stdout.txt)。
- [完整实际传输](model-run/transport/)：请求保存实际 UTF-8 body、字节数和 SHA-256；响应保存原 Ollama JSON、usage 和 `/api/ps`。这补足冻结裁判脚本仅保存文本的限制，没有修改其结果。
- [隔离探针](model-run/boundary-readiness.json)、[挂载白名单](model-run/boundary/boundary-plan.json)、[Ollama/CUDA 原始日志的脱敏副本](model-run/boundary/ollama-stderr.txt)。模型和控制器同 net/mnt/pid namespace，只有 lo；三次出网探针拒绝，宿主标记/逃逸链接不可见。候选检查与模型边界分别记录。
- [真实模型 digest/设备/usage 核账](accounting.json)：两模型 Q4_K_M、上下文 16384、实际 CUDA0，`size_vram==size`；本次作品调用无付费 API。冻结 `common.model_info` 的 `digest=15` 实为 GGUF `file_type`，**不是模型 digest**；以登记的 manifest SHA 和实际 `/api/ps.digest` 为准，原记录不改写。

## 接口修正与无模型验证

修正已选择结果文件在首次请求缺失时误命中空缓存导致 500；现在返回 409，并拒绝错误的 patch 列表结构。只读入口只新增两个 GET 白名单及操作者 CLI 文件参数；浏览器不能提供路径，写入仍 405，Host/Origin/查询限制保留。

- [定向软件 pytest/JUnit](protocol-after-elevated.xml)：56 passed，pytest 8.4.2，退出 0。
- [原 PR 测试](protocol-pr4-command.json)：51 passed、2 failed，原因是 Windows 测试用 HOME/WindowsPath 模拟 Linux；修复测试模拟方法，没有改变生产路径逻辑。
- [传输协议](transport-command.json)：4 passed，无模型/候选执行。
- [清洁安装只读真实 HTTP](installed-readonly.json)：6 passed；WSL探针、模型、执行、审批、导出全部 0。
- [wheel/解释器/site-packages 来源与摘要](install-provenance.json)。本轮 wheel 不作为大文件放入 Git；可从源码构建。
- 首次误写测试文件名的退出 4、受本机执行沙箱影响的 WinError 5 均保存在原记录；不计入模型结果，不覆盖。精确命令及退出码见各 `*-command.json`。

查看最新数据：安装当前 wheel 后，使用 `docs/handoff/frontend-5060/view-readonly.py --bench-results docs/bench/evidence-windows/20261012-pr4/bench-results-no-static.json`。入口明确标注历史材料，不执行项目代码或新的模型推理。

## 适用边界

这是开发可见的合成工程基准，8 个目标，不是独立盲测或企业部署；程序观察到的具体违规作为本次比较依据，不宣称检查器绝对准确。历史人机协作范围未被本批更改。原先 `_digest_tree` 的跨系统旧对象排序修复在独立 PR #1 评审分支；本次没有宣称所有旧 bundle 已跨系统兼容。模型、安全动态执行仍归 5090；5060 可读取这些文件做前端/汇总工作。

发布字节由 `.gitattributes` 对本批实验和证据使用 `-text` 保留。[公开派生映射](redaction.json)说明必要脱敏；原件在本地保留。不存在模型权重、真实凭据、rootfs 或虚拟环境。最终交付提交由 Git 固定；文件清单不计算自身。
