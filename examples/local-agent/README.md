# 可移动复检材料

所有凭据为隔离执行时生成的合成值；来源是一次新8例真实实验，历史报告和失败未改写。每个目录自带最小标准库复检程序，依赖已准备的WSL隔离设施，**不依赖原工作区、Qwen或云端模型**。

| 目录 | 来源 | 实际新判决 | 历史适用性 |
|---|---|---|---|
| accepted | h03 C 的第二候选 | PASS | true |
| rejected | h01 A 的未合格修复 | FAIL：logging泄露 | true |
| unchanged | h07 C 正常原件 | PASS | true |
| incomplete | h05 C 未真实调用工具的任务 | 原件 PASS，但历史任务仍 INCOMPLETE | true |
| stale-pass | accepted导出后增加无害注释 | PASS | false |
| missing-current | accepted导出后将current.py保留为current-withheld.py | UNKNOWN | false |

后两项是明确标注的材料漂移/遗漏故障注入，**不计入模型案例数，不冒充模型失败或成功**。源报告保留；`fresh-recheck.json` 是初次实际复检记录，不作为再次复检的输入真值。

复制任一完整目录到新位置，进入该目录：

```text
python -m agent_pilot.bundle recheck --bundle . --output recheck-new.json
```

输出文件必须尚不存在。PASS/FAIL/UNKNOWN退出码分别0/1/2。可信工具源码/必要配置漂移会停止执行；普通候选代码变化先使旧报告失效，再在相同固定检查下重新判断当前对象。不要执行不受信任第三方打包者提供的Python复检程序；源码与操作者受信任，哈希不是签名或第三方证明。
