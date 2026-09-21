---
name: drosophila-circadian-research
description: 面向果蝇神经生理与昼夜节律研究的证据检索、候选离子通道筛选、双语深度文献逐图解读、假说生成、实验设计、遗传杂交设计、数据分析和可复现作图。只要任务涉及果蝇、生物钟、时钟神经元、电生理或离子通道就使用本 skill，尤其适用于 Drosophila melanogaster 的 s-LNv、l-LNv、LNd、DN，分子节律—离子通道—膜电位或神经活动—行为节律，以及外界神经输入调控这些环节。
---

# 果蝇昼夜节律研究

## 总体目标

围绕以下工作模型组织研究，但不要把模型当作事实：

`分子节律 → 离子通道的表达/定位/功能节律 → 膜电位与神经活动节律 → 行为节律`

同时检验：`其他神经元的电/突触输入 → 离子通道或膜电位节律`。

默认使用中文回答，保留 gene symbols、genotypes、技术术语和 Nature 格式参考文献的英文写法。默认研究对象为 `Drosophila melanogaster`；不得自行补全性别、日龄、温度、LD/DD、ZT/CT 等未给出的条件。

## 启动任务

1. 读取用户提供的文件、既有结论和项目状态。
2. 若项目目录存在 `research-state.md`，先读取它；若不存在且用户正在建立持续项目，复制 `assets/project-state-template.md` 为 `research-state.md`。
3. 用一段话复述当前问题、已知事实、目标 readout 与本轮决策点。
4. 列出会改变实验解释的缺失信息。仅询问无法通过文件、数据库或安全假设解决的高影响问题。
5. 对低风险缺失项继续工作，但显式写出假设；对高风险缺失项先设计信息获取实验，不要直接设计跨越多条未证实因果边的正式实验。

## 研究级任务门槛

涉及真实数据、正式实验或论文结论时，先读取 `references/research-task-contract.md` 和 `references/metadata-and-data-dictionary.md`，并建立任务合同。每项工作都必须区分：

- `planning`：只有方案或分析计划，没有运行结果；
- `executed`：已使用指定文件和代码运行，但尚未完成独立复核；
- `verified`：通过预先定义的 QC、重跑或独立检查；
- `blocked`：缺少会改变结论的输入，或工具/数据不可用。

没有实际输入文件时，只能交付方法、模拟示例或信息获取实验；不得把预期输出写成已观察结果。公开数据任务还必须保留 accession、来源 URL、输入/输出文件哈希、脚本版本、供人阅读的命令、结构化 `command_argv` 和分析上下文；读取 `references/public-dataset-manifest.md`，先运行 `scripts/validate_public_dataset_manifest.py`。若分析被标为 `executed` 或 `verified`，还必须运行 `scripts/replay_public_dataset_manifest.py` 在隔离镜像中重放并逐项比对 output hash。不要从 benchmark 的参考答案、README 预期行为或文件命名反推真实生物学结论。

正式实验或正式分析前，必须明确真正独立的 `independent_biological_unit`（fly、brain 或按设计汇总后的单位）、主要 readout、样本量依据、排除标准、批次和时间条件。细胞数、ROI、技术重复数和动物数不得混写。正式实验必须用 `scripts/validate_power_basis.py` 保存 effect-size 敏感性区间、alpha、target power、比较数量、嵌套结构和 minimum n，并将报告传给实验计划 gate；复杂 nested/cosinor 设计必须使用外部审阅或 design-specific simulation。统计结果至少报告效应量及不确定性，不只报告 p 值。

## 选择工作流

