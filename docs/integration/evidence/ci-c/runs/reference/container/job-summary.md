# CredProof CI

## CredProof 验收：通过

- 配置：`examples/bench/b07-webhook-relay/project/credproof.toml`
- 入口文件：`examples/bench/b07-webhook-relay/project/tool.py`
- 报告摘要：`75e6d444ef4fae26e2ac2d7e6e4dbe9294a064268710cd07bd2a562d885f79a9`
- 项目树摘要：`7919e207b8a78cd84b3e535daf9ac337e6ba1c759f5bd17419def5d776ae6d2d`

本配置声明的 14 项条件全部满足。
- 业务测试与声明的入口场景按预期完成。
- 没有观测到凭据出现在返回值、输出、日志或异常中，也没有观测到禁止目录、范围外文件或未授权连接的访问尝试。
- 观测到对允许目录中资料的访问。
- 观测到携带正确凭据访问允许的服务。

本地复现：

```text
credproof-safety check --config examples/bench/b07-webhook-relay/project/credproof.toml
```

结论只覆盖该配置声明的入口、必要测试和访问组件，使用合成凭据与本地模拟服务。


## Execution receipts

| Step | Exit | Expected | Match |
|---|---:|---|---|
| container-apparmor-load | 0 | [0] | True |
| build | 0 | [0] | True |
| docker-version | 0 | [0] | True |
| docker-security | 0 | [0] | True |
| container-origin | 0 | [0] | True |
| doctor | 0 | [0] | True |
| check-0 | 0 | [0] | True |
| anchors | 0 | [0] | True |
| default-doctor | 4 | [4] | True |
| default-check | 3 | [3] | True |
| build-receipt | 0 | [0] | True |
| image-create | 0 | [0] | True |
| image-export | 0 | [0] | True |
| image-remove | 0 | [0] | True |
| image-scan | 0 | [0] | True |
| output-ownership | 0 | [0] | True |
| formats-scan | 0 | [0] | True |
| apparmor-denials | 1 | [0, 1] | True |
