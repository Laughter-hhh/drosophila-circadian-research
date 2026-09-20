# 嵌套数据的 biological-unit-aware cosinor

## 适用边界

当一只 fly 有多个 cell、ROI 或 trace，直接把所有行送入普通 cosinor 会把下层观测误当成独立 biological replicate。`scripts/analyze_nested_cosinor.py` 提供一个依赖轻量的探索性桥接：先在 `biological_replicate_id × time` 内平均 subunits，再以 biological replicate 为单位做固定 24 h cosinor、cluster bootstrap 和时间标签置换。

这不是 publication-grade mixed-effects model。它用于预实验、数据结构核查和模型开发；正式分析仍应根据实验设计预先指定 random intercept/slope、批次、性别、日龄、基因型和缺失处理。

## 输入字段

必需：

- `biological_replicate_id`：fly、brain 或其他预先定义的独立单位；
- `time_hours`，或可解析的 `time`/`ZT_or_CT`；
- `value`；
- `experimental_unit`，或命令行 `--experimental-unit`；
- 命令行 `--time-system ZT` 或 `--time-system CT`。

带 `ZT`/`CT` 的 token 必须与声明的时间系统一致；`CT6` 不会被当作 `ZT6`。直接 numeric `time_hours` 也必须声明时间系统，因为它决定 phase 的解释参照。

可选：`subunit_id`（也接受 `cell_id`/`roi_id`）、`gene_symbol`、`cell_type`、`background`。同一个 biological replicate 在同一时间的多个 subunit 会被聚合，但原始行数、聚合后的 unit×time 数和 subunit 数都会写入输出。

## 门槛与解释

- 缺少或混用 `experimental_unit` 时阻断；technical replicate 不能作为 biological unit。
- 每组至少需要 4 个 biological replicates、4 个聚合观测和 3 个时间点；细胞数不能替代 fly 数。
- 若每个 biological replicate 有多个时间点，置换在 unit 内打乱时间标签；若每个 unit 只有一个时间点，使用 global time-label shuffle 并在 warning 中标明。
- cluster bootstrap 重采样 biological replicate，而不是 cell/ROI。输出的 p/q 和区间仍是探索性结果，不是自动的 mixed-model 显著性。
- 未提供 `--time-system` 时，脚本在任何计算前返回 `blocked_time_system_unspecified`。

## 推荐命令

```powershell
python scripts/analyze_nested_cosinor.py validation/synthetic/nested_clock_data.csv `
  --time-system ZT --n-permutations 1000 --n-bootstrap 1000 --seed 20260906 `
  --output validation/synthetic/nested_clock_data_cosinor.json
```

报告时同时给出 `time_system`、`n_raw_observations`、`n_aggregated_biological_unit_time_means`、`n_biological_replicates`、`permutation_mode` 和 `inference_warning`。不得只报告细胞数或 p 值。

## 进入 formal mixed model 前的最小信息

1. 每个 cell/ROI 所属的 fly/brain ID；
2. 同一 biological unit 是否跨多个 ZT/CT 时间点；
3. batch、sex、age、genotype、temperature、LD/DD 和排除标准；
4. 主要 readout 与预先定义的效应量；
5. 缺失时间点、技术重复和离群值的处理规则。
