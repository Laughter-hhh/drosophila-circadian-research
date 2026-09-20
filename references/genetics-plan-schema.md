# 遗传杂交计划的机器可读审计

`validate_cross_plan.py` 用于在订购或建瓶前检查一行 cross plan 是否包含亲本、F1、balancer/selection、正反交、背景对照、温度/LD 和来源字段。

## 必需字段

`cross_id`, `purpose`, `virgin_parent_sex`, `virgin_parent_genotype`, `virgin_parent_stock`, `other_parent_sex`, `other_parent_genotype`, `other_parent_stock`, `f1_target_genotype`, `balancer_or_selection`, `reciprocal_cross`, `background_control`, `temperature_C`, `LD_schedule`, `timeline_days`, `stock_source_urls`。

## 审计规则

- `virgin_parent_sex` 必须标为 female；另一亲本可为 female 或 male。
- `NA`、`N/A`、`UNKNOWN` 和 `NOT_REPORTED` 在必需文本字段中视为缺失。
- `temperature_C` 与 `timeline_days` 必须为正数。
- 每行必须有可追溯的 stock 来源 URL；脚本只检查是否出现 FlyBase、BDSC 或 VDRC 等入口，不验证页面内容。
- 通过审计只表示格式和字段完整，不表示 stock 身份、染色体位置、driver 表达范围、遗传背景或当前库存已经核实。

正式实验仍需联网复核 FlyBase、BDSC、VDRC/NIG-Fly 和原始论文，并把页面访问日期、完整 genotype、balancer、插入位点、背景和风险写入任务合同。
