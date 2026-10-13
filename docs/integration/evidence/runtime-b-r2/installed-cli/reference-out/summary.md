## CredProof 验收：通过

- 配置：`reference/credproof.toml`
- 入口文件：`reference/tool.py`
- 报告摘要：`5c23dc196195ab036e89adc0fd1d3969ed6f3cce9f961cb8a9948abd64215e8e`
- 项目树摘要：`7919e207b8a78cd84b3e535daf9ac337e6ba1c759f5bd17419def5d776ae6d2d`

本配置声明的 14 项条件全部满足。
- 业务测试与声明的入口场景按预期完成。
- 没有观测到凭据出现在返回值、输出、日志或异常中，也没有观测到禁止目录、范围外文件或未授权连接的访问尝试。
- 观测到对允许目录中资料的访问。
- 观测到携带正确凭据访问允许的服务。

本地复现：

```text
credproof-safety check --config reference/credproof.toml
```

结论只覆盖该配置声明的入口、必要测试和访问组件，使用合成凭据与本地模拟服务。
