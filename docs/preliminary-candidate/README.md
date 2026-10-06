# CredProof 初赛候选材料入口

## 一句话

**让 AI 提出修复，让程序决定是否接受，让开发者能够复查。** CredProof 面向维护授权 Python/AI 工具的开发者和安全人员，把凭据输出、越界读取和未授权连接的受控证据，与候选补丁、业务检查和对应对象的复检材料放在同一条路径中。

## 推荐阅读和展示顺序

1. 先看当前资料助手接入：页面显示当前对象、三类检查和总体 `PASS/FAIL/UNKNOWN`。
2. 再看 [python-dotenv 外部组件记录](../../experiments/reusable-tool-safety/20261004-external-dotenv-observer-v2/summary.json)：117 项业务通过仍能由安全检查判 `FAIL` 的重新引入缺陷。
3. 最后看 [h03 历史反馈过程](evidence-index.md#h03-脱敏前缀不等于移除秘密)：第一候选被真实证据拒绝，第二候选通过。
4. 需要复查时运行 [启动模式](startup-modes.md) 和导出材料自带的复检入口。

正式正文见 [说明书](manuscript.md)，PDF 与可编辑文件见 [PDF](credproof-manuscript-candidate.pdf) 与 [DOCX](credproof-manuscript-candidate.docx)。本版候选包和校验值见 [preliminary.9 交付收据](delivery-receipts/preliminary-9/README.md)。主展示案例是精选演示，不替代完整批次统计；失败和未完成任务仍保存在 [证据索引](evidence-index.md) 与历史目录。

## 当前交付边界

只支持已登记的受控 Python 工具和合成凭据/授权模拟服务；不访问真实账户、不执行任意上传项目、不把本地模型或上游组件能力写成本项目原创。