- 对 ESAT 等 transcript-level GEO 处理矩阵审计候选通道的重复样本键（不做表达或节律推断）：运行 scripts/audit_esat_candidate_sample_keys.py；进入基因级 rhythm fit 前必须先处理重复的 gene × sample_id，不得把 isoform/probe 行当作生物学重复。
- 文献检索、综述或事实核查：读取 `references/evidence-search.md`。
- 深度文献解读、零基础教学、双语输出或逐 Figure/子图解释：读取 `references/deep-literature-reading.md`，并按需再读取 `references/evidence-search.md`。
- 筛选或排序离子通道：同时读取 `references/evidence-search.md` 和 `references/candidate-ranking.md`。
- 提出假说或设计实验：读取 `references/experiment-design.md`；涉及候选排序时再读取 `references/candidate-ranking.md`。
- 将 channel screen、channel rhythm、external neural input 和 behavior link 组织成可审计的分阶段实验蓝图：读取 `references/experiment-plan-schema.md` 和 `references/power-basis-schema.md`，运行 `scripts/validate_power_basis.py`，再运行 `scripts/validate_experiment_plan.py --power-report ...`。
- 设计果蝇遗传杂交或查 stock：读取 `references/genetics-and-stocks.md`，并联网核查当前记录。
- 编写遗传杂交计划或在订购前做字段审计：读取 `references/genetics-plan-schema.md`，运行 `scripts/validate_cross_plan.py`。
- 审计 FlyBase/BDSC/VDRC stock 身份、完整 genotype 与背景后再进入 formal cross：读取 `references/stock-audit-schema.md`，运行 `scripts/validate_stock_audit.py`。
- 在报告 stock、药物或论文来源前核对 URL 可达性与页面 identifier 是否实际出现：读取 `references/online-source-audit.md`，运行 `scripts/check_source_access.py`；`conditional_source_access` 只能作为待人工联网核对的 traceability，不得升级为 `identity_verified` 或直接证据。
- 将 stock 审计结果接入 formal 遗传设计、检查 driver 表达、成人期限制、发育控制和背景匹配：读取 `references/genetic-stage-gate.md`，运行 `scripts/validate_genetic_stage_gate.py --stock-audit ...`；`pilot`/`conditional_pilot` 的 warning 不得写成 formal 因果证据。
- 将亲本 genotype/F1/balancer 字段与 stock-to-cross gate 合并，并检查 driver/effector 是否真的出现在亲本 stock 中：读取 `references/integrated-cross-plan.md`，运行 `scripts/validate_integrated_cross_plan.py --stock-audit ...`。
- 从 primary paper 抽取 driver/effector、温度、LD/DD、实验单位和 n：读取 `references/primary-genetics-schema.md`，运行 `scripts/validate_primary_genetics.py`。
- 分析表格、图像或电生理数据并作图：读取 `references/data-and-figures.md`。
- 处理 GEO 表达矩阵、探针注释、候选基因汇总或探索性表达节律：读取 `references/geo-data-workflow.md` 和 `references/public-dataset-manifest.md`，先运行 `scripts/validate_public_dataset_manifest.py`；对需要标记为 `executed`/`verified` 的既有分析，再运行 `scripts/replay_public_dataset_manifest.py`，随后才按需运行 `scripts/parse_geo_series_matrix.py`、`scripts/extract_gene_expression.py` 和 `scripts/analyze_expression_rhythm.py`。
- 将 GEO processed matrix 的列与 GEO family SOFT 样本记录连接：先提供显式 `matrix_path × matrix_column × matrix_alias × GSM × timecourse_id` 映射表，再运行 `scripts/audit_geo_sample_map.py`；脚本核对列完整性、GSM/title、cell type、ZT/CT 与每个独立 timecourse 的采样覆盖，不从列名静默猜时间。输出 metadata 仍不能替代个体 fly、sex、age、genotype 或温度记录。
- 将候选通道符号与 Abruzzi et al. (2017) 的 GSE77451 S3 已发表 cycler 表核对：读取 `references/published-cycle-table-workflow.md`，运行 `scripts/audit_published_cycle_candidates.py`；按每张 worksheet 的表头解析 F24/JTK 列、精确匹配完整 gene symbol、保留 HC/LC 和重复行、对照论文与 supplement 的 HC 数量。未列出不等于无表达或无节律；将此 transcript evidence 与蛋白、膜电流、膜电位及因果证据分开，并运行 public-dataset manifest validator 与 isolated replay。
- 筛选时钟神经元候选通道的单细胞检出或查询 GSE157504 已发表节律：读取 `references/published-sc-clock-rhythm-audit.md`；运行 `scripts/audit_gse157504_candidate_detection.py` 匹配 raw counts 与细胞注释、运行 `scripts/extract_published_sc_clock_channel_rhythms.py` 提取作者高置信度节律表，再运行 public-dataset manifest validator 与 isolated replay。必须保留 DD 的 CT 时间系统、`LN_ITP` 混合类别、未匹配/未覆盖的 barcode 与 gene symbol，并将 raw UMI 检出解释限制为描述性转录证据。
- 将已验证的 GSE157504 转录检出/作者节律数据并列叠加到文献候选长名单，且不更改评分或电生理 gate：读取 `references/candidate-context-overlay.md`，先核实上游 manifest/replay，再运行 `scripts/build_candidate_evidence_context.py`；输出必须保留候选集差异、零 UMI/dropout、未评估候选、`LN_ITP` 模糊亚群、DN 子群范围及静态淘汰理由的人工复核标记。
- 将已验证的 GSE157504 候选 context 与 Abruzzi2017 S3 author cycler calls 合并成 score-neutral transcript sidecar：读取 `references/combined-transcript-candidate-context.md`，先重新验证双方 parent manifest/replay，再运行 `scripts/build_published_cycle_candidate_context.py`；保留 s-/l-LNv 混合组、LNd+第五个 PDF-negative s-LNv、DN1 subset 的范围，不将 HC/LC 或未列出结果升级为膜电流/膜电位因果证据，也不更改候选分数或电生理 gate。
- 处理公开果蝇行为数据、Ethoscope 元数据或体量很大的原始录像归档：读取 `references/public-behavior-metadata.md`，先运行 `scripts/audit_public_behavior_metadata.py`，再用 `references/public-dataset-manifest.md` 的 manifest gate 和 `scripts/replay_public_dataset_manifest.py` 做隔离重放；元数据审计通过不等于已经获得行为节律证据，缺少 genotype/sex/age/temperature/LD-DD、个体标识或 raw checksums 时必须保持 blocked。
- 对满足时间点要求的表达数据做探索性置换/bootstrap cosinor：读取 `references/cosinor-inference.md`，运行 `scripts/analyze_cosinor_inference.py`；必须提供 `--metadata` 或明确的 `--experimental-unit`，脚本会核对 sample/time、biological replicate 和重复观测，缺失或混用实验单位时阻断；不得把探索性 p/q 值当作论文级 mixed-model 结论。
- 对包含多个 cell/ROI/trace 的嵌套数据做 biological-unit 聚合与 cluster bootstrap：读取 `references/nested-cosinor.md`，运行 `scripts/analyze_nested_cosinor.py`；先按 `biological_replicate_id × time` 聚合，不得把下层观测当成独立动物，输出仍需标注为探索性且不替代 mixed-effects model。
- 准备 formal mixed-effects handoff：读取 `references/mixed-model-handoff.md`，运行 `scripts/prepare_mixed_model_input.py`；仅当 manifest 为 `ready_for_mixed_model` 时运行 `scripts/emit_mixed_model_templates.py`，并在有可用统计运行时后再拟合，缺失运行时必须标记 `blocked`。
- 检查 formal mixed-effects runtime：运行 `scripts/check_mixed_model_runtime.py`；该检查不安装依赖、不修改环境，只报告可用后端，所有拟合前仍需 ready manifest、收敛诊断和预先定义的 contrasts。
- 审计候选证据表的来源、目标细胞亚型、评分字段和淘汰理由：读取 `references/candidate-ranking.md`，先用同一份 `--search-log` 联合验证候选表，再用配对的 `--search-log`、`--readout-match` 和明确的 `--target-cell` 运行 `scripts/score_candidates.py`；评分/current 表缺 log 或候选声明与 log 不一致时 scorer 会 fail closed。仅 all-NA、非电生理 readout 的探索性上下文诊断允许无 log，且不得生成 Top。宽泛 `LNv` 不得自动等同于 s-/l-LNv，DN1p 也不得代表全部 DN。
- 建立或审计文献/数据库检索证据链：读取 `references/evidence-search-log-schema.md`，运行 `scripts/validate_evidence_search_log.py`；每条证据必须记录查询、数据库、日期、物种、目标细胞、assay、readout、证据标签、来源标识和纳入/排除决定，不能只保留不可回溯的 URL 串。
- 设计或审核信息增益预实验：读取 `references/information-gain-pilot-schema.md`，运行 `scripts/validate_information_gain_pilot.py`；必须写出缺失事实、最小 readout、experimental unit、对照、成人期边界和 go/no-go 规则，未核实的药物或 stock 只能标为待审计。
- 审核电生理、成像、表达或行为数据的实验元数据：读取 `references/experimental-metadata-gate.md`，运行 `scripts/validate_experiment_metadata.py --assay ... --stage ...`；在节律或药理拟合前先核对 cell identity、sex、age、temperature、ZT/CT、batch、biological replicate 和技术重复层级。
- 审核原始 ephys/imaging 文件、QC 指标和派生结果溯源：读取 `references/raw-qc-provenance-schema.md`，运行 `scripts/validate_raw_qc_provenance.py --assay ...`；在解释 channel blocker、膜电位或成像效应前核对 raw-file 哈希、metadata linkage、seal/access resistance、holding current、漂移、ROI/image QC 和 exclusion reason。
- 从标准化 trace CSV 派生可追溯的 ephys/imaging measurement：读取 `references/trace-derivation.md`，运行 `scripts/derive_trace_measurements.py`；先通过 metadata/raw-QC gate，只转换 `qc_status=pass` 记录，按 ZT/CT 从 metadata 锚定时间，并将结果接入 pre-analysis bundle；不自行解码未核实的 ABF/TIFF 二进制格式。
- 需要将已附 raw ephys trace 的 metadata→raw-QC→measurement→exploratory cosinor 链标为可重放：读取 `references/ephys-trace-replay-manifest.md`，以仓库相对 raw path 建立 manifest，先运行 `scripts/validate_ephys_trace_replay_manifest.py`，再运行 `scripts/replay_ephys_trace_manifest.py`。只有 `verified_ephys_trace_replay` 可证明当前输入、参数和代码的逐项 output hash 重现；它仍不代表 cell identity、节律或因果结论。
- 将 metadata、raw-QC manifest 与派生测量作为一个 pre-analysis bundle 审核：读取 `references/preanalysis-bundle-gate.md`，运行 `scripts/validate_preanalysis_bundle.py`；要求 pass raw record 与派生行一一可追溯，阻断 orphan/non-pass measurements 后再进入 cosinor 或药理效应分析。
- 对已通过 bundle gate 的 ephys/imaging 派生时序做探索性 cosinor：读取 `references/bundle-cosinor-analysis.md`，运行 `scripts/analyze_preanalysis_cosinor.py`；先在 `biological_replicate_id × time_hours` 内平均技术重复，报告 longitudinal/cross-sectional 设计与时间系统警告；formal 阶段必须阻断并转交 biological-unit-aware mixed-effects backend。
- 对已通过 bundle gate 且含多个 subunit/cell/ROI 的嵌套时序做 exploratory cluster permutation/bootstrap：读取 `references/nested-bundle-inference.md`，运行 `scripts/analyze_preanalysis_nested_cosinor.py`；先选择单一 `metric_name` 与一致 `value_unit`，按 `biological_replicate_id × time_hours` 聚合并按 biological unit 重采样；formal 阶段必须转交 mixed-effects backend。
- 创建或执行科研分析任务、整理输入输出和验收标准：读取 `references/research-task-contract.md`。
- 检查实验元数据、数据字典或 biological replicate：读取 `references/metadata-and-data-dictionary.md`。
- 设计或质控全细胞膜片钳、膜电位或离子通道电流实验：读取 `references/electrophysiology-qc.md`。
- 编写急性药理学阻断方案或在正式膜片钳前做浓度/选择性字段审计：读取 `references/pharmacology-plan-schema.md`，运行 `scripts/validate_pharmacology_plan.py`。
- 设计或质控钙成像、免疫染色、RNA-seq 或 single-cell 分析：读取 `references/imaging-and-sequencing-qc.md`。
- 需要可复现代码、运行日志、数据溯源或论文级产物：读取 `references/reproducibility-and-provenance.md` 和 `references/manuscript-claims.md`。
- 一项任务跨越多个工作流时，只读取直接相关的参考文件。

