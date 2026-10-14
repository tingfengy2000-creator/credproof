# R4 B：python-dotenv 工作台接入记录

程序固定于 `5211f98f96cd11913c4f6c1e04bbde3f726959a1`（R4 A 合并后）。模型调用 **0**；没有修改检查器、上游源码或必要业务测试。输入为仓库已登记的 `examples/external/python-dotenv-v1.2.2`。

来源固定为上游 `v1.2.2` / `36004e0e34be7665ff2b11a8a4005144f76f176d`，BSD-3-Clause。问题在**本项目人工注入的薄目录读取适配层**，不是上游漏洞。已有的人工修复控制不是模型候选。

Windows Edge 实际流程：上传文件夹 → 配置向导核对并保存 → 冻结 → v000 检查 → 手工提交已有修复 → v001 检查 → v002 重新引入边界缺陷 → v003 加入无关注释 → 导出诊断包 → 新目录复检。全程 `--demo --mode recheck`，动态执行在既有 WSL/bubblewrap 内，原项目不写回，人工状态 PENDING / NOT_APPLIED。

| 版本/用途 | 必要 pytest | 程序结论 | 依据 |
|---|---|---|---|
| v000 初始注入 | 116 passed / 1 failed | FAIL | [报告](before-review.json)、[截图](before.png) |
| v001 人工修复 | 117 passed | PASS | [报告](after-review.json)、[截图](after.png) |
| v002 再引入目录缺陷 | 117 passed | FAIL | [报告](reintroduced_defect-review.json)、[截图](reintroduced_defect.png) |
| v003 无关注释（修复版） | 117 passed | PASS | [报告](unrelated_change-review.json)、[截图](unrelated_change.png) |
| v003 导出后新目录复检 | 117 passed | PASS | [重新执行完整报告](recheck.json)、[截图](recheck.png) |

117 = **114 项上游 + 3 项适配测试**。初始注入版失败项为缺失文件错误行为，不以该版宣称“全部业务通过仍有安全问题”。这种情况对应 **v002**：保留 `resolve(strict=True)` 与实际 dotenv 解析，仅关闭目录归属判断，正常业务 117 项通过，但实际禁止目录访问与入口负例仍令安全检查 FAIL。

四版本属于同一审阅对象；导出的是最终 **v003**，不是借 v001 的报告解释 v003。`onboarding-dotenv.json` 保存每版代码/项目树摘要以及导出对象。页面接入是人工选择规则，不宣称任意项目自动适配。

## 实际入口与命令（路径脱敏）

```powershell
$env:CREDPROOF_RUNTIME_ROOT='[OPERATOR_APPROVED_WSL_RUNTIME]'
[TEST_PYTHON] -m agent_pilot.launch --workspace [DISPOSABLE_WORKSPACE] --demo --mode recheck --port 0
# 实际地址 http://127.0.0.1:62331
node check-dotenv-r4.mjs
# 原驱动退出 1：已完成 v000 FAIL / v001 PASS，随后停在隐藏的代码编辑器。
node resume-dotenv-r4.mjs
# 同一对象 v001 续行；未重跑前两次检查。退出 0：v002 FAIL / v003 PASS / 导出复检 PASS。
```

驱动使用已安装 Edge 与 Playwright 1.56.1，无下载浏览器。原 [驱动失败摘要](initial-driver-summary.json) 完整保留；[续行摘要](resume-driver-summary.json) 独立保存。错误是录制脚本未切回编辑页签，不是候选运行或验收失败；没有借重跑改写结果。分钟数没有单独测量，所以全部为 `null`。

向导把修改范围收窄为唯一入口 `credproof_entry.py`，必要测试仍是两个原路径，上游 `src` 与规则冻结。该接入只覆盖目录读取，不以未启用网络条件声称网络风险修复。

公开报告使用精确已知路径映射，保留代码、状态、计数和失败原因；[原始与派生摘要](publication.json)。扫描公开记录的敏感命中为 0。原始响应、上传副本和导出 ZIP 保留在本台运行目录；本 PR 不上传环境、真实凭据或身份信息。
