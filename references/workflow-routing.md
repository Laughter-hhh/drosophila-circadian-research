# 专用工作流路由

仅在请求匹配相应分析类型时读取本文件的对应小节，不要把所有高级流程预载入每个果蝇/昼夜节律任务。主流程、科研边界和常见研究入口见 `SKILL.md`。

## 文献与候选证据

- 建立或审计文献/数据库检索证据链：读取 `references/evidence-search-log-schema.md`，运行 `scripts/validate_evidence_search_log.py`；每条证据记录查询、数据库、日期、物种、目标细胞、assay、readout、证据标签、来源标识及纳入/排除决定。
- 候选通道表需做来源级评分时：读取 `references/candidate-ranking.md`、`references/candidate-scoring.md`，用同一份已验证 `--search-log` 审核候选表，再以配对的 `--search-log`、`--readout-match` 和明确的 `--target-cell` 运行 `scripts/score_candidates.py`。候选声明与日志不一致时应 fail closed；仅 all-NA、非电生理 readout 的探索性上下文诊断允许无 log，且不得生成 Top。宽泛 `LNv` 不等于 s-/l-LNv，DN1p 不代表全部 DN。
- 将候选排序连接到目标细胞/特定 readout 时，遵循 candidate-ranking 的直接性 gate；不把证据不足的候选补成 Top。

## 实验设计、遗传与药理

- 将 channel screen、channel rhythm、external neural input 和 behavior link 组织成可审计的分阶段蓝图：读取 `references/experiment-plan-schema.md`、`references/power-basis-schema.md`，运行 `scripts/validate_power_basis.py`，再运行 `scripts/validate_experiment_plan.py --power-report ...`。
- 编写遗传杂交计划或订购前字段审计：读取 `references/genetics-plan-schema.md`，运行 `scripts/validate_cross_plan.py`。
- 审计 FlyBase/BDSC/VDRC stock 身份、完整 genotype 与背景：读取 `references/stock-audit-schema.md`，运行 `scripts/validate_stock_audit.py`；将审计结果接入 formal 设计时再读取 `references/genetic-stage-gate.md` 并运行 `scripts/validate_genetic_stage_gate.py --stock-audit ...`。pilot/conditional-pilot warning 不能升级为 formal 因果证据。
- 合并亲本 genotype/F1/balancer 字段与 stock-to-cross gate：读取 `references/integrated-cross-plan.md`，运行 `scripts/validate_integrated_cross_plan.py --stock-audit ...`，确认 driver/effector 确实出现在亲本 stock 记录中。
- 从 primary paper 抽取 driver/effector、温度、LD/DD、实验单位和 n：读取 `references/primary-genetics-schema.md`，运行 `scripts/validate_primary_genetics.py`。
- 在报告 stock、药物或论文来源前核对 URL 可达性和页面 identifier：读取 `references/online-source-audit.md`，运行 `scripts/check_source_access.py`；`conditional_source_access` 仅是待人工核查的来源线索，不是已验证身份或直接证据。
- 设计或审核信息增益预实验：读取 `references/information-gain-pilot-schema.md`，运行 `scripts/validate_information_gain_pilot.py`；写明缺失事实、最小 readout、experimental unit、对照、成人期边界和 go/no-go 规则，未核实药物/stock 保持待审计。
- 编写急性药理阻断方案：读取 `references/pharmacology-plan-schema.md`，运行 `scripts/validate_pharmacology_plan.py`。
- 设计或质控全细胞膜片钳、膜电位或离子通道电流实验：读取 `references/electrophysiology-qc.md`。

## GEO、转录组和公共数据