## 证据与推理纪律

候选排序工作流的详细边界见 `references/candidate-ranking.md`：真实候选必须以已验证 search log、明确的 `--readout-match` 和逐个 `--target-cell` 运行来源级评分；仅用候选表摘要的结果只能作为探索性长名单，不得报告为来源级 directness shortlist。

对每个关键陈述标注以下之一：

- **结论｜直接证据**：目标物种、目标神经元或紧邻 readout 的实验直接支持。
- **结论｜间接证据**：果蝇其他细胞、其他时间条件或代理 readout 支持。
- **推断**：由多项证据推导出的可检验解释；同时给出替代解释。
- **无证据/未检索到**：当前检索未发现支持；不要写成“已证明不存在”。

把预印本和非果蝇研究单独标注，不得让其替代果蝇直接证据。不使用学位论文，除非用户主动上传。任何文献、stock 编号、genotype、药物选择性、driver 表达范围或数据库状态都必须联网核查后再报告；无法核查时明确写“未核实”，不得凭记忆补齐。

缩写、分组名和文件字段也属于需要核查的事实。若原始任务或数据字典没有定义 `TAR`、`CTRL` 等标签，写“标签含义未核实”，不要自行扩展全称。把 benchmark 的硬性格式要求与真实研究中的方法学建议分开标注，不能因为某道题要求某个检验或参数，就把它写成普遍生物学规则。

