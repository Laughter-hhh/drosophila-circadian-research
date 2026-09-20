# 功效依据与样本量 gate

正式实验不能只写一句“按预实验估计样本量”。使用 `scripts/validate_power_basis.py` 保存一份独立的 JSON 报告，并将它传给 `scripts/validate_experiment_plan.py --power-report`。

## 报告字段

每条记录对应一个 `plan_id`，至少声明：

- `independent_biological_unit`：真正独立的单位（通常是 `fly`、`brain` 或按设计汇总后的单位），不能把同一 fly 的多个 cell/ROI 当成独立动物；
- `effect_size`、`effect_size_low`、`effect_size_high` 与 `effect_size_metric`；预实验效应量应给敏感性区间；
- `alpha`、`target_power`、`comparison_count`、`multiplicity_method`；
- `cluster_structure`：写明 cell/brain/fly/day 的嵌套与阻塞；
- `basis_status` 与 `basis_source`：区分 pilot、literature、simulation、feasibility-only 和 not-available；
- `n_per_group` 与 `minimum_n_total`，均按 independent biological unit 计数；
- `calculation_method`。当前内置可计算方法是 `normal_approximation_two_group_equal_n`，要求 Cohen’s d。

内置方法会用最保守的 `effect_size_low` 计算两个等量组的近似样本量，并检查声明的 n 是否足够。它是透明的 planning approximation，不是 achieved power，也不替代 mixed-effects/cosinor/重复测量设计的 simulation。嵌套、cosinor 和重复测量设计必须使用 `nested_or_cosinor_external` 或 `other_external`，并提供 `external_simulation`、`externally_reviewed_power` 或 `design_specific_simulation` 方法；脚本不会把它们静默降级成独立两组公式。

## 推荐运行

```powershell
python scripts/validate_power_basis.py validation/public-data/synthetic-power-basis.json --output validation/power-basis-validation.json
python scripts/validate_experiment_plan.py plan.csv --power-report validation/power-basis-validation.json --output validation/plan-validation.json
```

`verified_power_basis_report` 只表示假设、计算和生物学单位声明通过结构化检查；不表示药物选择性、样本质量、因果关系或实际功效已经验证。没有 power report 时，含 `formal_experiment` 的实验蓝图会被阻断；pilot 可以保留 `feasibility_only`，但必须明确它不能支持 confirmatory claim。