- 处理 GEO 表达矩阵、探针注释、候选基因汇总或探索性表达节律：读取 `references/geo-data-workflow.md` 和 `references/public-dataset-manifest.md`。已有输入先做适用哈希验证；已有 executed/verified 上游分析先 replay。新解析/提取/分析须先以 `planning` manifest 登记并通过 validator，再执行；写入真实输出哈希后依次完成 `executed` validator + replay 和 `verified` validator + replay。
- GEO processed matrix 与 GEO family SOFT 的样本映射：先建显式 `matrix_path × matrix_column × matrix_alias × GSM × timecourse_id` 映射，再运行 `scripts/audit_geo_sample_map.py`。它核对列完整性、GSM/title、cell type、ZT/CT 和每个独立 time course 的采样覆盖，不从列名静默猜时间；该 metadata 仍不能补足 fly、sex、age、genotype 或温度。
- 比较 sex、genetic background、cell type、time 或 treatment 等设计因素前：用 `scripts/audit_design_confounding.py input.csv --factor sex --factor genotype_background --factor ZT_or_CT` 检查观察到的水平是否一一绑定。`perfectly_confounded` 只能报告为不可辨识，不能写成独立因素效应；blank 值保持缺失并触发 warning。
- ESAT transcript-level GEO matrix：用 `scripts/audit_esat_candidate_sample_keys.py` 审计候选通道重复样本键（不做表达/节律推断）；通过后可用 `scripts/prepare_esat_candidate_expression.py` 生成候选长表及 sum/median/max 基因级敏感性表。保留 transcript 行与显式来源核查 alias，不推断归一化或生物学单位。进入 `scripts/analyze_expression_rhythm.py` 前处理重复 `gene × sample_id`；若提供 `timecourse_id`，按 course 分组而不合并。
- Abruzzi et al. (2017) GSE77451 S3 cycler 表：读取 `references/published-cycle-table-workflow.md`，运行 `scripts/audit_published_cycle_candidates.py`；按 worksheet 表头解析 F24/JTK，精确匹配完整 gene symbol，保留 HC/LC 和重复行并核对论文与 supplement 的 HC 计数。未列出不等于未表达/无节律；transcript evidence 不等于蛋白、电流、膜电位或因果证据。完成后运行 public-data manifest validator 与 isolated replay。
- GSE157504 clock-neuron 单细胞检出或作者节律：读取 `references/published-sc-clock-rhythm-audit.md`；运行 `scripts/audit_gse157504_candidate_detection.py` 连接 raw counts/细胞注释，并运行 `scripts/extract_published_sc_clock_channel_rhythms.py` 提取作者高置信度节律表。保留 DD/CT、`LN_ITP` 混合类别、未匹配/未覆盖 barcode 与 gene symbol；raw UMI 只作描述性表达证据。对照公开数据还需 manifest validator 与 isolated replay。
- 将 GSE157504 检出/作者节律并列叠加到候选长名单：读取 `references/candidate-context-overlay.md`，验证上游 manifest/replay 后运行 `scripts/build_candidate_evidence_context.py`。保留候选集差异、零 UMI/dropout、未评估候选、`LN_ITP` 模糊亚群、DN 子群范围及静态淘汰理由的人工复核标记；不更改评分或电生理 gate。
- 合并 GSE157504 context 与 Abruzzi2017 S3 cycler calls 为 score-neutral sidecar：读取 `references/combined-transcript-candidate-context.md`，先重验双方 parent manifest/replay，再运行 `scripts/build_published_cycle_candidate_context.py`。保留 s-/l-LNv 混合组、LNd 加第五个 PDF-negative s-LNv、DN1 subset 范围；不将 HC/LC 或未列出结果提升为功能/因果证据，也不改候选分数或电生理 gate。
- 公开果蝇行为数据、Ethoscope metadata 或大型录像归档：读取 `references/public-behavior-metadata.md`，先将输入、审计命令和预期输出登记在 `planning` manifest 并预检，再执行审计；记录实际输出后完成 `executed` validator + replay，再进 `verified` validator + replay。metadata audit 不等于行为节律证据；缺 genotype/sex/age/temperature/LD-DD、个体标识或 raw checksums 时保持 blocked。
- GEO 描述性与推断性表达 cosinor：分别读取 `references/geo-data-workflow.md`、`references/cosinor-inference.md`；描述性分析按 gene/cell/background/developmental_stage/sex 分组，若有 `timecourse_id` 也分组。缺失 strata 标为 `unknown`；表达表与 metadata 的 stage/sex/timecourse 冲突时阻断。推断分析运行 `scripts/analyze_cosinor_inference.py`，提供 `--metadata` 或明确 `--experimental-unit`；按 course 分层、阻断部分缺失 course map 和重复的 `gene × sample_id`，pooled/library 数不能写成独立 fly n，全空候选标为 `no_numeric_expression`，探索性 p/q 不是论文级 mixed model 结论。
- 含多个 cell/ROI/trace 的一般嵌套时序：读取 `references/nested-cosinor.md`，运行 `scripts/analyze_nested_cosinor.py`，先按 `biological_replicate_id × time` 聚合并标注探索性分析。

