# PR #4 执行层与接口评审结论

评审原始提交 `8e9dd7bdd8395fabfa488c37a985b50b308864d2`，没有合并 main。

1. **修正结果文件缺失返回 500（P2）**：`Application.bench` 初始缓存为 `(None,None)`，缺文件的 stamp 同样为 None，跳过读取并返回 None。随后 `.get` 触发 500，与契约 409 不符。现在先 stat，缺失/删除/解析失败均为明确 409；patch 列表也校验类型。三个新的定向 HTTP 回归通过。
2. **补足只读接口交付（P2）**：原 `view-readonly.py` 没有两个 bench GET 的白名单或 CLI 结果参数。现在只扩展 GET 路由和操作者参数，POST/路径穿越/查询/跨 Origin 仍拒绝。清洁安装用实际 HTTP 验证 6 项，禁止的执行/审批函数调用全部为 0。
3. **纠正测试可移植性**：原 native-runtime 两项测试假设改 HOME 就改变 Windows expanduser，并用 WindowsPath 模拟 POSIX 路径。分别 mock POSIX 主目录服务和已解析的 PurePosixPath；未更改生产 runner。Windows 的 WSL 分支通过真实 24+26 次前置复验，没有扩大挂载、网络或工具权限。
4. **冻结元数据缺陷单独说明**：`common.model_info` 将 `general.file_type=15` 填进 digest；这不是权重身份。本轮保留冻结函数及原输出，以独立登记与每次真实 `/api/ps` 记录提供准确 digest。下一个协议可修元数据字段，本批不换提示词、模板或采样定义。

未发现本 PR 的原生分支在 Windows 上放开宿主执行的证据；本轮证明的是 Windows/WSL 路径与登记预期一致，并不自动验证所有 POSIX 平台。旧 `_digest_tree` 跨系统身份问题的独立修复没有因 PR #4 自动并入；不可把本批只读 GET 或 Windows 复验写成其跨系统验收。

模型隔离适配不参与生成策略：它只将冻结脚本的 HTTP 请求转入相同 GPU/白名单/私有网络边界，逐字保存 body，并保存完整裁判 response/usage。两个固定模型、温度/seed/上下文/输出上限与 prompts 均未变。完整失败与 INVALID 均在本批数据中。
