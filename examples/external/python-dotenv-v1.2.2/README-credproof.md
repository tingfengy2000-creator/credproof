# python-dotenv v1.2.2 外部接入

- 来源：`https://github.com/theskumar/python-dotenv`
- 固定提交：`36004e0e34be7665ff2b11a8a4005144f76f176d`
- 许可证：BSD-3-Clause，原始 `LICENSE` 随目录保留。
- 保留的上游材料：`src/dotenv`、`tests/test_main.py`、`pyproject.toml` 和原始说明。

CredProof 在仓库旁增加了极薄的 `credproof_entry.py` 适配层，把配置文件读取
入口接入共同检查。该适配层的初始目录检查是**人工注入的受控缺陷**，不是
python-dotenv 的上游漏洞、CVE 或企业部署证据。`credproof_entry_fixed.py`
是保留 dotenv 解析行为的受控修复。两份配置会在同一隔离实验中运行上游
`test_main.py`，分别得到问题版 FAIL 和修复版 PASS；只覆盖目录读取这一类。

```powershell
python -m credproof_safety check --config examples/external/python-dotenv-v1.2.2/credproof.toml
python -m credproof_safety check --config examples/external/python-dotenv-v1.2.2/credproof-fixed.toml
```

这是小型外部接入案例，不能推导 python-dotenv 的通用安全性质，也不替代上游
升级或安全公告。使用了 `pytest` 进行原有测试收集；测试导入同样发生在
CredProof 的 WSL/bubblewrap 副本中。
