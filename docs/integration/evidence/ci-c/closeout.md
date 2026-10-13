# C 收尾

状态：C_ACCEPTANCE_COMPLETE_IN_DECLARED_ENVIRONMENT，待 PR #13 评审。

被测程序/CI：466534c79eacf8dc9e59d267c9ee5e614b0f4a0f。
演示实际 checkout 为 GitHub 临时合并树，另见 results.json，不当作稳定分支 head。
当前后补提交只添加证据、材料校验工具与已验证范围说明，未重跑模型或演示。
全部十次真实工作流触发均列在 attempts.json，初稿故障保留，不拼接为成功率。

两个独立演示 PR 不合并：#14 漏洞原版双红，#15 既有人工参考修复双绿。
两者业务测试均实际 2/2 通过；前者仍有三个安全条件失败，后者 14 条满足。
不是新 AI 修复，也不声称告警自动关闭。模型调用为 0。

正式 native / container 均有 16/16 锚点；默认 Docker doctor=4、check=UNKNOWN(3)。
正式镜像扫描完整，未豁免命中 0，4,045 个已审阅匹配仍可逐项查看。
固定基础镜像、实际 apt、wheel、rootfs 清单及源码摘要在构建原件中。
没有发布模型、rootfs、虚拟环境或镜像 tar。GitHub 构件 ZIP 与源码 ZIP 不混用。

限定 AppArmor profile 尚无强制执行证据；本轮验证的是契约允许的显式 outer
unconfined 方案，另由宿主对固定 bwrap 路径加载 userns 应用例外。限制值保持 1，
未修改 sysctl。不要将该结果推广到所有宿主、Docker 或 LSM 组合。

浏览器已登录后读取真实告警和 job 摘要，四张匿名截图可查，未撤销告警。
截图通过排除导航和活动区域匿名，不重绘状态；小视口用于告警匿名截图，已恢复。
应用页面/启动器未改，沿用有摘要映射的既有浏览器验收，没有伪称新现场推理。

本轮实施与验收已结束。不合并三个 C/演示 PR，不修改 main，不创建 Release。
