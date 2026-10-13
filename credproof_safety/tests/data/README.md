# 测试数据

- `sarif-schema-2.1.0.json`：OASIS SARIF 2.1.0 官方 JSON Schema（errata01）。
  - 来源：`https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json`。
  - 取得时间：2026-10-13。
  - SHA-256：`c3b4bb2d6093897483348925aaa73af03b3e3f4bd4ca38cef26dcb4212a2682e`。
  - 随仓库保存，测试时不联网下载。
  - 使用前提：需要安装 `jsonschema`（`pip install .[test]`）。本地未安装时，Schema 校验测试会显式跳过；设置 `CREDPROOF_REQUIRE_SARIF_SCHEMA=1`（CI 中使用）时，未安装直接判为失败。
- `report-formats/`：报告样例，供 `test_report_formats.py` 使用。
  - **来源**：其中 5 份是 5060 容器原型上运行真实检查器得到的报告，只保留派生格式会用到的字段：
    - b07 漏洞原版 FAIL；
    - b07 参考修复 PASS；
    - b01 日志泄密；
    - b05 读取禁止目录；
    - Docker 默认参数下的 UNKNOWN。
  - **合成样例**：`blocked.json` 和 `not_reached.json` 两份是按 `project._verdict` 的输出结构构造的；`pass_minimal.json` 由 b07 参考修复的 PASS 去掉允许资料访问和服务请求记录得到，对应配置不要求读取文件和认证的 PASS。
  - **刻意埋入的“陷阱”**：每份样例都带有绝对路径、类似用户名的路径和类似凭据的值，用来断言它们不会出现在任何派生格式中。
  - **用途限制**：这些样例只用于测试格式转换，不是隔离验收证据。原型用 `/` 作 rootfs，见契约第 1 节。
