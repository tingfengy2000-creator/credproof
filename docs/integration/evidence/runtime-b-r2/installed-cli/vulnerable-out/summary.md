## CredProof 验收：不通过

- 配置：`vulnerable/credproof.toml`
- 入口文件：`vulnerable/tool.py`
- 报告摘要：`f0a57f415c14dcec6392edb6d34b9ca4b8ef8cf29df1e76ca39b16002c92113e`
- 项目树摘要：`fcd19cf8321628d0618b2a699b2bc5be85d45a0b45a475d62091c128fc2a98d2`

| 未满足的条件 | 运行中观测到的事实 |
| --- | --- |
| 每个声明的场景得到预期结果 | 场景结果不符：“allowed_service_redirect_refused”预期抛出 HTTPError，实际正常返回。 |
| 禁止的服务没有收到请求 | 禁止的服务收到 1 次请求，其中 1 次携带了认证凭据。 |
| 没有未授权的连接 | 观测到向允许服务以外地址的连接尝试 1 次。 |

本地复现：

```text
credproof-safety check --config vulnerable/credproof.toml
```

结论只覆盖该配置声明的入口、必要测试和访问组件，使用合成凭据与本地模拟服务。
