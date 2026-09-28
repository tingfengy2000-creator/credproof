# 密证 CredProof

面向代码仓库的凭据暴露研判与可验证修复系统。

当前阶段：方案评审，尚未开始业务功能实现。

本仓库用于版本管理与后续开发。GitHub 远端为私有仓库，已完成实际推送验证。账号凭据、模型权重、原始比赛材料和真实秘密样本不进入版本库。

当前方案：React + TypeScript + Vite 前端，FastAPI + SQLite 精简后端，现成 Qwen3 4B 的本地推理辅助解释。所有检测与修复验证结论由确定性检查产生。

## 查看设计

- [方案目录](docs/plan-v2/README.md)
- [定位与总体架构](docs/plan-v2/00_方案总览与总体架构.md)
- [前端体验与视觉规范](docs/plan-v2/01_前端体验与视觉规范.md)
- [精简后端与验证契约](docs/plan-v2/02_精简后端与验证契约.md)
- [轻量模型与隐私边界](docs/plan-v2/03_轻量模型与隐私边界.md)
- [实施排期与 Git 交付](docs/plan-v2/04_实施排期与Git交付.md)

下载或克隆后，可用浏览器打开 `docs/plan-v2/prototype/index.html` 查看可点击界面原型，打开 `docs/plan-v2/review.html` 阅读含七张图的离线整合版。GitHub 网页不会直接执行这些 HTML。

**界面原型全部使用模拟数据，当前没有实际扫描、修复或模型性能结果。** 架构图的 SVG/PNG/Mermaid 图源位于 `docs/plan-v2/diagrams/`。`qa/` 的检查记录只验证文档和原型，不代表业务验收。

用户批准新版方案后再开始业务实现。
