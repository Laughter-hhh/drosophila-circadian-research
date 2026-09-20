# 全细胞膜片钳药理学阻断计划的机器可读审计

validate_pharmacology_plan.py 用于在采购药物或开始正式记录前，检查急性离子通道阻断计划是否具备可追溯的浓度、选择性、给药、洗脱和 stage-gate 信息。

## 必需字段

plan_id, candidate, neuron, readout, blocker, concentration, concentration_unit, application, vehicle, washout, blocker_selectivity_source, concentration_source, positive_control, negative_control, off_target_risk, stage, source_url, selectivity_status, dose_response_status, washout_status。

## Stage 枚举

stage 只能是 pilot、conditional_pilot 或 formal。任何其他标签（例如 exploratory_pilot、preliminary 或 screening）都会被拒绝，避免自然语言标签绕过 formal gate。

## 状态字段

- selectivity_status: native_verified, heterologous_only, not_assessed 或 unknown。native_verified 表示引用来源在目标 native 神经元中用对应遗传缺失/抑制等对照验证了 blocker-sensitive current；它是来源级证据，不代表本实验室已完成验证，也不证明该药在所有浓度、细胞或制备中具有绝对选择性。
- dose_response_status: validated, not_assessed 或 unknown。
- washout_status: validated, needs_confirmation, not_applicable 或 unknown。
- conditional_pilot/pilot 可以在这些状态未完成时通过格式审计，但会产生警告并标记为 blocked_for_formal；formal 必须同时满足 native_verified、validated dose-response 和 validated/not_applicable washout，否则拒绝。

## 机器状态解释

status=verified_pharmacology_plan 只表示表格结构、格式和 stage-gate 一致，不等于药理学方案已获准执行。必须同时读取 formal_status：

- conditional_pilot_only：没有 formal 行，当前只能做条件性预实验或信息获取实验；
- formal_gate_blocked：存在 formal 行，但至少一行未通过药理学 gate；
- formal_gate_passed_external_checks_pending：形式 gate 通过，但仍需确认药物来源、native-cell 选择性、起效/洗脱动力学、毒性和实际浓度；
- blocked_by_validation_issues：存在字段、格式或 formal gate 错误，包括未知 stage 或联合证据失败。

## 候选证据联合门禁

默认单表审计保持兼容。若使用 --candidate-evidence，必须同时提供 --search-log。脚本随后要求：

- 药理学 candidate 精确出现在已通过 search-log 的候选证据表中；
- 药理学 source_url 与候选证据 sources 至少有一个共享来源 token；
- candidate 的 evidence_label 为 direct、near_direct 或 indirect；unverified 不能被当作可执行候选证据。

若名称不是精确匹配，可额外提供 --candidate-mapping。映射表必须包含 source_candidate、evidence_candidate、mapping_type、mapping_status、mapping_source；只接受 mapping_status=checked、明确的 official_symbol_alias 或 curated_synonym，以及可核查 URL。映射只解决名称对应关系，不提升 evidence label、target scope 或 source linkage。因此公开 fixture 中 Shaker→Sh 的身份映射已被接受，但 Sh 的 unverified 证据仍会被联合门禁阻断；这是一种有意保守的结果。

## Blocker-specific source-log bundle

若要验证 blocker、浓度和选择性来源，使用 validate_pharmacology_bundle.py，而不是只运行单表 validator。它要求一个独立 source log，并把每条记录按 plan_id + candidate + blocker 连接回计划：

- source log 必须通过 validate_pharmacology_source_log.py；
- source_url 必须与 source log 的来源链接；
- target_neuron 必须与计划 neuron 一致；
- formal 行必须有 checked source、matched concentration 和 native_verified selectivity；若只有文献级 native 选择性，仍应在 formal 实验中确认当前 preparation、vehicle、局部剂量和 off-target 风险。
- pilot 行可以保留 not_assessed，但会产生 blocker_concentration_not_verified 或 blocker_native_selectivity_not_verified warning。

source log 的必需字段包括 record_id、plan_id、candidate、blocker、source_id、source_url_or_identifier、target_neuron、assay、evidence_label、source_support_status、concentration_status、reported_concentration、reported_concentration_unit、selectivity_support_status、result_summary、decision 和 decision_reason。concentration_status=not_assessed 或 conflict 时，reported concentration/units 可以写 NA；matched 时必须有正数和合法单位。

source_url_or_identifier 可以是 HTTP(S) URL，也可以是受限、可审计的 identifier（例如 PMID:31612994、DOI:10.xxxx/...、FBgn:FBgn0003380、GSE:GSE... 或合法 stock/database 前缀）。bundle 会把 PubMed URL 与对应 PMID:<数字>、DOI URL 与 DOI:<值> 规范化为共同 token；这只解决记录联结，不代表来源内容已经被全文核查。

推荐命令（PowerShell）：

    python scripts/validate_pharmacology_bundle.py validation/public-data/primary-pharmacology-methods.csv --source-log validation/public-data/primary-pharmacology-source-log.csv --output validation/primary-pharmacology-bundle-validation.json

若要同时启用候选证据联合门禁，再追加 --candidate-evidence、--search-log 和可选的 --candidate-mapping；联合门禁失败时应保留其阻断结果，不要把基础 source-log bundle 的成功误读为候选证据成功。

bundle 成功只表示来源记录和字段链接通过；公开 fixture 当前会得到 verified_pharmacology_bundle 但 formal_status=conditional_pilot_only，因为 exact concentration 和 native selectivity 仍未验证。

## 审计规则

- 浓度必须是正数，并明确 nM、µM/uM 或 mM；不要把“高浓度”或只写药物名称当作可执行方案。
- blocker_selectivity_source 与 concentration_source 必须分别可追溯；脚本不判断来源是否真的支持该浓度或选择性。
- 必须显式写出 application（例如 bath/perfusion）、vehicle、washout 或不可洗脱的理由、positive/negative control、off-target 风险和实验 stage。
- plan 的 source_url 需为 URL；source log 的 source_url_or_identifier 可使用上述受限 identifier。若来源不是 PubMed、PMC、DOI、期刊或机构原始论文入口，只给出警告，不自动判定为无效。
- 通过审计只表示字段完整、格式可解析且 stage gate 一致，不表示药物在 native clock neuron 中具有单一靶点，也不表示浓度、起效/洗脱时间或细胞耐受性已经验证。

## 使用边界

Smith et al. 2019 报告过 l-LNv 中 DTX 100 nM、GxTX 20 nM、BDS 300 nM 和 PaTX 100 nM 的选择性阻断条件；这些是文献起始条件，不应直接替代本实验的剂量-反应、vehicle、洗脱和 off-target 预实验。正式方案必须把来源、核查日期和本实验的 stage gate 单独保存。
