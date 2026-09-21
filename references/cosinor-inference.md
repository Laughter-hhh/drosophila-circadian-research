# 探索性 cosinor inference

`analyze_cosinor_inference.py` 在固定 24 h 周期下提供可复现的振幅置换检验、subject-level row bootstrap 和 Benjamini–Hochberg q-value。它不是论文级 mixed model，也不能替代预注册的 biological-unit-aware 分析。

## 时间基准与输入独立性

运行必须显式提供 `--time-system ZT` 或 `--time-system CT`。带有 `ZT`/`CT` 标签的输入和 metadata 必须与该声明一致；例如 `CT6` 不会被当作 `ZT6`。直接 numeric `time_hours` 也必须提供该声明，因为它决定 phase 的解释参照。

正式运行推断前必须显式提供 `--metadata` 或 `--experimental-unit`。只有 `sample_id` 不足以证明独立性；GEO 数据应优先用包含 `experimental_unit` 和 `biological_replicate_id` 的 sample sheet。metadata 存在时，脚本会核对 sample ID、ZT/CT 时间，并优先使用 `biological_replicate_id` 作为重采样单位。

每个 subject/biological replicate 默认只能有一行。发现重复 ID 时，脚本返回 `blocked_repeated_subjects`，要求改用预先定义的 hierarchical/mixed model，避免把技术重复当作独立动物。`pooled_cell_sample` 允许做探索性 sample-level 分析，但结果明确不是 animal-level effect estimate。

## GEO expression grouping

表达输入按 gene_symbol × cell_type × background × developmental_stage × sex 分组；缺失 stage/sex 以 unknown 独立分组，避免与已知标签合并。metadata 可补充表达表中缺失的 stage/sex；若两者都提供，标签必须匹配（比较时忽略大小写并将下划线视为空格），否则阻断。输出仍保留样本表的原始标签。

## 输出解释

- `p_amplitude_permutation`：将 time label 全局打乱后的经验尾部概率；是探索性 QC，不是正式推断。
- `bootstrap_*_ci95`：按 biological replicate/sample 重采样得到的描述性 95% percentile 区间。
- `q_amplitude_bh`：在本次运行的可检验 group 中进行 Benjamini–Hochberg 校正。
- `blocked_time_system_unspecified`、`blocked_experimental_unit_unspecified`、`insufficient_or_invalid_time_series` 和 `blocked_repeated_subjects` 都表示不能作节律结论。
- 顶层 `analysis_status=executed_exploratory` 与 `scientific_status=exploratory_not_verified` 不等同于生物学验证；结果必须保留 `time_system`、`seed`、置换次数、bootstrap 次数、metadata 文件、输入文件和数据字典。

## 推荐命令

```powershell
python scripts/analyze_cosinor_inference.py validation/public-data/GSE22308_channel_regulator_expression_samples.csv `
  --metadata validation/public-data/GSE22308_sample_metadata.csv `
  --time-system ZT --n-permutations 1000 --n-bootstrap 1000 --seed 20260906 `
  --output validation/public-data/GSE22308_channel_regulator_expression_inference.json
```

看到显著 p/q 值只能说明“该输入和该探索性模型下存在周期性信号”；不能单独证明目标时钟神经元中的通道表达节律，更不能证明膜电位或行为因果。
