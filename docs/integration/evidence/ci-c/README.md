# C：GitHub 托管 runner 实测入口

起点：a5b51e303315dd2dd3f4671d7a771fb9afab0310。模型调用为 0。

状态：**C_ACCEPTANCE_COMPLETE_IN_DECLARED_ENVIRONMENT**；容器已在下面的
明确 AppArmor 选项下实测。等待本 PR 代码评审，不等于第三方认证。

[收尾说明](closeout.md) · [公开材料完整清单](manifest.json) ·
[材料静态校验](publication-validation.json)。

## 固定版本与两个演示

程序/工作流源码：`466534c79eacf8dc9e59d267c9ee5e614b0f4a0f`。
后续提交只添加收据、索引、状态与本地材料校验脚本，不更改被测运行流程。
checkout 为 GitHub 的临时 PR 合并树，实际 SHA 与稳定 head SHA 均在
[results.json](results.json) 记录，不把两者混用。

| 独立控制 | PR / 托管运行 ID | native | container | 必要业务测试 | 安全条件 |
|---|---|---|---|---|---|
| 既有漏洞原版 | #14 / 38414183954 | FAIL(2)，job 红 | FAIL(2)，job 红 | 2/2 实际通过 | 3 项不满足 |
| 既有人工参考修复 | #15 / 38414202492 | PASS(0)，job 绿 | PASS(0)，job 绿 | 2/2 实际通过 | 14 项满足 |

两个分支都提向独立的 demo/ci-gate-base，不合并。漏洞入口与历史 Qwen3
原样补丁逐字节一致；base 已包含它，因此漏洞 PR 通过新增运行登记触发，
没有伪称新增漏洞。参考修复不是新 AI 输出。只证明红/绿闸门，不说明告警关闭。

## 实际验收及原件

- [逐次命令、退出码、stdout/stderr、完整报告和派生格式](runs/)；
  [实际下载字节和 GitHub 构件摘要](artifact-receipts.json)、
  [逐文件取件收据](collection-receipt.json)。不把 GitHub 源码 ZIP 当作构件 ZIP。
- 每个环境的 [漏洞控制](runs/vulnerable/) 与 [参考控制](runs/reference/)
  均有独立 16/16 锚点；程序来自同次安装包，输入固定取自 A+B 基线。
  必要测试与独立入口场景的原报告随锚点逐例保留。模型调用为 0。
- [native doctor](runs/reference/native/doctor.json) /
  [container doctor](runs/reference/container/doctor.json)：ready，专用 rootfs，
  不可见 /home、/workspace、/opt/credproof，独立 user/net/pid/mnt，能力已丢弃。
- [默认容器 doctor](runs/reference/container/default-blocked/doctor.json) 退出 4；
  [实际 check](runs/reference/container/default-blocked/report.json) 为 UNKNOWN(3)。
  这是命名空间阻断；不是错误 CLI 参数导致的退出 4。
- [AppArmor 环境与限制值](runs/reference/container/identity.json)、
  [实际附着与安装入口](runs/reference/container/container-origin/stdout.txt)、
  [固定 bwrap 的 userns 应用例外](runs/reference/container/container-userns.profile)、
  [拒绝日志](runs/reference/container/apparmor-denials/stdout.txt)。
  限制值为 1、外层为 unconfined、内层为命名的 unconfined 应用例外；未改 sysctl。
  限定版 deploy/apparmor/credproof-bwrap 仍没有强制执行证据，不能称其已验收。
- [完整镜像扫描](runs/reference/container/image-scan.json)：COMPLETED，
  8,960 文件、204,822,007 字节，未豁免命中 0；已审阅模式匹配 4,045 次。
  [精确例外目录](../../../../deploy/docker/scan-exceptions.json) 和
  [审阅来源](scan-exception-review.json) 公开；变字节失效，不按目录跳过。
  [native 格式扫描](runs/reference/native/formats-scan.json) /
  [container 格式扫描](runs/reference/container/formats-scan.json) 均完整、0 命中，
  包含实际 SARIF/JUnit/摘要，另检查仓库账号值且不把该值放入公开收据。
- [构建收据](runs/reference/container/build-receipt.json)：基础摘要、实际 apt
  版本、wheel SHA、源码及 rootfs 清单 SHA；[构建原输出](runs/reference/container/build/stderr.txt)。
- [完整软件回归与沿用浏览器依据](software-validation.json)；Windows 258 通过、
  2 个 Linux 专项跳过、1 个 qwen-agent 依赖导入弃用警告；没有模型调用。
  页面/启动/判断/组件与 A+B 基线对应文件摘要不变，浏览器验收明确沿用，未冒称重跑。

## 三项失败事实与截图

入口跳转场景预期 HTTPError，却正常返回；禁止服务收到 1 次请求且携带正确
合成认证凭据；观察到 1 次未授权连接尝试。正常业务 2/2 通过不能抵消它们。

- [红色检查列表](screenshots/failure-checks-final.jpg)
- [Code Scanning 实际告警](screenshots/failure-alerts.jpg)
- [job 摘要的具体失败事实](screenshots/failure-summary-final.jpg)
- [绿色检查列表](screenshots/success-checks-final.jpg)
- [截图来源及可见文字核验](screenshots/index.json)

截图只使用实际 GitHub 页面；通过滚动排除账户/仓库导航，不重绘检查结果。
SARIF 没写 region，GitHub UI 显示的 :1 是平台文件级回退，不是本项目定位到第 1 行。
漏洞 PR 没有改入口行，Code Scanning 的“无新增改动行告警”检查可能为绿；
三个分支告警仍可查，CredProof 两个闸门以实际 check 非零退出为红。

## 历史迭代与适用范围

[attempts.json](attempts.json) 保留全部触发与初稿失败，包括 doctor 参数错误、
锚点目录冲突、Ubuntu userns 拒绝，以及隐私清单未完成。它们是工程迭代，
不作为额外安全案例或模型成功率。首次错误参数产生的 doctor=4 不算隔离证据。
现有旧 B/WSL 记录保留；本次新增非 WSL 证据来自托管 VM，不是物理机验证。

实现：[工作流](../../../../.github/workflows/credproof.yml)、
[调度器](../../../../scripts/ci/run.py)、
[锚点工具](../../../../scripts/runtime/verify-anchors.py)、
[镜像扫描](../../../../scripts/runtime/scan-image.py)。
使用步骤及未实测的 GitLab/Jenkins 片段见 [ci.md](../../ci.md)。
