# CredProof 0.1.0-agent-review.2：可供外部审查

本地研发修订包，不是比赛终版、发布版或外部验收通过。保留 `0.1.0-agent-review.1` 原包、旧提交、失败及逐案例结果；没有推送、发布或更改可见性。本轮未换模型、框架、隔离环境，未新增业务功能、案例集或改版工作台。

## 先读事实，再读修订

1. [原新8例逐案例核清](evidence-audit.md)：A 唯一没修好的是 **h01**，不是 h03；A 在 h03 第一份候选即通过。历史 A/B/C 任务完成仍为 7/8、4/8、6/8，不与本轮复测拼成绩。原14例此后都是已知回归案例。
2. [h03 完整失败—反馈—修正](evidence-audit.md#h03真实迭代成立根因解释不完全正确)：首候选只插入 `[REDACTED]` 前缀，真实值仍在日志；失败反馈真实进入下一请求，第二候选换成固定错误详情后通过。模型把原因解释为字面单词 `credential`，这个解释仍然错误。两份补丁、全部请求/响应、验证记录都在相对链接中。D 的 h01/h03 六次无反馈尝试均失败；仅最大输出预算相同，实际调用与输入 tokens 不匹配。
3. [h05/h06 协议定位](protocol-diagnosis.md)：缺少服务端 coder 模板的外层起始标记，响应退回普通文本；没有原生调用。保留官方版本源码链接、原始响应哈希及解析回归。
4. [有限修改协议](protocol.md)、[模型客户端](../../../agent_pilot/model_client.py)、[C启用位置](../../../agent_pilot/reliability.py)：最多一次固定格式纠正，复用同一任务历史与剩余预算。只执行原生 `tool_calls`；拒绝未知工具、非法参数和路径。必要条件已完成就结束；文本结束不能代替完成。
5. [本轮两例新推理](retest-results.md)：h05/h06 分别6/8次调用，最终诊断正常、13项验收PASS、原文件不变。**首响应已原生调用，两例纠正分支均未触发。** 不能据此证明纠正提示挽救了真实失败。h06 仍提出一次无证据支持的删日志提案，被程序拒绝；实际零修改不等于模型没有错误行动建议。
6. [旧冻结偏差](freeze-deviation.md)与[固定旧版补跑结果](freeze-rerun-results.md)：旧退出1不变。缺少逐文件终点摘要，另从原9a3提交在干净目录补跑受影响原6例，退出0且全部36个导出文件前后不变。该次 A/B/C 任务完成为6/6、5/6、5/6；C p06选中对象PASS但无合法完成调用，仍INCOMPLETE。按新记录单列，不能追认旧轮冻结通过，也不混入采用新纠正客户端的h05/h06成绩。

### 源码、测试和材料

| 内容 | 可直接读取的依据 |
|---|---|
| 原h05/h06伪调用不执行；最多一次纠正、完整历史、预算与拒绝边界 | [15项协议REPLAY测试](../../../agent_pilot/test_tool_protocol.py)、[原24项客户端测试](../../../agent_pilot/test_model_client.py)、[39项真实命令输出](../../../experiments/local-agent-pilot/tool-call-revision/validation-01/client-protocol-stderr.txt) |
| 原8例的正常结束、诊断、对象验收、完整任务各自计数 | [30行分层机器表](../../../experiments/local-agent-pilot/tool-call-revision/prior-case-audit.json) |
| 两个已知案例的全新模型请求、响应、候选提案与工具回执 | [新轮原始目录](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/)、[逐例审计](../../../experiments/local-agent-pilot/tool-call-revision/retest-results.json) |
| 原件修改权限、固定裁判、隔离 | [reliability](../../../agent_pilot/reliability.py)、[judge](../../../agent_pilot/judge.py)、[isolation](../../../agent_pilot/isolation.py) |
| 受限真实单页与API | [web.py](../../../agent_pilot/web.py)、[ui](../../../agent_pilot/ui/)；本轮只把回放/验收时间文案改为“记录时间”，不把文件时间当原执行时间 |
| 可迁移材料与重新执行 | [六套合成材料及说明](../../../examples/local-agent/README.md)、[导出/复检程序](../../../agent_pilot/bundle.py) |
| 原8例全部记录，含h03两份补丁和失败反馈 | [原轮目录](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/) |
| 固定依赖与来源 | [依赖锁](../../../agent_pilot/requirements-lock.txt)、[框架边界](../framework.md)、[隔离准备](../isolation.md)、[开源与AI参与](../reliability/source-attribution.md) |

## 运行条件与命令

**阅读材料、HTTP协议回放和单元测试不需要GPU、模型权重或模型服务。** 协议测试仍需锁定的Qwen-Agent Python依赖，用内存HTTP控制输入，绝不是新推理。**确定性复检不需要模型/GPU，但需要已有可信WSL隔离环境及其rootfs/seccomp配置。** 单页启动只需普通Python；点击“开始分析与修复”才需本地Ollama、模型与隔离设施。新推理实测显存采样峰值约18.72GiB，仅作本机测量参考。

Windows在解压根目录：

```powershell
python -m agent_pilot.web --port 8767
```

打开 `http://127.0.0.1:8767/`。界面标为“模型怀疑”的文字分析可能有误；程序确认、授权及验收是独立证据。历史回放必须保留REPLAY标识；没有实际运行A+Agent组合，不声称组合8/8。原工作区和原index默认只读，不开放任意项目上传、Shell或真实凭据服务。

已有WSL环境中，`<解压目录的WSL路径>`需替换为实际目录；运行设施路径来自本机已验收安装，不表示跨机器开箱即用：

```text
wsl -d Ubuntu-24.04 --cd <解压目录的WSL路径> --exec /home/tingfeng/credproof-agent-runtime/venv/bin/python -B -m unittest agent_pilot.test_model_client agent_pilot.test_tool_protocol -v
wsl -d Ubuntu-24.04 --cd <解压目录的WSL路径> --exec /home/tingfeng/credproof-agent-runtime/venv/bin/python -B -m unittest discover -s agent_pilot/tests -v
```

只用材料进行真正复检，输出必须是新文件：

```powershell
New-Item -ItemType Directory -Path runs -ErrorAction SilentlyContinue
python -S -m agent_pilot.bundle recheck --bundle examples/local-agent/accepted --output runs/recheck-accepted.json
python -S -m agent_pilot.bundle recheck --bundle examples/local-agent/rejected --output runs/recheck-rejected.json
python -S -m agent_pilot.bundle recheck --bundle examples/local-agent/stale-pass --output runs/recheck-stale.json
python -S -m agent_pilot.bundle recheck --bundle examples/local-agent/missing-current --output runs/recheck-missing.json
```

预期退出码依次0、1、0、2；对应PASS、FAIL、旧报告不适用但新检查PASS、UNKNOWN。原报告字段不决定新结论。信任操作方制定的需求、裁判与隔离设施；普通哈希不是第三方认证或防伪证明。

GPU新推理复现命令见各轮 `*-launch.json`、`supervisor-result.json`；不要把HTTP回放或旧轨迹展示当成新推理。不在本说明中要求再次跑14例或下载模型。本次作品运行未调用付费API，不包含硬件、电力和开发订阅零成本的承诺。

## 尚未解决与外审边界

真实复测没有再现原始文本调用失败，所以一次纠正分支目前只有协议REPLAY控制证据，缺少“真实失败后由纠正救回”的观测。相同首请求的这两次不同输出不构成稳定性保证。正常任务仍会出现无依据提案、非法对象ID；程序拒绝是执行侧保护，不是模型诊断优势。h03根因解释不准确依然保留。不存在超出受控明文通道、固定样例与需求的普遍安全结论。

[赛事要求映射](../reliability/competition-boundary.md)和匿名、开源归属要求继续适用。AI实质参与方案、代码、测试及文稿生成已披露；允许范围仍待参赛者向教师/组委会确认，不代签原创声明，不标记参赛资格已通过。当前状态仅为**可供外部审查**。
