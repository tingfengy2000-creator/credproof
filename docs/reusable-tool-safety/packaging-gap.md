# 清洁安装发现并修复的打包缺口

旧 dev13 wheel 在仓库外启动单页时缺少 `agent_pilot/ui/index.html`、`app.js` 和 `styles.css`，页面服务报错。问题由清洁安装发现，未被 HTTP 假成功掩盖。

本轮在 `pyproject.toml` 增加 `[tool.setuptools.package-data]`，显式携带 `agent_pilot/ui/*` 及审查过的合成 fixture；不包含模型权重或本机运行时。dev14 wheel 清洁安装后，单页在 `127.0.0.1:18773` 完成真实查看范围、无模型检查和导出操作。
