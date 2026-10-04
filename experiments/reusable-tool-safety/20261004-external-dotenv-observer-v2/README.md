# python-dotenv observer-fix v2

这是固定 `python-dotenv` v1.2.2 快照（commit
`36004e0e34be7665ff2b11a8a4005144f76f176d`）的受控外部接入复测。目录读取缺陷是
本项目在 disposable 副本中人工注入的适配问题，不是上游漏洞或 CVE；不调用模型，
也不把本次结果写成 Agent 自动修复成功。

本轮使用新版 pytest 观测器和导入捕获。114 项上游 `test_main.py` 测试加 3 项
CredProof adapter 测试，共 117 项；before 为 116 passed/1 failed，after 为
117 passed，reintroduced 与 unrelated 的 pytest 退出码分别为 0/0，但安全判定按
实际文件和输出证据区分。
