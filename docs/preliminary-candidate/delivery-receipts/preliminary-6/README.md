# preliminary.6 增强初赛候选版交付收据

本版把三类受控安全检查、项目接入、导出报告复检和通俗讲解整合到同一候选交付中；没有新增模型任务、案例集或安全类别。源码评审包从固定提交 `7f4810c2b928739c01b23f509d4939b96b37939f` 的 Git blob 构建；本收据在包构建后单独提交，不在包内，也没有为了加入自身哈希而重打包。

- 候选版本：`0.2.0-preliminary.6`；安全包版本：`0.3.0-dev.10`
- 包名：`credproof-0.3.0-dev.10-20261005-7f4810c2b928.zip`
- 本地位置：`E:\比赛\密证_CredProof-local-agent\_runs\review-packages\0.3.0-dev.10-rebuild\`
- 大小：14,037,133 字节
- ZIP SHA-256：`3b44c08290d606a5bee00909efa828e5a1867991f4e8dc1f383d62c7343be38c`
- `manifest.json` SHA-256：`73b3e06f6aa7c7dededdcca40a679499bff0059151af2d166afa19b517f6ad4a`
- 清单源文件：3,988；包内不含模型权重、虚拟环境、真实凭据或本机二进制

## 已执行检查

- 核心单元测试：33 项，退出码 0。
- Agent/runtime 测试：98 项，退出码 0。
- 导出消费者回归：固定与无关变更副本新报告为 `PASS`；重新引入目录缺陷的新报告为 `FAIL` 且含 `no_forbidden_file_read`；pytest/JUnit 与报告三者均已核对，脚本退出码 0 表示预期回归已观测。
- 安全演示：`vulnerable=FAIL`、`fixed=PASS`、`reintroduced_file_bypass=FAIL`。
- 外部 python-dotenv 受控记录：`before=FAIL`、`after=PASS`、`reintroduced=FAIL`、`unrelated=PASS`；未调用模型。
- 启动 smoke：新虚拟环境安装轮包后 `python -m credproof_safety --help` 退出 0；view 模式首页、health、bootstrap、project-modes 均返回 200。新环境未安装 pytest，因此不把 help 检查写成完整业务复检。
- 说明书：15 页；PDF 603,423 字节，小于 10 MB；DOCX/PDF 哈希见 `docs/preliminary-candidate/render-validation.json`。

机器可读证据位于 [`experiments/reusable-tool-safety/20261005-enhanced-candidate-v1`](../../../../experiments/reusable-tool-safety/20261005-enhanced-candidate-v1/)。该包保留历史批次和失败记录，不把典型案例拼成总体成功率，也不声称 ChatGPT 已验收或模型实验已重新运行。
