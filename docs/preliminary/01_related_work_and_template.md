# 初赛相关工作与官方模板核查

核查日期：2026-09-29（北京时间）。范围：官方文档、当前公开源码、两篇原论文、赛事官网及本地模板；未运行竞品、未测量效果、未登录报名或提交材料。本文服务于初赛版本，不替换 `docs/plan-v2` 的历史方案。

## 1. 已有能力与公平比较边界

| 对象 | 本次确认的已有能力 | 对 CredProof 的约束 |
| --- | --- | --- |
| Gitleaks | 官方 README 支持 `git/dir/stdin`，以及 baseline、allowlist、复合规则；当前 `cmd/git.go` 有 `--staged`，实际调用 staged diff。未提供自定义配置时使用内置默认配置。[1] | 不能写“现有工具不查暂存区”“只能匹配孤立字符串”。全量 index blob 与 staged diff 范围不同；若比较，应把相同字节提供给同版本、同配置检测器，另做模式差异实验。 |
| TruffleHog | 支持 Git、文件系统、stdin、pre-commit；当前源码在 hook 上下文配置暂存变更扫描。区分 `verified/unverified/unknown`，支持关闭验证、扫描错误退出控制；自定义规则可不设置验证端点而报告 unverified。[2] | 不能把离线检测或错误状态处理当成我们的独有能力。用合成、无效凭据评测时应关闭在线验证，并保留未验证发现；只取 verified 会把实验变成凭据有效性筛选。 |
| GitHub Secret Scanning | 扫描平台仓库各分支历史及若干协作内容；支持通用/自定义模式、有效性检查。状态有 active/inactive/unknown，某些验证还使用 host/URL 上下文。[3] | “发现凭据”与“凭据有效”已有明确区分。平台服务和本地未提交 index 不属于同一观测范围；不得据此宣布平台不支持上下文、历史或处置。未实测的能力记作未确认。 |

两类 fallback 必须分清：把原密钥留在环境变量读取的默认值中，仍可能被现有内容检测器检出，不能预设竞品必然漏检；外部扫描器不可用时换用简易内置规则，则必须记录真实引擎、版本和规则范围，不能继续把结果称为 Gitleaks/TruffleHog。是否识别某一具体假修复，只能由固定输入的实验说明。

特别注意，TruffleHog 当前源码在 pre-commit 上下文还会把结果过滤改为 `verified,unknown`。[2] 离线合成样例对照不能直接套用该 hook 输出，应采用明确输入范围的普通调用，并核对实际过滤条件。

上述源码核查针对当日公开分支，不等于某个已发布二进制具备完全相同的选项。正式对照应冻结 release/commit、配置、排除项、输入范围、退出码和错误日志；扫描失败或范围不全不能按“零发现”计成功。本文未证明任何竞品缺少完整修复验证链路，也不把未查到文档等同于“不支持”。

## 2. 修复验证与证据绑定的研究依据

**通过测试不等于正确修复。** Qi、Long、Achour、Rinard 的 ISSTA 2015 原论文分析 generate-and-validate 修复系统，区分测试集上 plausible 与真正 correct；还指出仅检查退出码等弱代理及删掉功能的补丁会制造假成功。原文 PDF 第 1—2 页、§2—3 是本项目最相关依据。[4] 因此，“复扫无告警”“语法通过”“程序退出 0”都不足以单独证明凭据修复正确。受控功能检查应比较明确的预期行为，同时检查旧值残留、扫描范围和源版本。有限测试仍不能证明任意程序语义等价，报告只能写“在指定范围和测试义务下通过”。

**将步骤、输入和产物绑定是已有工程与研究思想。** Torres-Arias 等人在 USENIX Security 2019 的 in-toto 论文中，用材料、产物、命令、执行副产物和签名元数据描述软件供应链步骤；§2、§4.2（PDF 第 3、8 页）明确使用输入/输出哈希核验产物流转。[5] CredProof 可借鉴其可追溯原则，记录源快照、补丁、规则配置、验证器版本和证据文件的摘要关系。但本地 JSON 加哈希若没有独立签名和可信执行者，只能帮助检查内容一致性，不能宣称达到 in-toto 的供应链保证，或证明同一操作者没有同时篡改文件与摘要。

## 3. 初赛可主张什么

| 层次 | 拟写入报告的表述 |
| --- | --- |
| 已有/复用 | 凭据模式检测、Git 内容读取、暂存区扫描、有效性与存在性区分、测试驱动验证、摘要绑定均有先例；明确标注工具和研究来源。 |
| 我们待测的增量 | 面向受限凭据修复，把源版本、声明范围、精确值移除、语法、受控功能及复扫组织成可复算的验证契约；对缺证据、过期证据和假修复拒绝给出完整通过结论。 |
| 必须由实验支持 | 对比较 A“只复扫”、比较 B“同范围复扫＋语法检查＋受控功能测试”和完整契约使用同一组修复候选，统计错误接受、正确接受、拒绝/未知与耗时；单独消融版本绑定和完整性门槛。 |
| 禁止提前写出的结论 | 首创、全面超越检测器、自动证明程序正确、保证没有泄露、已撤销全球凭据，以及尚未运行的准确率、提升率或成功率。 |

挑战样例可覆盖保留默认原值、移走而非移除、工作区改了但 index 未改、删除必要功能、缩小扫描范围和验证后再次改源。需同时包含有效修复，不能靠全部拒绝获得漂亮的“零错误接受”。这些是实验设计，不是已经验证有效的成果。

