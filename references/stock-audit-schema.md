# FlyBase/BDSC/VDRC stock 身份审计

`validate_stock_audit.py` 用于在正式遗传杂交或订购前检查每个候选 stock 是否已经从“数据库摘要”推进到可执行身份记录。

## 必需字段

`candidate`, `flybase_id`, `flybase_url`, `stock_center`, `stock_number`, `full_genotype`, `insertion_chromosome`, `genetic_background`, `balancer_or_marker`, `availability_status`, `source_checked_date`, `source_url`, `verification_status`, `notes`。

## 审计规则

- `flybase_id` 可以是 FlyBase 的 gene、stock、insertion、construct、allele、balancer 或 aberration ID（例如 `FBgn`, `FBst`, `FBti`, `FBtp`, `FBal`, `FBba`, `FBab` 加数字）；不能把 gene ID 规则错误地套用于 stock/insertion report。
- `flybase_url` 必须是可解析的 FlyBase `/reports/<ID>` URL，且 `<ID>` 必须与 `flybase_id` 一致；这能拦截把 gene、stock 和 insertion 页面混用的追溯错误。
- `stock_number`、完整 genotype、插入染色体、遗传背景和 balancer/marker 是正式建瓶所需字段；缺少任何一项都不能标记为 `identity_verified`。
- 空值以及 `NA`、`N/A`、`unknown`、`not reported`、`not specified`、`none reported` 等占位文本都按缺失处理；如果某项确实不适用，应在 `notes` 中解释并保持 `partial`，而不是伪装成已核实身份。
- `availability_status` 和 `verification_status` 必须显式写出；`unknown` 或 `not_verified` 只能作为规划/信息缺口，不能直接进入 formal cross。

## 机器状态解释

`status=verified_stock_audit` 只表示表格结构和字段格式通过；它不等于正式杂交已准备好。重点看 `formal_status`：

- `blocked_identity_not_verified`：至少一个候选仍为 `partial`/`not_verified`；只能做 conditional pilot 或信息获取实验；
- `identity_gate_passed_external_checks_pending`：身份字段达到门槛，但当前库存、driver 表达、背景匹配和功能仍需外部核查；
- `blocked_by_validation_issues`：存在结构、ID、URL 或必需字段错误。

脚本不确认页面当前库存、染色体位置、driver 表达、插入方向、背景纯合度或 stock 是否真的符合目标构建；这些仍需人工逐条打开 FlyBase、BDSC/VDRC/NIG-Fly 与原始论文核对。