## 控制因果链深度

把一条直接可检验关系视为一级逻辑，例如 `channel X activity → s-LNv resting membrane potential`。

当上游事实缺失时：

1. 指出缺失的关键事实。
2. 优先设计获得该事实的实验或分析。
3. 最多跨一级提出探索性预实验。
4. 不把跨越两条或更多未证实关系的方案包装成正式验证实验。

## 形成候选与实验方案

优先处理 leak channels 与 gated channels；再考虑其他成孔通道、gap junctions、pumps/transporters/exchangers 和通道调控蛋白。先输出可追溯的完整长名单，再给 Top 5 或 Top 10 深入分析。显示评分、证据、未知项和淘汰或降级理由，不使用只有总分而没有来源的黑箱排名。

默认策略：

- 遗传筛选优先 RNAi，并优先规避发育效应；阳性结果要求独立 reagent 或正交方法复核。
- 全细胞膜片钳的急性机制筛选优先考虑 pharmacological blockade，但必须核查药物选择性、浓度依据、溶剂、起效或洗脱和 off-target 风险。
- 允许快速预实验，但始终与 confirmatory design 分开标注；预实验不得被描述为正式因果证明。
- 正式设计默认包含生物学重复、实验单位、样本量依据、随机化、盲法、排除标准、阳性或阴性对照、批次效应、性别、日龄和 circadian time matching。
- 需要执行分析时优先运行仓库内的可复现脚本，保存配置、软件版本、输入清单、QC 和中间结果；只给出代码片段而不运行不能标记为 `executed`。
- 候选排序必须公开评分维度、权重、缺失证据和敏感性分析；不得用不可追溯的总分替代证据。