## 4. 官方赛程及提交材料状态

本次实时打开官网赛事首页、通知列表与当届邀请函。首页公示报名为 **2026-06-18 至 2026-10-18**，资格审查至 **10-21**，作品提交至 **10-22**；邀请函给出的报名末时为 **10-18 23:59**。所查通知列表最新当届通知仍为 2026-06-18 邀请函；其内容可在线更新，发布日期不等于未修改。[6]

截至 2026-09-29，日期处于官网公示窗口内；**未核查用户账号、培养单位审核、校内选拔截止或提交按钮状态，不能据此保证用户仍可报名/提交**。邀请函要求培养单位资格审核通过。初赛采用专家网评，提交 PDF 文档（不超过 10M）及可执行程序；资料还包括作品声明，不能只交架构图。[6]

邀请函第五部分同时出现“队长姓名+作品名称+资料名称”和文件命名填写高校名称的表述，存在文字不一致。本轮保留该不确定性，不自行拼出最终文件名；提交前应以平台字段及赛事明确答复核对。本轮没有联系组委会或发送材料。

## 5. 模板逐项对照

从官网邀请函附件 2 在内存读取 ZIP，只读取其中 DOC 字节，未运行文件、未另存下载包。包内作品报告、原创性声明、重大改进说明三个 DOC 均与本地同名原件 SHA-256 一致。[7] 报告正文采用已存在的本地抽取文件：`E:\比赛\选题与架构方案\working\templates\中国研究生网络安全创新大赛作品报告.txt`。

| 本地报告位置 | 已确认要求及本项目落实方式 |
| --- | --- |
| 填写说明第 1—4 条 | 基本完整的设计；A4；除标题外宋体、小四、1.5 倍行距。删除指导性说明文字，但保留“填写说明”页；允许增加内容或微调结构。 |
| 填写说明第 5 条 | 避免学校、院系、指导教师等身份信息，违反可取消资格。正文、图表和截图均检查匿名性；报告元数据检查属于我们的提交质量措施。 |
| 摘要 | **500 字以内**，说明动机、功能、特性、创新及实用性；该限制针对摘要，不是整份报告。 |
| 目录及章标题 | 摘要；第一章作品概述；第二章作品设计与实现；第三章作品测试与分析；第四章创新性说明；第五章总结；参考文献。 |
| 参考文献示例 | 模板提示参考 GB/T 7714-2015；最终条目需对应实际引用，不能保留示例文献冒充相关工作。 |

本地原件：`E:\比赛\第五届中国研究生网络安全创新大赛作品相关模板\中国研究生网络安全创新大赛作品报告.doc`。报告 DOC SHA-256：`4c5ad7c9d54ab7a92243e61bb2db36d86fa3df8c2eb498793c080dacd7b7cdbc`；官网附件 ZIP 为 12,541 字节，SHA-256：`ac8c2dea17e913c69356b91de70a42b206cb810256adb733ef746f3e7e87c02c`。本轮确认文本要求与字节一致性，未重新渲染 Word 检查分页，也没有把模板中预置的“共 7 页”当成报告页数上限。

## 6. 核查来源

以下为 7 组直接来源，均于 2026-09-29 核查；公开分支和赛事网页可能变化，实施/提交前应冻结所用版本。

1. Gitleaks：[官方 README](https://github.com/gitleaks/gitleaks)、[当前 Git 命令源码](https://raw.githubusercontent.com/gitleaks/gitleaks/master/cmd/git.go)、[staged diff 实现](https://raw.githubusercontent.com/gitleaks/gitleaks/master/sources/git.go)。
2. TruffleHog：[官方 README](https://github.com/trufflesecurity/trufflehog)、[当前 main.go](https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/main.go)。
3. GitHub：[Secret scanning](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning)、[Validity checks](https://docs.github.com/en/code-security/concepts/secret-security/validity-checks)。
4. Qi Z, Long F, Achour S, Rinard M. *An Analysis of Patch Plausibility and Correctness for Generate-and-Validate Patch Generation Systems*. ISSTA, 2015: 24–36. DOI: 10.1145/2771783.2771791。[作者公开原文](https://people.csail.mit.edu/rinard/paper/issta15.pdf)。
5. Torres-Arias S, Afzali H, Kuppusamy T K, Curtmola R, Cappos J. *in-toto: Providing farm-to-table guarantees for bits and bytes*. USENIX Security, 2019: 1393–1410。[会议页面](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias)、[论文原文](https://www.usenix.org/system/files/sec19-torres-arias.pdf)。
6. 中国研究生网络安全创新大赛：[当前赛事首页](https://cpipc.acge.org.cn/cw/hp/2c90800c8093eef401809d33b36f0652)、[通知列表](https://cpipc.acge.org.cn/cw/contestNews/list/2c90800c8093eef401809d33b36f0652/1)、[第五届邀请函](https://cpipc.acge.org.cn/cw/contestNews/detail/2c90800c8093eef401809d33b36f0652/2c9080199ed8b78d019ed96ceea21560?page=1)。
7. 邀请函附件 2：[第五届作品相关模板 ZIP](https://cpipc.acge.org.cn/sysFile/downFile.do?fileId=dc0d4965d508456db60ab9464d39b476)。与上述本地 DOC 的字节核对通过；格式、匿名及 500 字要求来自报告模板正文。
