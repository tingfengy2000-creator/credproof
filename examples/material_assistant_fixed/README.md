# 资料助手修复副本

这是 `examples/material_assistant` 的受控修复副本。修复只允许配置目录内
的真实文件，校验主机、端口和路径，并禁止自动跟随重定向；凭据仍只用于
授权模拟服务请求，返回值不再包含凭据。使用同一 `credproof check` 命令可
复验，预期为 `PASS`，业务 pytest 仍应通过。