## 输出结构

根据任务裁剪，避免机械输出无关章节。完整研究任务优先使用：

1. **当前问题与边界**
2. **已知、推断与缺口**
3. **证据表或候选长名单**
4. **Top 候选与排序理由**
5. **关键信息获取实验**
6. **探索性预实验**
7. **满足 stage gate 后的正式实验蓝图**
8. **遗传杂交与 controls**
9. **分析、统计与可复现作图计划**
10. **风险、替代解释与 go/no-go 标准**
11. **Nature 格式参考文献、直接链接、检索日期与检索日志**
12. **建议写入项目状态的更新**

真实数据任务还应交付：任务合同、数据字典、原始文件清单、QC 报告、分析配置、运行日志、代码版本和可重跑命令。若这些产物尚未生成，明确标为“尚未生成”。

若用户只问一个窄问题，直接回答该问题并保留必要的证据标签、来源和不确定性。

## 维护项目状态

把以下内容作为持续记录：已验证事实、待检验假说、候选评分、现有或拟购 stocks、实验结果、失败与排除、数据集、分析版本、决策和下一步。不要把本轮推断升级为已验证事实。修改 `research-state.md` 前显示拟写入的关键变化；得到用户确认或在其明确要求维护记录时再写入。

每次结束时给出最小可执行下一步，并指出完成它后会解锁哪一级正式设计。

## P0 自检

交付前确认：

1. 所有缩写、标签、stock、药物和数据库状态都有来源或明确标为未核实；
2. 所有结果都带有 `planning`、`executed` 或 `verified` 状态；
3. 正式方案具备独立 biological unit、通过 gate 的功效或样本量依据、QC、排除标准和替代解释；
4. 代码和配置可以在同一输入上重跑，并产生可比较的结果；
5. 结论没有超出目标物种、目标细胞和实际 readout 的证据范围。
