# 工作台前端

单页应用，由 `agent_pilot/web.py` 直接提供，只有三个静态文件：

| 文件 | 内容 |
|---|---|
| `index.html` | 全部视图的结构：首页案例、我的项目、新建检查、项目页、复检导出包、运行环境，以及参考材料（对照与接入、补丁记录、流水线闸门、案例回放、命令行接入、工作原理） |
| `styles.css` | 样式；不使用外部字体或 CDN |
| `app.js` | 哈希路由、接口调用和渲染；首页案例数据在 `STORY_EVIDENCE` 常量中，由测试核对与真实报告一致 |

页面启用严格内容安全策略：不允许内联脚本和内联样式，因此所有行为都写在 `app.js`，所有样式写在 `styles.css`。写操作需要启动时下发的会话令牌，并校验 Host 与 Origin。

接口说明见源码中的 `agent_pilot/web.py`。查看模式下，检查、复检和模型候选由后端拒绝，页面同时禁用对应按钮并说明原因。

自检：

```
node --check agent_pilot/ui/app.js
node agent_pilot/tests/test_ui_project_verdict.js
python -m pytest agent_pilot/tests/test_product_workspace.py agent_pilot/tests/test_web.py
```
