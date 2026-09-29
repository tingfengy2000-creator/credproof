# 初赛机制 pilot：预先登记协议

> 保留原验收机制实验协议。本轮 Agent 对照、授权门禁、模板留出与分母定义见 [新协议](../local-agent/reliability/protocol.md)，两组结果不合并成一个成功率。

案例预期标签先于第一次执行登记。目标是核查“快照绑定的副本修复义务链”是否按定义工作，不把少量人工场景包装成真实世界检出率或领先成绩。机器可读定义为 `experiments/protocol.json`，runner 为 `experiments/pilot.py`。案例表中的 PASS、FAIL、UNKNOWN 是预期标签，实测另见具体 run 的结果文件。

这是一轮机制开发 pilot：16 个案例全部对开发者可见，没有独立最终留出集或盲测。开发 smoke 后，为澄清同范围公平比较，将 scope_omission 与 function_not_checked 从 fresh 移入 evidence_completeness 层，标签不变；同期明确 B-fresh 的独立统计和源码冻结记录。不能将这次澄清后的协议称为整个文本在所有开发结果之前完全冻结。

## 1. 研究边界与公平比较

只生成隔离的自有 Python 小仓库，使用 `CP_SYNTH_` 加 24 个十六进制字符的合成值，没有真实账户、认证请求或用户源码。每个仓库只有声明范围内的 `config.py`、`notes.txt`。原始目标是单行模块级字符串赋值，已有 `import os`，并有自有函数 `authorization_header()`；候选读取约定环境变量，不允许 fallback。这项 pilot 不评价通用 Python 改写能力、全语言覆盖或云端凭据有效性。

同一次 trial 的 A、B、C、C-no-binding 使用同一个扫描程序、配置、原对象、当前候选和同一份交付证据；调用时深拷贝，避免一个比较模式修改另一个模式的输入。A 只看扫描义务，B 检查范围内扫描、语法和受控功能，C 再检查原值移除、授权差异及所有证据绑定，C-no-binding 保留五项检查但去掉绑定判断。它们是本项目自建的机制对照，不代表 Gitleaks 或现成 CI 产品的默认策略，也不暗示那些产品承诺了修复状态管理。

正常 fresh 只保留同范围、完整执行的 10 例（4 个正确副本、6 个不符合契约的候选）。2 个 evidence_completeness 与 4 个 delivery 故障分别列结果；这 6 例中的 A/B 是“接收给定检查结果”的自建简化聚合策略，不代表合理 CI 固定范围重跑的行为。每例再对当前候选、完整意图范围重新 collect 后运行 B-fresh。对旧证据病例必须展示这个合理的“重新运行 CI”对照；如果 B-fresh 同样发现问题，结论应是绑定检查补充证据交付保障，不能宣称功能检测是 C 独有能力。不得用缩小支持范围换取全工具胜率。

B-fresh 已更换输入证据，因此单列统计，并以新证据对应的独立 scan/syntax/function oracle 判断；不得继续沿用旧交付证据的 UNKNOWN 标签，将其正常 PASS 算成错误接受。无关文件修改不影响这三个检查时，B-fresh 允许 PASS，表示检查契约覆盖范围不同，不声称该修改一定恶意。

## 2. 预先定义的 16 个机制案例

| 层 | 案例 | 独立事实 | C 预期 |
|---|---|---|---|
| fresh | good_basic | 合法环境读取，功能保持，原件不变 | PASS |
| fresh | good_format | 单引号、空白及注释变化后的同类直接赋值 | PASS |
| fresh | good_order | 函数定义在赋值前，附属非秘密配置保持 | PASS |
| fresh | constant_zero_alert | 删除格式值后改成无秘密常量；无告警但功能错误 | FAIL |
| fresh | fallback_retained | 旧值留在默认参数，环境缺失仍成功 | FAIL |
| fresh | syntax_broken | 候选出现明确语法错误 | FAIL |
| fresh | residual_other_file | 声明范围的另一个文件仍含同值 | FAIL |
| fresh | unrelated_change | 目标修复之外还改写 notes.txt | FAIL |
| evidence_completeness | scope_omission | 候选正确，但交付证据漏了 notes.txt | UNKNOWN |
| evidence_completeness | function_not_checked | 候选正确，但受控功能义务未执行 | UNKNOWN |
| fresh | index_residual_local_pass | 工作区已改，index 仍旧；指定副本正确 | PASS |
| fresh | wrong_environment_name | 读取错误变量，正向功能探针失败 | FAIL |
| delivery | stale_pass_replay | 收集成功证据后将候选改坏，再提交旧证据 | UNKNOWN |
| delivery | cross_object_evidence | 从另一独立对象取得成功证据再拼接 | UNKNOWN |
| delivery | cross_scope_evidence | 只替换扫描检查，使其来自较窄范围 | UNKNOWN |
| delivery | cross_rule_evidence | 只替换扫描检查，使其来自另一配置摘要 | UNKNOWN |

