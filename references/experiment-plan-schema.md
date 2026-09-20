# 分阶段实验方案 schema

当任务同时涉及 channel screen、channel rhythm、external neural input 或 behavior link 时，使用 `scripts/validate_experiment_plan.py` 审计实验蓝图。正式方案还必须提供 `scripts/validate_power_basis.py` 生成的功效依据报告，并通过 `--power-report` 传入。它们不是实验结果分析器，不会证明因果。

## 必需内容

每行对应一个模块，必须明确：

- hypothesis、causal_link、target_neuron、species；
- stage：information_gain_pilot、conditional_pilot 或 formal_experiment；
- perturbation、time_basis（ZT/CT）、LD/DD、sex/age/temperature；
- experimental_unit、biological_unit_definition、minimum_n 和 sample_size_basis；
- primary_readout、secondary_readouts、controls、qc_metrics 和 analysis_plan；
- expected_result_matrix、alternative_explanations 和 go_no_go_rule；
- developmental_boundary、reagent_identity_status、stock_identity_status 和 source_status；
- formal 方案的 independent biological unit、effect-size 敏感性区间、alpha、target power、比较数量、嵌套结构和可追溯的功效依据。

## 特殊 gate

- channel_screen/channel_rhythm 至少要声明与 assay 相符的 QC（例如 seal、access、series、cell_health 或 ROI）。
- pharmacology/RNAi 必须声明 vehicle、driver-only/effector-only/background 等身份与背景控制。
- optogenetics 必须声明 light/sham 与 retinal control；temperature_activation 必须声明 temperature/sham control。
- formal_experiment 必须有 verified reagent/stock（或 not_applicable），不能把 unknown/pending_audit 当作正式因果证据。
- 任何 ZT0/CT0 等带数字的时间 token 都会被解析为合法 ZT/CT；混合时间系统仍应由数据分析 gate 另行阻断。
- formal_experiment 没有有效 power report、功效依据不是正式可用、独立 biological unit 与方案不一致或方案 minimum_n 小于保守敏感性样本量时，formal gate 阻断。
- 内置两组近似仅适用于明确的 Cohen’s d；nested/cosinor/repeated-measures 设计必须声明外部审阅或 design-specific simulation，不得把 cell/ROI 数量当作 fly n。

验证成功表示方案字段自洽且 stage gate 通过，不表示药物选择性、stock genotype、driver expression、统计功效或生物学结果已验证。


运行 `scripts/validate_power_basis.py` 的详细字段和限制见 `references/power-basis-schema.md`。



