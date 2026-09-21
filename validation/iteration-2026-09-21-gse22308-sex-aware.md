# 迭代验证：GEO sex/gender 上下文保留

日期：2026-09-21
数据集：GSE22308（NCBI GEO）
目的：验证 sex-aware 表达汇总能否保留公开 GEO 样本上下文，并在真实数据上重跑可复现流程。

## 发现与修复

GSE22308 的 `characteristics_json` 包含 `gender`：`yw` 样本标注为 `male and female`，`per01` 样本标注为 `male`。旧版提取器没有把该字段带入样本表或汇总分组键。当前数据的 cell-type × background × time 组内性别标签一致，因此此前汇总均值未发生混合；但输出丢失了重要来源信息，且若将来出现同组标签差异，就会发生不透明合并。

提取器现在将 `sex` 或 `gender` 统一保留为 `sex`，缺失时标为 `unknown`，并将其加入样本长表、描述性汇总与分组键。来源值按原样保留；`male and female` 只表示 GEO 的混合来源注释，不被拆成独立性别重复。GEO 工作流文档同步说明了该边界。

## 真实数据前向验证

NCBI GEO 原始 series matrix：`GSE22308_series_matrix.txt.gz`，SHA-256 `ad40dc0c4ce2338a241c09d3cc116ae78484bbf3f37fe69474c82d36e5cc27f7`。结构解析得到 24/24 个注释与表达样本对齐、18,952 个 probe/feature、0 个重复 ID、0 个非数值。15 个候选通道基因生成 360 条 sample-level 长表记录及 150 条分层汇总行；`large PDF/yw` 保留 `male and female`，`large PDF/per01` 保留 `male`。

节律流程得到 60 个 gene × cell type × background 组：15 组拥有四个 ZT 时间点，45 组只有两个时间点而被判为 `insufficient_or_invalid_time_series`。探索性推断中，15 个可检验组没有任何 BH 校正后 `q < 0.05`（最低 `q = 0.08991`，候选 `sei`）。分析单位是 pooled cell sample；数据在 LD 条件下采集，因此不能区分内源性 circadian 变化与光驱动效应。表达节律不等同于离子电流、膜电位或因果功能证据。

## 验证结果

- 聚焦提取器测试：5/5 通过，包括合成 `sex`/`gender` 别名和真实 GSE22308 性别注释测试。
- 全套单元测试：308 项通过。
- GSE17803 stage-context manifest：7 个文件、2 个 run 校验通过；隔离重放 2 个 run、4 个输出哈希通过。
- GSE22308 provenance manifest：16 个文件、8 个 run 校验通过；隔离重放 8 个 run、11 个输出哈希通过，新增 channel-regulator 提取与节律步骤。
- 本轮 blind forward manifest：9 个文件、4 个 run 校验通过；隔离重放 4 个 run、6 个输出哈希通过。
- `skill-creator` 的 `quick_validate.py` 因当前 bundled Python 缺少 `PyYAML` 无法启动；手动确认 `SKILL.md` frontmatter 包含 `name`/`description` 且分隔边界闭合。该手工检查不等价于完整 YAML parser 校验。

## 证据边界

这是 GEO 表达数据的数据工程与探索性统计回归，不证明候选离子通道在目标神经元中造成膜电位节律，也不能支持性别效应比较。正式推断仍需明确 pooled-sample 的构成、批次/温度等元数据，并用适配实验设计的 mixed model 验证。

来源：[NCBI GEO GSE22308](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE22308)。
