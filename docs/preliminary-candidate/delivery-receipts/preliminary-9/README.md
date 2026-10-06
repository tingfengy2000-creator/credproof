# preliminary.9 候选材料交付收据

- 候选版本：`0.2.0-preliminary.9`
- 源码固定提交：`55d6c4a18bdb9bb9744590d9bbb4bcd4e24c58c2`
- 评审源码快照：`credproof-0.3.0-dev.13-20261006-55d6c4a18bdb.zip`
- 评审快照 SHA-256：`25f2fe93d1395125b2b084aafbf8da426190b60e15e3f8e8666121759f6c2d9c`
- 候选包：`credproof-preliminary.9-20261006-55d6c4a18bdb.zip`
- 候选包大小：17,817,530 字节
- 候选包 SHA-256：`2dd62f923a521fd752b38e62228ebb7104a944c68f8ec4bad8e2e2e51c626126`
- wheel：`credproof_safety-0.3.0.dev13-py3-none-any.whl`
- wheel SHA-256：`d56e58234bc8585c23b92c331d310916317f1c428d1b23272d621dcd6c981213`
- PDF：`docs/preliminary-candidate/credproof-manuscript-candidate.pdf`，585,616 字节，SHA-256 `91e63ca2cbf1d3d374248048fbed9e83063b07557b865b8239dbb570cbf554d8`

## 验证范围

源码快照由 `scripts/build-review.py` 从固定提交生成；候选包在其上附加同一干净工作区构建的 wheel 和 `candidate-package.json`。ZIP 未提交到 Git 历史。PDF 使用 WPS Office 导出、pypdfium2 逐页渲染，12 页全部检查，匿名字段仍为“待填”。

定向命令：

```powershell
.venv\Scripts\python.exe -m pytest -q agent_pilot/tests/test_web_material_binding.py agent_pilot/tests/test_bundle.py
# 28 passed
C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe agent_pilot/tests/test_ui_project_verdict.js
# ui-project-verdict-regression: PASS (FAIL/PASS/stale/missing cases)
```

界面显示回归未执行 Agent；浏览器现场查看模式真实显示未执行项目的总体 `UNKNOWN`。现场重新检查仍依赖既有 WSL/隔离设施，缺少隔离时不在宿主机降级执行。

历史视频保持静态帧停留剪辑，并在 `video/README.md` 中明确标注；本轮没有把历史画面改称连续录屏或模型现场推理。