## 原始实验数据与混合模型

- 审核电生理、成像、表达或行为数据元数据：读取 `references/experimental-metadata-gate.md`，运行 `scripts/validate_experiment_metadata.py --assay ... --stage ...`；检查 cell identity、sex、age、temperature、ZT/CT、batch、biological replicate 与技术重复层级。
- 审核原始 ephys/imaging 文件、QC 指标与派生溯源：读取 `references/raw-qc-provenance-schema.md`，运行 `scripts/validate_raw_qc_provenance.py --assay ...`；解释 blocker、膜电位或成像效应前核对 raw-file hashes、metadata linkage、seal/access resistance、holding current、漂移、ROI/image QC 和排除理由。
- 从标准化 trace CSV 派生 ephys/imaging measurements：读取 `references/trace-derivation.md`，运行 `scripts/derive_trace_measurements.py`；先过 metadata/raw-QC gate，只转换 `qc_status=pass` 行，并从 metadata 锚定 ZT/CT；不自行解码未经验证的 ABF/TIFF。
- 对含 raw ephys trace、metadata、raw-QC、measurement 和 exploratory cosinor 的分析链做重放：读取 `references/ephys-trace-replay-manifest.md`，使用仓库相对 raw path，运行 `scripts/validate_ephys_trace_replay_manifest.py` 和 `scripts/replay_ephys_trace_manifest.py`。重放只证明当前输入/参数/代码的 output hash 可复现，不证明 cell identity、节律或因果。
- 将 metadata、raw-QC manifest 与 measurements 作为 pre-analysis bundle：读取 `references/preanalysis-bundle-gate.md`，运行 `scripts/validate_preanalysis_bundle.py`；pass raw record 必须与派生行一一追踪，orphan/non-pass measurements 阻断下游分析。
- 已过 bundle gate 的 ephys/imaging 派生时序：读取 `references/bundle-cosinor-analysis.md` 并运行 `scripts/analyze_preanalysis_cosinor.py`；在 `biological_replicate_id × time_hours` 内平均技术重复，说明纵向/横断面及时间系统；formal 阶段转交 biological-unit-aware mixed-effects。
- 含多个 subunit/cell/ROI 的 bundle 时序：读取 `references/nested-bundle-inference.md`，运行 `scripts/analyze_preanalysis_nested_cosinor.py`；选定单一 `metric_name` 和一致 `value_unit`，按 biological unit 聚合/重采样；formal 阶段转交 mixed-effects backend。
- 准备 formal mixed-effects handoff：读取 `references/mixed-model-handoff.md`，运行 `scripts/prepare_mixed_model_input.py`；仅当 manifest 为 `ready_for_mixed_model` 才运行 `scripts/emit_mixed_model_templates.py`。缺可用统计运行时则标为 blocked。
- 检查 mixed-effects runtime：运行 `scripts/check_mixed_model_runtime.py`。该检查不安装依赖、不改环境；拟合前仍要有 ready manifest、收敛诊断和预先定义的 contrasts。
- 设计或质控钙成像、免疫染色、RNA-seq 或 single-cell：读取 `references/imaging-and-sequencing-qc.md`。可复现代码、运行日志、数据溯源或论文级输出：读取 `references/reproducibility-and-provenance.md` 与 `references/manuscript-claims.md`。
