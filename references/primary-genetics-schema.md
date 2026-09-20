# primary-paper 构建级遗传条件记录

`validate_primary_genetics.py` 用于从原始论文提取 driver/effector、目标细胞、温度、LD/DD、实验单位和 n，同时把“论文报告的构建级 genotype”与“可订购 stock 的完整 genotype”分开。

## 必需字段

`paper_id`, `reported_genotype`, `driver`, `effector`, `cell_scope`, `temperature_C`, `LD_schedule`, `free_running_condition`, `experimental_unit`, `n`, `readout`, `source_url`, `evidence_level`, `genotype_completeness`, `notes`。

## 边界

- `construct-level only` 只能说明论文中报告了这些构建和实验条件，不能替代 FlyBase/BDSC/VDRC 的 stock identity audit。
- 论文中的 `n` 必须保留其 experimental unit（例如 individual fly），不能和细胞数或技术重复合并。
- `verified` 仅表示抽取字段完整且格式正确；不表示重现实验、driver 表达范围、背景匹配或行为/电生理效应已经验证。
