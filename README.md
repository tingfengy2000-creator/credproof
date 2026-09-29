# 密证 CredProof

**面向凭据修复的证据化验收系统。** 将“通过”限定到具体副本、范围和条件，检查证据是否仍适用；不把零告警或过期结果当作修复完成。

当前是可运行的**合成机制原型**：真实 worktree/index 读取、受限 Python 副本修复、Gitleaks 扫描、确定性验收和材料复检。没有接入大模型，不依赖 GPU。

## 本轮方案与实测

- [初赛定位、机制与 10—14 天计划](docs/preliminary/00_positioning_and_plan.md)
- [工具能力、研究来源与官方模板](docs/preliminary/01_related_work_and_template.md)
- [最小实验协议](docs/preliminary/02_experiment_protocol.md)
- [实测结果、三分钟讲稿与五个问答](docs/preliminary/03_results_and_demo.md)
- [主机制图](docs/preliminary/diagrams/mechanism.png)
- [逐案例脱敏记录](experiments/results/20260929T014733Z_00c48b93/summary.md)

首轮正常同范围案例中，C 接受正确副本 4/4、不合格候选 0/6；其余 6 个证据异常案例均为 UNKNOWN。全部为开发可见合成案例，不是独立盲测。合理重跑的 B-fresh 能发现旧结果掩盖的行为错误；不能据此宣称超过完整 CI。

## 运行

在仓库根目录使用 Python 和 Git。CLI/回归实测 Windows / Python 3.14.7；机制实验使用 Python 3.12.14，详见记录。Python 代码无额外 pip 依赖，其他环境尚未完成打包验证。

```powershell
python scripts/get_gitleaks.py
python scripts/demo.py
python -m unittest discover -s tests -v
python experiments/pilot.py --gitleaks .tools/gitleaks-8.28.0/gitleaks.exe --output runs/pilot --repeats 3
```

第一条从官方 release 获取固定 Gitleaks 8.28.0 并检查发布方 checksum，之后本地试验不访问真实账户。已有程序可用 `--gitleaks <路径>` 指定。回归测试默认 Windows 路径，其他平台可设 `CREDPROOF_GITLEAKS`；缺检测器/Git 会明确跳过，跳过不算成功，此轮实际无跳过。

演示创建新合成仓库，真实执行：零告警但行为破坏 → 正确修复 → 额外变化使旧证据 UNKNOWN → 新检查发现越界 FAIL。标签不传给判决器。每次输出新的 `runs/demo/<编号>/`；最终故意停在越界副本，便于复检：

```powershell
python -m credproof recheck --bundle "runs/demo/<编号>/bundle"
```

重新读取材料和执行检查，不信保存的 PASS。CLI 返回 0=PASS、1=FAIL、2=UNKNOWN；PowerShell 如需原样传递退出码，再执行 `exit $LASTEXITCODE`。

## 当前边界与既有成果

- 只处理合成标记、单处模块级 Python 字符串赋值、已有 `import os` 的源文件。
- 功能检查只运行明确允许的闭合样例语法，不执行任意待扫描仓库脚本、导入或测试。
- 原工作区/index 只读，只在副本修改；不提供自动应用、历史清理或云撤销。
- 副本 PASS、原工作区是否匹配、index 残留、撤销未知分别呈现。
- 脱敏报告不能独自复现缺失材料；哈希/JSON 不是签名、第三方认证或安全证明。

[V2 方案和界面原型](docs/plan-v2/README.md) 原样保留，原型是**模拟数据**，不能充当本轮结果。有冲突时以本轮方案为准。后续保留 React/TypeScript 和薄 FastAPI，只服务一页验收工作台。

检测复用 Gitleaks，代码与文稿使用 Codex 辅助开发，见 [归属说明](THIRD_PARTY_NOTICES.md)。原材料、私有见证和运行目录被 Git 忽略，不因仓库公开就自动上传。可见性由用户管理，本轮仅本地提交，未推送或改变可见性。最终 DOC/PDF 和干净环境程序包尚未交付。
