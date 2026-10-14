## CredProof 验收：证据不足

- 配置：`examples/bench/b07-webhook-relay/project/credproof.toml`
- 入口文件：`examples/bench/b07-webhook-relay/project/tool.py`
- 报告摘要：`c03bd215ed75447393a8fdf120084a412817ce08552fcf2efce3d7a26a8e2d53`
- 项目树摘要：`fcd19cf8321628d0618b2a699b2bc5be85d45a0b45a475d62091c128fc2a98d2`

隔离环境没有完成执行，无法确认安全（原因代码 sandbox_execution_incomplete，执行状态 PROCESS_ERROR）。

证据不足按安全失败处理：本次检查不能证明补丁安全。

本地复现：

```text
credproof-safety check --config examples/bench/b07-webhook-relay/project/credproof.toml
```

结论只覆盖该配置声明的入口、必要测试和访问组件，使用合成凭据与本地模拟服务。
