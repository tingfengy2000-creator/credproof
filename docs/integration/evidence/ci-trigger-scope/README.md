# C 合并前触发范围修正

依据 PR #13 评审评论 6149425198，只修改工作流的 PR 目标分支过滤。
原验收交付：83f21d78edc356f8f2e4ce94064afefd983c07fc；原安全运行证据不改写。

**主线 PR 不触发。** `pull_request.branches` 仅含 `demo/ci-gate-base`，
不是对 PR 的 head 分支过滤。通过 GitHub API 核对 #14、#15 的真实 base，
两者均为该演示分支，继续匹配。#13 提向 `feat/frontend-human-review-5060`，
不匹配；`main` 也不匹配。两条演示 PR 保持 open / merged=false。
这是合并前的真实字段快照。本轮用户已授权完成该修正后合并 #13；
旧 C 收尾文件中当时的“暂不合并”记录保留，不追改历史安排。

[checks.json](checks.json) 保存实际 PR 字段、范围匹配、工作流 jobs 原文摘要，
以及本次定向协议测试命令、退出码和结果。测试是配置/软件协议验证，
不冒充新的托管运行或安全验收；新增模型调用、候选执行和容器构建均为 0。

工作流 jobs、调度器、检查器、目标配置、镜像和固定样例未改变，继续引用
[C 原始完整验收](../ci-c/README.md)。接入其他仓库须同时替换 branches 和
targets.txt，见 [CI 使用说明](../../ci.md)。
