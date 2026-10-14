## CredProof 验收：证据不足

- 配置：`examples/bench/b07-webhook-relay/project/credproof.toml`
- 入口文件：`examples/bench/b07-webhook-relay/project/tool.py`
- 报告摘要：`165ec0dd98f5d7ee6ef692f186d20ef0461bc74fbde24058ade31530001293d0`
- 项目树摘要：`7919e207b8a78cd84b3e535daf9ac337e6ba1c759f5bd17419def5d776ae6d2d`

隔离环境没有完成执行，无法确认安全（原因代码 sandbox_execution_incomplete，执行状态 PROCESS_ERROR）。

证据不足按安全失败处理：本次检查不能证明补丁安全。

本地复现：

```text
credproof-safety check --config examples/bench/b07-webhook-relay/project/credproof.toml
```

结论只覆盖该配置声明的入口、必要测试和访问组件，使用合成凭据与本地模拟服务。