其中 scope_omission 与 function_not_checked 是缺证据，不是坏补丁；不计入坏修复拦截率。index_residual_local_pass 是“局部 PASS 与剩余风险同时成立”的正例，不能作为 C 拒绝了坏修复来计分。所有正常病例原 index 都可能仍含测试值，这正是“只改副本”的设计边界。

cross_rule_evidence 的 donor 配置只增加注释，实际检测语义相同、文件摘要不同；它检验的是严格来源身份契约，不是假装另一份规则漏检了秘密。cross_object/scope/rule 的目标候选本身保持正确，重新收集正确来源证据后 B-fresh 可以正常 PASS。

## 3. 独立 oracle 与防标签泄漏

案例定义先固定，runner 再生成材料并采集结果。评判器 `assess()` 仅接收 bundle、evidence、scanner 和 mode；不得获得 case_id、expected_C、目录名中的语义标签或预期结果。所有对象采用无语义序号目录；标签、预期及独立断言只存外层试验结果，不写入 contract、before、candidate 或 evidence。

oracle 不把 `assess()` 的输出重新当答案。它独立解析自己生成的候选 AST，检查目标是否为约定的 `os.environ[...]` 读取、原合成值是否仍出现、非目标文件是否发生变化，并使用仅适用于自有模板的受限行为解释器验证“注入指定值后返回 Bearer + 注入值”和“缺变量时失败”。它不导入候选、不执行任意仓库测试。证据交付病例另独立比较收集时对象摘要与当前文件摘要，或验证替换检查确实来自另一对象、范围、配置。预期标签与这些事实不一致时，该 trial 记为 ERROR，不能把实验构造失败计作方法成功。

原仓库保护独立比较原工作区文件和 `git show :路径` 结果；trial 前后均读取，必须逐字节相同。所有 Git 操作仅针对 runner 新建的输出子目录，使用参数数组，不运行 hooks、联网或处理真实仓库。原件发生变化时，该轮视为实验错误。

## 4. 执行与冻结记录

入口示例：

```text
python experiments/pilot.py --gitleaks <本地冻结可执行文件> --config <冻结规则配置> --output runs/pilot/ --repeats 3
```

每次命令创建新的时间戳目录，不覆盖旧实验。首先保存协议、runner、扫描器与配置的 SHA-256、扫描器版本、Python 版本、代码提交号和参数。配置的文字变更病例只能在独立 donor 中生效；主比较的扫描器/配置保持相同。无需下载额外数据集。程序失败、扫描失败或 oracle 构造失败保留错误，不能补成 PASS 或删除不利案例后重算。

同时保存 core/scanner/runner 源码摘要；结束时再次核对源码、协议、配置和二进制均未改变。提交号不能替代未提交代码的内容摘要。冻结输入在运行期间变化时，命令以非零状态结束，结果不能直接当成最终固定版本证据。

每次重复都重新生成仓库、冻结对象、候选及证据。默认 3 次用于发现执行不稳定；同一案例的三次运行仍是一个机制案例，不能写成 48 个独立样本。临时工作材料保留在该 run 目录，以便核查；外部分享使用脱敏结果，不打包原始材料冒充真实数据集。

开销另测：在 good_basic 的同一个有效两文件副本上，A、B、C 各独立执行 3 次“按模式裁剪 collect + assess”，依次轮换 A/B/C、B/C/A、C/A/B 顺序，记录原始毫秒数、均值、范围、样本方差以及 C 均值减 B 均值。A 只收集 scan，B 收集 scan/syntax/function，C 收集全部五项。主判决矩阵共享 full collect 的耗时不能代替各模式开销。这个单机、单夹具、每组 3 次的描述性结果不用于速度优势或显著性声明；时延部分失败也必须保留。

## 5. 输出、计数与结论约束

输出 `results.json` 保留逐 trial 的 oracle、A/B/C/C-no-binding/B-fresh 报告、预期一致性、原件保护结果、耗时和错误；`summary.md` 给出每例五列判决矩阵。fresh、evidence_completeness 与 delivery 分表，4 个原证据聚合模式都给出分子/分母：坏候选错误接受数 / 6、正确副本通过数 / 4、缺失或错配证据错误接受数 / 6、稳定 UNKNOWN 数 / 16。重复不扩大这些分母；错误接受按任一次 PASS 保守计数，正确通过和稳定 UNKNOWN 要求所有重复一致，混合结果和错误另列。B-fresh 有单独新输入 oracle，不混入原证据异常错误接受分母。

主要验收是：C 逐例与独立预期一致；原仓库无改写；错误与未知不伪装通过；B-fresh 对交付故障的表现完整公开。任何失败都意味着先修工程或缩小已验证能力，不允许改案例标签来迁就实现。合成值零告警不等于行为正确；结构识别成功不等于凭据真实有效；副本 PASS 不等于 index、历史或云端撤销完成。

结果完成后再写“观察到什么”。未运行前不预填准确率、提升比例、时延或领先结论；结果不支持预期收益时保留负面结论。更大数据集、通用语言修复、复杂结构关联与统计置信区间不属于本轮初赛 pilot 的验收要求。
