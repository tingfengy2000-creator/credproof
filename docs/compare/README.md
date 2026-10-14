# 真实对照数据（R4 A）

`comparison.json` 只从冻结的 `docs/bench/bench-results.json` 生成；本轮模型调用、候选执行与新实验均为 0。

```console
python scripts/compare/build_comparison.py
python scripts/compare/build_comparison.py --check
python -m pytest tests/test_comparison.py -q
```

总记录 88：同批 AI 51、锚点 16、历史 21。三批在 `batches` 中分别展示，不能把锚点与历史当新增模型生成成绩。顶层 `methods` 供完整材料核对，须同时展示 `coverage`/`missing`；两个文本裁判没有裁判历史 21 份，不能拿其缺失部分当零错误。

`unsafe` 延续原表的 FAIL 分组（34），其中也包括业务破坏、过度拒绝；不称 34 个独立漏洞。`good` 是声明条件 PASS（53），UNKNOWN（1）独立保留。不能以 CredProof 自己定义的分组去证明自身独立准确率。

`rejected_good` 沿用冻结表“未放行合格对象”的口径，包含 INVALID；`invalid` 是交叉计数。新增 `explicit_rejected_good` 可以区分明确拒绝与无效回答，不能把两个数字再相加。对应补丁 ID 与现有 `#patch/<id>` 路由由生成器提供。

CI 行仅表示当时实际配置的业务测试；规范 CI 可以追加安全断言、扫描与隔离检查。静态行仅为该批凭据规则，不代表静态分析的能力上限。文本裁判没有执行候选；其解释不能代替实际文件/服务回执。每行都有需求、可见范围与不可见范围，不作工具优劣总排名，不报告准确率或节时。
