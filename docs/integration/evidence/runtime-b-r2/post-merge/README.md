# A+B 最终合并后的复验

项目主线 `feat/frontend-human-review-5060` 最终合并提交：
`a5b51e303315dd2dd3f4671d7a771fb9afab0310`。

- PR #11 merged=true，合并 SHA `454f1ef00920a05821c4fac9ab4bdc3614691b44`。
- PR #12 merged=true，合并 SHA 为上述最终提交。
- `main` 前后均为 `2d2d81ee3fe9e1869bfca0b160410deaf83c4bca`。

**在最终合并提交上实际重新运行**，不拿试合并计数代替：

| 范围 | 结果 | 原始事件的脱敏派生件 |
| --- | --- | --- |
| Windows Python 3.12.14 / pytest 8.4.2，agent_pilot/tests + credproof_safety/tests；强制 SARIF Schema | 251 passed、2 Linux 专属 skip、exit 0；1 个 SDK 导入弃用 warning，无模型调用 | [windows.xml](windows.xml) |
| WSL Python 3.12.3，Linux runtime/native/runtime-config 定向检查 | 40 passed、无 skip、exit 0 | [wsl.xml](wsl.xml) |
| Linux 干净检出 | status / diff 为空 | [clean-linux.json](clean-linux.json) |
| Windows 独立工作区 | status 为空；混合行尾原日志保持 -text | [机器收据](receipt.json) |
| JS 语法及 verdict 软件回归 | 两项 exit 0 | [机器收据](receipt.json) |

最终程序、测试、Docker/运行脚本与试合并被测版本 `4eb8d5e49cfdbe07e2fa6ae49ed29b53f4c92fed` 的相关目录逐字节相同。因此 [干净 wheel 的 doctor、参数错误、b07 FAIL/PASS 及真实派生格式](../installed-cli/receipt.json)证据可按此范围沿用；没有伪造另一轮动态检查。

五项修正及来源见 [R2 入口](../README.md)。C、模型、正式固定镜像容器验收、AppArmor 执行验证和实际镜像扫描均**未启动**；容器部分仍为 CANDIDATE。本目录只追加合并后收据，不改原失败或历史实验。
