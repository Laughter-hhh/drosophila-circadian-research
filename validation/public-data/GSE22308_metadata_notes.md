# GSE22308 真实数据 dry-run

来源：NCBI GEO accession `GSE22308`，标题为 *Circadian expression profiling of purified clock neurons in adult Drosophila*。本地 CSV 是从 GEO series matrix 的公开样本注释整理出的审计表，不是原始表达矩阵。

已核对字段：

- 物种：`Drosophila melanogaster`；
- 样本类型：`ELAV`、large PDF（对应 l-LNv 富集群）和 small PDF（对应 s-LNv 富集群）；
- 时间：`ZT0`、`ZT6`、`ZT12`、`ZT18`；
- 平台：`GPL1322`；
- 样本编号：`GSM555213`–`GSM555236`；
- 重复：样本标题标注 biological replicate；
- 研究设计：GFP 标记细胞经手工分选，约来自 50 个 adult brains 的 pooled cell sample。

未在该公开 sample annotation 中可靠获得的字段：具体 temperature、每个 pooled sample 中单只 fly 的身份和独立 fly-level replicate。它们被保留为 `unknown`，不能用于声称单 fly 层面的效应。

该 dry-run 的用途是验证元数据映射、时间字段、层级单位和证据边界；没有把表达数值分析结果写入本 skill，也没有把该数据集当作 s-LNv 膜电位或离子通道功能的直接证据。
