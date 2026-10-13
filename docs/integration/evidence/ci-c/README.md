# C：GitHub 托管 runner 实测入口

起点：a5b51e303315dd2dd3f4671d7a771fb9afab0310。模型调用为 0。

当前状态：实现待托管运行。容器仍为 CANDIDATE；不以单元测试或预研替代正式验收。

实现：`scripts/ci/run.py`、`.github/workflows/credproof.yml`。
输出包含命令/退出码、doctor、逐目标 JSON/SARIF/JUnit/摘要、16 锚点、
默认容器阻断控制、AppArmor 状态/拒绝日志、构建收据和镜像扫描。

后续在本目录追加真实运行索引与脱敏原始证据，不改写旧 B 失败记录。
两条演示 PR 独立、不合并；不会触碰 main 或冻结研究统计。
