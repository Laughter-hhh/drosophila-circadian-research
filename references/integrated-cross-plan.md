# Integrated cross plan audit

validate_integrated_cross_plan.py 将亲本/F1/balancer/正反交/背景/温度/周期字段，与 stock identity、driver expression、成人期限制、发育控制、背景和在线来源 gate 合并。它还检查 driver_stock_candidate 与 effector_stock_candidate 是否真的出现在两个亲本 stock 字段中。

## Formal gate

formal 需要 --stock-audit、--source-access-report，两个候选必须在 audit 中为 identity_verified，并分别出现在 virgin_parent_stock 或 other_parent_stock；source-access report 中还必须有两个候选的 reachable_content_verified 记录。

pilot/conditional_pilot 可通过格式审计，但亲本链接、stock 身份、在线来源或上游表达缺口会产生 warning，并标记 blocked_for_formal。该审计不解析完整 Mendelian 分离、重组概率、插入方向、driver 的真实表达、RNAi 效率、背景纯合度或当前库存。

## 推荐命令

    python scripts/validate_integrated_cross_plan.py validation/public-data/top4-rnai-integrated-cross-plan.csv --stock-audit validation/public-data/shaw-clock-tool-stock-audit.csv --source-access-report validation/public-data/stock-source-access-validation.json --output validation/top4-rnai-integrated-cross-plan-validation.json

formal_status=conditional_pilot_only 只能支持信息获取或预实验；formal_gate_passed_external_checks_pending 也不等于生物学因果已证明。
