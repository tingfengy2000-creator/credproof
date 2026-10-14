# 已验证的容器运行方式

状态：**VERIFIED_IN_DECLARED_HOSTED_ENVIRONMENT**。
依据：`docs/integration/evidence/ci-c/README.md` 的两个独立演示和完整原始记录。
仅覆盖 GitHub 托管 Ubuntu 24.04 x86_64、Docker 28.0.4，以及本提交的程序。
不是所有内核、Docker/LSM 组合的认证，也不是生产安全保证。

固定 seccomp + systempaths=unconfined + network none + read-only + tmpfs /tmp:exec
+ cap-drop ALL + no-new-privileges + 非 root。显式选择外层 AppArmor unconfined；
Ubuntu 限制值为 1，宿主为固定的 bwrap 文件加载 userns 许可应用例外。
没有修改宿主 sysctl；不是自动放宽，也不宣称外层 AppArmor 仍在强制约束。

实际 profile 文件在证据中的 `container-userns.profile` / `native-userns.profile`，
其宿主加载命令及退出码可查。内层 doctor 实测有限 rootfs、独立命名空间、
零有效能力，并且看不到 /home、/workspace、/opt/credproof。
`deploy/apparmor/credproof-bwrap` 限定候选 profile 尚未取得宿主强制执行验收，
保留为可选候选，不与这里的明确放宽方案混淆。

镜像扫描完整结束，未豁免命中 0；报告保留 4,045 次已审阅匹配，
由 2,921 个精确文件/内容/匹配条目约束。目录没有被跳过，改变的文件不能
沿用旧例外。真实作者路径已排除，不作为例外。

安装 wheel 使用固定 ZIP 时间戳 1980-01-01，便于同源码的安装元数据复核。
这不是整镜像可跨日期逐字节复现的承诺：apt/PyPI 准备源仍可能更新，
实际版本、wheel、rootfs 和源码摘要在各次构建收据中记录。
