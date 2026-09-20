# Experimental metadata gate

在电生理、成像、RNA-seq 或行为数据进入节律/药理分析前，先把原始测量的层级和关键协变量结构化。`scripts/validate_experiment_metadata.py` 按 `exploratory` 或 `formal` 阶段检查同一份 sample sheet。

## 基础字段

`species`, `genotype`, `sex`, `age_days`, `temperature_C`, `lighting`, `ZT_or_CT`, `experimental_unit`, `biological_replicate_id`, `batch_id`。

## assay-specific 字段

- `ephys`：`preparation`, `cell_type`, `recording_id`, `technical_replicate_id`。
- `imaging`：`preparation`, `cell_type`, `roi_id`, `technical_replicate_id`。
- `expression`：`preparation`, `cell_type`, `library_id`, `technical_replicate_id`。
- `behavior`：`cage_id`（可作为随机/批次因素）。

`experimental_unit` 必须明确；同一只 fly 的多个 cell/ROI/trace 不能直接当作独立动物。`unknown` 可用于探索性 QC，但正式阶段会阻断高影响缺失项。所有输入和派生输出应记录文件大小与 SHA-256。
