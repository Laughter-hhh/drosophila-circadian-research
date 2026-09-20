# Information-gain / pilot-plan schema

信息获取实验与正式因果实验分开保存。每一行必须回答：“当前哪一个事实缺失？这个最小实验如何获得它？在什么条件下停止或升级？”

## 必需字段

`plan_id`, `candidate`, `missing_fact`, `causal_link`, `target_neuron`, `stage`, `perturbation`, `reagent_identifier`, `reagent_identity_status`, `stock_identifier`, `stock_identity_status`, `readout`, `experimental_unit`, `minimum_n`, `sample_size_basis`, `positive_control`, `negative_control`, `developmental_boundary`, `go_no_go_rule`, `source_status`。

## 关键约束

- `stage` 使用 `information_gain_pilot`、`conditional_pilot` 或 `formal_experiment`。
- `perturbation` 使用 `observation_only`、`RNAi`、`pharmacology`、`temperature_activation`、`optogenetics` 或 `other`。
- `reagent_identity_status` 与 `stock_identity_status` 使用 `verified`、`pending_audit`、`not_applicable` 或 `unknown`。
- pharmacology/RNAi 方案若身份仍为 `pending_audit`，只能是 pilot，并且 identifier 必须明确写 `not_yet_selected`、`pending_*_audit` 或 `to_be_audited`；不得凭记忆猜药物、浓度或 stock 编号。
- `formal_experiment` 必须具备 verified reagent/stock（或明确 `not_applicable`）、成人期/发育边界、最小样本量依据和 go/no-go 规则。
- `minimum_n` 是该 pilot/formal 设计的最小 biological units，不得把 cell、ROI 或 technical replicate 当作动物数。
- 通过校验只表示方案字段自洽，不表示药物选择性、stock genotype、driver 表达或因果链已经被实验验证。

运行 `scripts/validate_information_gain_pilot.py`。输出状态仍区分 `planning`、`executed`、`verified` 和 `blocked`。
