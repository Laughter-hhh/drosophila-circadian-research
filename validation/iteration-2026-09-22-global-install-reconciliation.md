# 迭代 2026-09-22：全局安装一致性与真实数据前向验证

## 本轮结论

全局安装版的运行时 skill 已与当前仓库对齐，并通过当前安装中可发现的完整测试子集。此前记录的 scorer API 不匹配和旧测试夹具问题已修复。公开数据重放与真实候选打分也已验证。此结论不代表 316 项仓库测试都存在于全局安装，也不构成新的生物学发现。

## 失败诊断与安全同步

先在全局安装重跑旧测试：222 项中 15 项失败，主要原因是候选表与 evidence-search log 夹具仍使用旧 schema。同步已核实的旧测试/夹具后，测试暴露出全局 `score_candidates.py` 不接受 `--search-log`、`--readout-match` 和 `--target-cell`，而且旧 `SKILL.md` 与 `candidate-ranking.md` 没有路由到当前的来源级 readout/亚型 gate。旧 replay runner 的白名单也缺少当前已审核的 GSE77451 与候选证据脚本。

审阅了四份原先保留的全局差异文件：旧内容没有当前仓库尚未包含的专属段落或 scorer 能力，主要是版本落后。为可回滚，替换前把四份原文件保存在 `E:\skill\.skill-install-rollback-2026-09-22`，随后仅同步其当前仓库版本：

- `SKILL.md`
- `references/candidate-ranking.md`
- `scripts/score_candidates.py`
- `scripts/replay_public_dataset_manifest.py`

另同步了 5 个已确认过时的测试模块、4 个当前测试所需数据夹具；对后续替换的 2 个 scorer 测试和 1 个合成候选夹具也保留了回滚副本。未删除全局安装中的额外文件。

## 可复现验证

- 运行时包 SHA-256 审计（排除自动生成的 `__pycache__`）：仓库有 106 个 `SKILL.md`、`agents/`、`references/`、`scripts/`、`assets/` 运行时文件；全局安装 **106/106 完全相同**，无缺失或差异文件。全局 `SKILL.md` 中引用的 81 个路径全部存在。
- 仓库回归：**316 项通过**。
- 全局安装回归：发现 65 个测试模块，共 **234 项通过**。全局安装比仓库少 16 个测试模块，因此这是安装内可发现测试的通过结果，不等同于完整 316 项覆盖。
- 全局 GSE22308 manifest：`verified_public_dataset_manifest`，11 个文件、4 次分析运行、0 个 issue。隔离重放：`verified_public_dataset_replay`，4 次运行、6 个输出哈希匹配、0 个 issue。结果保存在：
  - `validation/public-data/global-install-GSE22308-manifest-validation-2026-09-22.json`
  - `validation/public-data/global-install-GSE22308-replay-2026-09-22.json`
- 全局版候选 scorer 用实际 `candidate-evidence-real.csv` 与已核查的 `candidate-evidence-search-log.csv`，针对 `membrane_potential_or_current`、`s-LNv` 完成端到端打分。输出 SHA-256 为 `FAF74A37DEC12154429EA5BE80700F5F0424E476D972F50A6115DBB1E7785682`，与仓库已验证文件 `candidate-scoring-source-log-guard-score-slnv.csv` 完全相同。`Shaw`、`Shal` 通过本 readout 的直接性与 shortlist gate；`na` 因目标细胞不匹配、`Irk1` 因缺少该电生理 readout 的来源级支持而未通过。该 gate 表示证据范围匹配，不等于证明因果。
- 仓库内的 GSE77451/Abruzzi 2017 S3 候选审计重跑：15 个候选、45 个“候选×细胞群”组合；6 个组合出现在作者发布的 cycler 表：`Shab` 在混合 LNv 为 HC、在 DN1 subset 为 LC；`Sh` 在 LNd+第五个 PDF-negative s-LNv 为 LC；`para` 在混合 LNv 为 LC；`cac` 在 LNd 组为 LC；`sei` 在混合 LNv 为 LC。其余 9 个候选未在这些 sheet 中精确匹配；这不表示未表达或无节律。manifest 验证 4 个文件/1 次运行、0 个 issue；隔离重放验证 2 个输出哈希、0 个 issue。
- 原文正文报告 LNv 有 249 个 HC cyclers，而 S3 表格解析为 252 个 unique HC symbols；本轮保留为未解决的来源差异，不自行校正。GSE77451 的 LNv 混合 s-/l-LNv，LNd 组包含一个 PDF-negative s-LNv，DN1 为 subset；这些 pooled transcript calls 不能说明具体亚型的膜电流、膜电位或因果作用。

GSE77451 来源：Abruzzi, K. C. et al. RNA-seq analysis of *Drosophila* clock and non-clock neurons reveals neuron-specific cycling and novel candidate neuropeptides. *PLoS Genet.* **13**, e1006613 (2017). https://doi.org/10.1371/journal.pgen.1006613. 数据入口：[NCBI GEO GSE77451](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE77451)；补充表 S3：https://doi.org/10.1371/journal.pgen.1006613.s003.

## 验证限制与下一步

`skill-creator` 的 `quick_validate.py` 未能运行：配置的 Python 没有 `PyYAML`，PATH 中的 `python` 是 Windows 应用商店占位符；本轮未安装依赖，也不把它报告为 skill 内容错误。仓库与全局单元测试仍然通过各自上述范围。

独立前向测试已完成 transcript-level 重建与描述性筛查（`executed`），但完整公开数据流水线尚未通过 manifest 验证及隔离重放，因此不标为 `verified`。36 个 pooled-neuron libraries 映射为每组 12 个、两个六时点课程；来源不能区分单只果蝇，也未提供性别、日龄、基因型和温度。LNv 混合 s-/l-LNv，LNd 组含第五个 PDF-negative s-LNv，DN1 仅是 DN 子集，故不可据此做特定亚型结论。

对 19 个候选保留 transcript 行，并以 sum、median、maximum 三种基因聚合方式作敏感性比较；输入未声明数值单位，也未补做归一化。每个候选×细胞组×timecourse 仅 6 个时间点，使用两课程重复性与两倍动态范围的描述性启发式，不是显著性检验。primary sum 下 57 个候选×细胞组组合中 14 个通过筛查；12 个组合在三种聚合规则下都通过。Irk1 在矩阵中以 Ir 标记，需要 synonym 映射；LNv 中未检出 Ork1、qsm、Ncc69 对应矩阵行不代表生物学缺失。以上 pooled processed transcript profiles 不支持内源性节律、单细胞亚型表达、膜电流/膜电位或因果结论。

本次暴露出真实使用缺口：manifest validator 要求至少一个 run，导致分析前无法通过纯计划态 manifest 校验；skill 自带 GEO extractor 不支持 ESAT transcript-ID/gene-symbol 矩阵格式；最终 manifest 只记录三个 cosinor 命令，没有纳入自定义矩阵适配及样本/键审计，且没有完成最终 manifest 验证或 replay。不得把 cosinor 子步骤成功误报为整条数据链已重放验证。独立测试生成的中间矩阵与脚本保留在隔离目录，未作为未经审阅的分析代码一并发布。

下一轮应先补上可审阅、可重放的 ESAT adapter 与其 manifest/replay 记录，并决定是否把尚缺的 16 个开发测试模块纳入全局安装包；测试模块缺失不影响当前 106 个运行时文件的一致性，但限制了全局安装的回归覆盖范围。
