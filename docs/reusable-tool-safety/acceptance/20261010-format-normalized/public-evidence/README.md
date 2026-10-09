# 可直接读取的事后格式归一化证据

入口：[本轮说明](../README.md)；[收尾](../closeout.md)。原正式任务UNKNOWN不变，派生候选FAIL，新增模型调用0，NOT_READY_FOR_HANDOFF。

- [原模型响应](original-model-response.json)、[原UNKNOWN](original-unknown-report.json)、[来源核对](diagnosis.json)。原始与公开派生摘要不混用。
- [精确删除](normalization.json)、[差异](normalization.diff)、[派生正文](normalized-candidate.py)、[静态语法](syntax.json)。只去外层围栏，无语义修复。
- [完整隔离报告](report.json)、[自动生成摘要](summary.json)、[执行收据](execution-receipt.json)、[安装来源](installed-origin.json)、[冻结](freeze.json)、[命令](commands.json)。
- [13项协议JUnit](protocol-junit.xml)、[stdout](protocol-pytest.txt)、[原始/派生摘要映射](derivation.json)、[逐文件清单](manifest.json)。
- [当次项目配置](project/credproof.toml)、[必要测试](project/tests/test_business.py)、[入口](project/tool.py)。配置/测试公开LF字节映射见derivation；这是失败证据副本，不是已导出的PASS bundle。

本目录不包含模型权重、运行环境、真实凭据或账户资料。只有已知宿主前缀/主机名被映射；`/tmp/project`与`/tmp/lab`是受控沙箱路径，保留其语义。完整原始材料留在5090，公开报告的合成凭据已脱敏。
