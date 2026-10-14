# 产品工作台 P1 验收记录

范围见 [../PRODUCT-API.md](../PRODUCT-API.md)。本目录的截图来自一次真实运行：服务在 `local/credproof-b` 候选镜像（Ubuntu 24.04、非 root、cap-drop ALL、只读根、seccomp 与 `systempaths=unconfined`）中以 `--demo --mode recheck` 启动，检查在镜像内的 bubblewrap 隔离环境执行，没有调用模型。

浏览器脚本 [check-product.mjs](check-product.mjs) 走完整条用户流程，全部通过：

| 步骤 | 实际结果 |
|---|---|
| 示例“资料助手（问题版本）”接入，沿用自带配置，冻结并开始 | 配置有效，审阅 v000 |
| 隔离检查 v000 | FAIL；未满足条件与已记录的原版报告相同（7 项） |
| 粘贴开发者修订（案例 v001 源码）提交为新版本，再检查 | PASS |
| 以“功能测试”身份采纳，下载 SARIF，导出已采纳修复 | SARIF 2.1.0；导出包含 manifest |
| 在“复检导出包”上传该 zip | 新目录重新检查 PASS，包内报告适用 |
| 上传一个没有配置的项目文件夹（报表下载工具），用向导填写入口、凭据变量和两个场景 | 配置有效；检查 FAIL：跟随跳转到禁止服务、凭据进入日志 |
| 手机宽度 390px 首页与项目页 | 无横向溢出 |
| 控制台错误 | 0 |

只读路由检查 [../console-v1/check-console.mjs](../console-v1/check-console.mjs) 同时通过（不发出任何写请求）。

截图：`home.jpg`、`new-config-example.jpg`、`project-fail.jpg`、`project-pass.jpg`、`project-uploaded-checked.jpg`、`recheck.jpg`、`projects.jpg`、`mobile-home.jpg`。

未覆盖：Windows + WSL 上的同一流程（由 5090 验证）；本地模型生成候选进入同一审阅链（P2）。
