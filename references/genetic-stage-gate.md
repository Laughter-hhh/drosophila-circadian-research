# 遗传设计的 stock-to-cross stage gate

validate_genetic_stage_gate.py 将完整 cross plan 与 formal readiness 分开。formal 行必须同时提供 --stock-audit 与 --source-access-report。

## Formal gate

- driver 与 effector 必须在 stock audit 中出现且为 identity_verified。
- driver expression 必须为 verified；成人期限制为 verified 或 not_applicable；发育控制为 present 或 not_applicable；背景为 matched 或 not_applicable。
- source-access JSON 中两个 parent stock candidate 都必须有 access_status=reachable_content_verified。只有 URL 存在、HTTP 可达或 conditional_source_access 都不能通过。
- pilot/conditional_pilot 可以保留缺口，但每个缺口必须成为 warning，并标记 blocked_for_formal。

source-access JSON 由 scripts/check_source_access.py 或人工浏览器核查后生成，按 record_id 连接到 driver_stock_candidate 和 effector_stock_candidate。challenge/login/dynamic 页面若未匹配 token，会得到 reachable_content_unverified，formal gate 必须阻断。

## 状态边界

status=verified_genetic_stage_gate 只表示结构和字段通过，不等于 formal cross 已获准。formal_status=conditional_pilot_only 表示只能做预实验；formal_gate_passed_external_checks_pending 仍需外部核查；formal_requires_online_source_access 或 formal_requires_verified_online_source_access 表示在线来源门禁缺失或未通过。

## 推荐命令

    python scripts/validate_genetic_stage_gate.py validation/public-data/top4-rnai-genetic-stage-gate.csv --stock-audit validation/public-data/shaw-clock-tool-stock-audit.csv --source-access-report validation/public-data/stock-source-access-validation.json --output validation/top4-rnai-genetic-stage-gate-validation.json

先使用 conditional_pilot；完成 stock 身份、在线来源、成人期限制、背景匹配和表达验证后再复制为 formal。该 gate 仍不验证 driver 实际表达、RNAi 效率、插入方向、背景纯合度或当前库存。
