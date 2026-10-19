# 第三方组件说明

本作品由 DUIDUI队 开发。下列第三方组件归各自权利人所有，均按其许可使用；作品自有代码中的检测思路、14 项必要条件、证据绑定、三状态审阅、导出复检、工作台与评测方法由本队实现。

| 组件 | 用途 | 许可 | 是否随包分发 |
|---|---|---|---|
| Python 3.12.10 Windows 嵌入式发行版 | Windows 查看模式的随包运行时 | PSF License（原许可文件保留在 `runtime/python/`） | 是 |
| bubblewrap | 隔离执行的命名空间沙箱 | LGPL-2.0-or-later | 否，由运行时准备脚本从 Ubuntu 官方源按固定哈希下载 |
| pytest、iniconfig、packaging、pluggy、requests 等 | 在隔离环境中运行被测项目的业务测试 | MIT / Apache-2.0 等（见各包元数据） | 否，按 `credproof_safety/requirements-lock.txt` 的哈希安装 |
| Qwen-Agent 0.0.34 及其依赖 | 本地模型 Agent 与工具调用 | Apache-2.0 等 | 否，按 `agent_pilot/requirements-lock.txt` 安装 |
| Ollama | 本地模型推理服务 | MIT | 否，用户自行从官方发布页安装 |
| Qwen3-Coder 30B、Qwen2.5-Coder 32B Instruct | 本地候选修复模型 | 各模型发布页所列许可 | 否，权重不随包分发 |
| python-dotenv v1.2.2 | 外部开源组件接入示例（`examples/external/`），其中的目录越界缺陷为人工注入，不是上游漏洞 | BSD-3-Clause（原许可保留在示例目录） | 是（源码副本） |
| Gitleaks、Bandit、Semgrep 社区规则 | 对照评测中的静态方法，以及早期验收器原型 | MIT / Apache-2.0 / LGPL-2.1 等 | 否 |
| Docker 默认 seccomp 配置 | 容器加固配置的来源基线（`deploy/docker/`） | Apache-2.0（`LICENSE.moby-profiles` 保留） | 是（配置文件） |

所有实验均使用每次随机生成的合成凭据和隔离环境内的本地模拟服务，不涉及真实账户或外部系统。
