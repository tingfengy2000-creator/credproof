# preliminary.4 交付核对

本版目标是一个外部组件、分层运行入口和真实演示。历史八例、旧失败与旧候选包保持不变，不新增泛化率或获奖承诺。

## 结果与边界

| 内容 | 实际结果 | 可读证据 |
|---|---|---|
| 已修机制回归 | 起始 37 项通过；加入本轮入口与适配器后 52 项通过；历史时间修正后 22 项定向回归通过。数字是软件测试数，不是安全案例数 | `checks/external-delivery-20261003/baseline-regressions.txt`、`final-regressions.txt`、`history-time-regressions.txt` |
| Twine 原版与公开修复 | 原版 3 个错误配置条件确认 stderr 泄露，4 个正常/既有错误条件通过；上游修复版 7 项通过 | `experiments/external-twine/20261003-probe-02` |
| 一次真实模型任务 | 冻结提交 `64b091f104772ac8eab63ad94b1b28fb61ddb0da`；5 次请求、3 份候选；两份被边界拒绝，第三份通过 7 项，正常完成。没有重新抽样 | `experiments/external-twine/20261003-live-01/external/result.json`、全部 model 请求响应与 candidate 文件 |
| 运行成本及网络 | 模型任务 5.993 秒，外部子进程 7.500 秒，不含预热；服务端输入/输出 tokens 为 14,671/1,046。每 2 秒采样 10 次，观察显存峰值 19,184 MiB，非连续精确峰值。运行网络只有 lo，外连探测均未连通 | 同目录 `run-summary.json`、`resources.json`、`network-before/after.json`、`service-config.json` |
| 外部材料干净目录复检 | 仅 pip 的新 Windows Python venv；材料 INTACT、旧报告适用、新检查 PASS（7 项），无需模型 | `checks/external-delivery-20261003/clean-external-recheck.json` |
| 页面实录中的新复检 | h07 当前对象 13 条 trial PASS，历史材料 INTACT，旧报告适用；界面 14 条依据含额外 1 条 profile。导出按钮实际返回下载成功 | `checks/external-delivery-20261003/recorded-recheck-9f06460adee142cc96e69e7f1876cf8b.json`、实录帧与视频 |
| 说明书与视频 | PDF 13 页、588,305 字节；逐页检查版式并清除作者元数据。实录 180 秒与同素材 60 秒字幕版，无配音；检查 8 个解码关键画面 | `render-validation.json`、`video/video-receipt.json`、`video/capture-manifest.json` |

所有新动态执行仍使用既有隔离环境和本地模型，作品本次运行未调用付费 API。新源码目录和新 Python 环境在同一机器上，未声称跨机器验证。

## 执行命令

从项目根目录：

```powershell
python -B -m unittest agent_pilot.tests.test_web_material_binding agent_pilot.tests.test_bundle agent_pilot.tests.test_runtime_config agent_pilot.tests.test_presentation -v
python -B -m agent_pilot.external_twine probe experiments/external-twine/20261003-probe-02
python -B -m agent_pilot.preflight
```

模型执行使用现有 `offline_run --external-twine` 入口和局部无外网 namespace，原始命令、退出 0 和耗时见 `supervisor-result.json`。最多 12 调用、3 候选，没有云端回退。推理期间注册文件逐字节摘要一致；随后 `web.py`/`launch.py` 的分层入口及时间修正是交付修改，没有回填模型运行记录。

新目录中实际执行 `python -m agent_pilot.launch --demo --mode recheck --port 8786`，浏览器逐一查看 h01、h03、h07，点击重新验收与导出。外部材料目录中实际执行 `python -B -m agent_pilot.external_twine recheck .`，退出 0。最终候选 ZIP 的独立清单、解压和启动记录随包外校验材料提供，后续不会改写包内源码。

## 保留的失败与制作修正

第一次适配 probe 因可信 harness 的 future import 放在沙箱前导语句之后而报 SyntaxError，两对象均 UNKNOWN；原记录位于 `20261003-probe-01`，错误原文见 `adapter-probe-failure.txt`。修正仅涉及 harness 装配，不放宽隔离或断言；第二次 probe 后才冻结并执行一次模型任务。

包外命令第一次误在主项目目录执行 `recheck .`，缺少材料清单退出 1；转到材料根目录后通过。一次制作目录的 Git archive 命令因目录不是 Git 仓库而失败，未改变仓库，随后从实际项目固定提交生成新目录。上述是操作/打包路径错误，不计作模型失败或成功。

录制前发现复制/解压改变 mtime，旧页面却用它标记历史任务时间。本版改为读取已保存的 `task_started`/`task_finished` 事件，缺少事件显示未知；视频显示 2026-09-29 的历史与 2026-10-03 的新复检，不混同二者。

文档技能 renderer 缺少 LibreOffice，原错误与退出 1 保留在 `docx-renderer.txt`；使用本机既有 WPS 导出，再由 PDFium 逐页渲染检查。没有安装新的办公软件，未将失败 renderer 标记通过。

## 保留内容与后续事项

`experiments/local-agent-pilot`、原 h01/h03/h07 可复检材料、旧裁判和 sandbox runner 相对基线无改动。preliminary.3 ZIP SHA256 仍为 `6e822a04c5cc7cf7b67768cc8fe2bd4beb1745778da69b28d9444a00368f3cb4`。不改 main，不发布 Release，不提交赛事平台。

当前支持已登记 Python 任务及 Twine 配置文件组件的窄适配；没有通用上传执行、任意仓库、多语言或真实云撤销。更广接口适配、跨机器验证和人工使用研究留到后续。身份、AI 辅助开发许可与声明签署仍由参赛者及导师/组委会确认。
