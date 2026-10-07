# candidate-02 POST_RUN_VERIFICATION

这是对保存的正式模型候选 2 的一次独立、无模型事后复检。原始正式运行仍标记 `UNVERIFIED`，本目录不修改或回填原记录。

## 可复检材料

- `project/tool.py`：候选 2 的 UTF-8 LF 源码。
- `project/credproof.toml`：冻结配置。
- `project/tests/test_business.py`：冻结必要测试。
- `public-evidence/report.redacted.json`：结构化脱敏报告。
- `public-evidence/command-output.redacted.txt`：实际命令输出和退出信息。
- `public-evidence/post-run-verification-summary.json`：由上述报告派生的摘要。

命令（在仓库根目录）：

```powershell
.venv\Scripts\python.exe -m credproof_safety check --config docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot/post-run-verification-candidate02-v1/project/credproof.toml --output docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot/post-run-verification-candidate02-v1/report.json
```

实际退出码为 `2`，报告 `FAIL`。pytest 4/4 通过只是测试覆盖不足；正常入口返回常量对象，没有允许文件读取、允许服务回执或认证证据。允许文件+跳转场景提前抛出 `ValueError`，因此没有真正执行跳转请求，不能把它称作跳转负例通过。该结果是 `POST_RUN_VERIFICATION`，不计入原 12 次模型任务。

根目录的 `report.json`、`command-output.txt` 保留在本机作为原始件，未上传；公开件采用结构化路径脱敏，不对嵌入代码做宽泛替换。
