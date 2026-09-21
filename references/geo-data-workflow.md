# GEO 系列矩阵 dry-run 工作流

## 解析顺序

1. 保存 accession、下载日期、原始 URL 和文件哈希；
2. 先解析 `!Series_*` 和 `!Sample_*` 注释；
3. 检查 sample accession 顺序是否与表达矩阵列顺序一致；
4. 统计探针/feature 行数、重复 ID、非数值和缺失值；
5. 再核对平台 probe annotation、参考基因组/转录本版本和归一化方法；
6. 只有 annotation 和 biological replicate 层级都明确时，才进入表达差异或节律分析。

表达汇总必须保留会改变生物学解释的样本上下文。提取器至少保留 `developmental_stage`、`background` 和 `sex`（兼容 GEO characteristics 中的 `sex`/`gender` 键），并按这些字段分层；相同 cell-type label 的 larval 与 adult samples 不得合并。性别标签按来源元数据原样保留（例如 `male and female` 是混合来源注释，不能据此拆成性别重复）。其他已记录的 genotype、treatment、lighting 或 collection context 也应在分析前分层或显式建模。缺失字段写 `unknown`，不能用 sample title 的相似性推断补齐。

## 重要边界

GEO series matrix 中的 `ID_REF` 通常是 probe 或 feature ID，不一定是 gene symbol。不能把 probe ID 直接当作离子通道基因，也不能把“某个细胞群的表达数据”写成该细胞的电生理或膜电位证据。

若公开资料只提供 pooled sample、未提供 fly-level replicate、temperature 或批次，报告这些缺口；可以做结构性 dry-run 和探索性描述，但不能伪造样本量或正式机制结论。

## 解析器输出

`parse_geo_series_matrix.py` 输出：

- `summary.json`：数据维度、样本对齐、重复 ID、非数值、注释字段和输入文件 SHA-256；
- 可选的 `metadata.csv`：每个 sample 的 accession、标题、来源和结构化 characteristics；
- 错误或未决字段不会被静默填补；样本列错位会输出 `blocked_geo_parse` 并以非零退出码结束。

对已下载文件可用 `--expected-sha256 <64位摘要>` 核对精确文件版本；若不提供预期摘要，报告仍会记录观测到的 SHA-256，但标记为 `hash_recorded_not_verified`。

## 直接表达节律入口

进入 cosinor 前，长表必须对 gene_symbol × cell_type × background × developmental_stage × sex × sample_id 唯一；每个分组中的 sample ID 只对应一个时间点。analyze_expression_rhythm.py 与 analyze_cosinor_inference.py 按 gene、cell type、background、developmental stage 和 sex 分组；缺失 stage/sex 标记为 unknown，不会与已知标签混合。若表达表与 metadata 同时提供 stage/sex，则标签必须一致；比较时忽略大小写并将空格与下划线视作等价，但输出保留来源原值，不一致时阻断。一个样本有多个 microarray probes 或 RNA-seq transcript/isoform 行时，不得把 feature 行当作重复观测；应预先规定并说明 gene-level aggregation，或将各 transcript 作为独立特征分析。analyze_expression_rhythm.py 会阻断重复或空白 sample ID，不会替用户猜测求和、平均或取中位数。可用 audit_esat_candidate_sample_keys.py 对 ESAT transcript-level GEO 文件先做结构性审计；该审计不归一化表达量，也不检验节律。

如果仅需对已整理的表达长表做 descriptive fixed-period cosinor，运行 `scripts/analyze_expression_rhythm.py` 时必须显式提供 `--time-system ZT|CT`。脚本会核对每个 `time` token 的前缀；`CT6` 不会被静默重标为 `ZT6`。该入口只适合探索性描述，正式推断应使用 `scripts/analyze_cosinor_inference.py` 并提供 metadata 或明确的 experimental unit。

## GEO 样本列映射

Supplementary processed matrix 常用 BAM 前缀或自定义标签作为列名，不一定与 GEO sample title 相同。先建立显式 `matrix_path`, `matrix_column`, `matrix_alias`, `gsm_accession`, `timecourse_id` 表，再用 `scripts/audit_geo_sample_map.py` 对照 family SOFT：所有矩阵列必须恰好映射一次，GSM title alias、GEO `type`/source name、ZT/CT 和完整 timecourse 时间网格必须一致。若样本无法唯一连接，停止节律分析并保留缺口，不要仅凭列的顺序或相邻编号补时间。

该审计输出的是 GEO sample/library 元数据。多个神经元 pool 或细胞数不能替代个体 fly replication；timecourse 标签用于保留独立采集序列，不证明具体的实验批次或个体重复结构。

## 对照作者发表的 cycling-transcript 表

若问题只是“某个候选基因是否出现在已发表时钟神经元 cycler 名单”，读取 `references/published-cycle-table-workflow.md` 并运行 `scripts/audit_published_cycle_candidates.py`。这条路径精确核对 Abruzzi et al. (2017) S3 中的 symbol 和 HC/LC call，不重算表达节律；空匹配不得解释成未表达或无节律。若要重做统计，应另行核对 GEO 原始/processed 表、采样时间、transcript-to-gene 规则和 biological replicate，再进入对应分析 gate。
