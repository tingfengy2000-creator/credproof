# Twine 配置组件的外部接入

本轮接入真实开源项目的历史问题，不是人工注入。Twine [PR #1240](https://github.com/pypa/twine/pull/1240) 说明：读取格式错误的 `.pypirc` 时，未处理的 `configparser` 异常可能把敏感配置带到控制台。固定来源见 [source.json](source.json)，Apache-2.0 许可证及原文件保存在 `upstream-before`、`upstream-fixed`。

| 对象 | 固定提交 | 结果 |
|---|---|---|
| 上游修复前 | `4038f7bdfdad05697510a3f9657bd4fdc7c12d4b` | 3 个错误配置条件泄露；4 个正常/既有错误处理条件通过 |
| 上游修复后 | `ae1d03bf1f6943c3ffd65597044ccac6294b065e` | 7 项条件通过 |
| 本地模型候选 | 本项目冻结执行版本 `64b091f104772ac8eab63ad94b1b28fb61ddb0da` | 5 次模型调用、3 份候选；第三份通过 7 项条件，任务完成 |

这是 **1 个外部组件场景的 7 项验收条件**，不增加原 8 例统计分母，不代表外部泛化率。首次适配探测因可信 harness 中 future import 位置不合法而 UNKNOWN；修正 harness 后再进入唯一一次模型任务。全部探测与三份候选均保留在 `experiments/external-twine`。

## 保留了什么，适配了什么

执行 `twine/utils.py` 的 `get_repository_from_config` 配置文件分支；`get_config`、`normalize_repository_url` 和两种异常类由固定原文件逐字提取，解析逻辑、默认仓库、用户与凭据读取、URL 规范化、缺文件与缺仓库错误逻辑保留。`repository_url` 固定为 None，未调用上传或联网认证。可信 harness 仿照上游 `__main__.main` 的领域异常输出，其他异常保留 traceback。

现有旧样例裁判只支持 `run(request, auth_service)`，不适合直接加载 Twine。为避免把 Twine 改写为旧 fixtures，本次增加一个**限定配置组件适配器**：只允许追加配置解析异常转换分支，原业务 AST 和原有异常分支不可改；新增消息表达式不能读异常值或配置值。这个编辑范围明显比任意代码修复窄，且明确告知模型。因此这次结果支持“保留上游组件业务的受控接入可行”，不证明模型自主找到了通用修复策略，也不声称超过固定规则。

旧裁判和 `sandbox_runner.py` 未放宽。候选始终在既有无外网、只读根文件系统、资源及系统调用限制的隔离设施内执行。合成凭据只在执行侧生成；模型收到脱敏控制台内容，不能读取上游参考修复、测试断言或其他文件。

## 三份候选与真实成本

第一份追加两个 handler，边界拒绝；第二份使用元组异常类型，超出预先固定的单一解析异常轮廓，边界拒绝；第三份仅追加 `configparser.Error` → `InvalidConfiguration` 的安全错误摘要，通过程序检查。前两次是**修改权限拒绝**，不是已执行补丁的泄露/功能 FAIL，不与 h03 的动态失败反馈混为一谈。

实际模型请求 5 次，服务端报告输入 tokens 合计 14,671、输出 1,046；模型任务区间 5.993 秒，外部子进程区间 7.500 秒。模型预热和环境准备不包含在这两个区间内。不据此声称人工节省时间或稳定速度。

## 复现和复检

需要本地模型的新推理：在已准备的 WSL 环境、项目根目录运行下面命令，`<runtime>` 替换为统一配置指向的 Linux 目录；输出目录必须不存在。

```sh
CREDPROOF_RUNTIME_ROOT=<runtime> unshare --user --map-root-user --net --fork <runtime>/venv/bin/python -B -m agent_pilot.offline_run --external-twine --output <new-output>
```

不需要模型的程序验收：

```sh
python -B -m agent_pilot.external_twine probe <new-output>
python -B -m agent_pilot.external_twine export <run>/external --destination <new-material>
cd <new-material>
python -B -m agent_pilot.external_twine recheck .
```

复检读取当前材料、比较旧报告绑定、检查清单并再次执行七项条件；它不信任保存的 PASS。缺少隔离返回 UNKNOWN，无宿主执行回退。信任前提是本地需求、适配器、校验工具和隔离设施；摘要不构成第三方认证。原始源码及许可证包含公开上游署名，匿名比赛正文与内部研发来源资料分别管理。
