# 资料助手：共同入口示例

这是一个位于 CredProof 仓库之外的受控小型 Python 工具样例。它保留了一个
正常业务入口和 pytest 测试，同时在初始副本中人工注入了三类问题：读取
`data` 以外的文件、允许 HTTP 重定向到未授权服务、把合成凭据写入日志和返回值。

`tool.py` 的当前文件是“人工注入版本”，不是上游漏洞或 CVE。提交中的
`tests/test_business.py` 是项目原有业务测试示例；CredProof 还会在独立
副本中运行配置入口。测试服务、文件和凭据均由执行器动态生成。

```powershell
python -m credproof_safety check --config examples/material_assistant/credproof.toml `
  --output examples/material_assistant/.credproof/vulnerable.json
```

当前版本预期为 `FAIL`，这是为了证明观察层实际看到了问题。修复副本应保留
业务返回和错误处理，再运行同一命令得到 `PASS`；重新引入任一问题应再次
得到 `FAIL`。这不是跨平台或通用 SSRF 证明，当前观测覆盖 Python audit
`open`/`socket.connect` 以及隔离 loopback 模拟服务。
