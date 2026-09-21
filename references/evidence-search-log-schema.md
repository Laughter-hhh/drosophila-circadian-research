# Evidence search-log schema

候选筛选不能只保存一串 URL。每条文献、数据库或 stock 记录都应作为一行 evidence record，保留当时的检索上下文与决定，使后续复核可以重建“为什么纳入/降级/排除”。

## 必需字段

同一篇文章若报告不同实验和 readout，应拆成多条 source-log 记录；例如细胞内离子浓度、培养细胞 patch clamp、体内行为分别记录。每条记录只声明其直接测量的 readout 与细胞范围，不得把一项实验的目标细胞范围借给另一项实验。

| Field | 允许值或要求 |
|---|---|
| `record_id` | 稳定、唯一的记录名 |
| `candidate` | gene symbol 或其他明确候选名 |
| `query` | 实际检索词，不得留空 |
| `database` | FlyBase、PubMed、PMC、GEO、BDSC、VDRC 或其他明确数据库 |
| `search_date` | ISO `YYYY-MM-DD` |
| `source_id` | PMID、DOI、FBgn、GEO accession 或数据库记录号 |
| `source_url_or_identifier` | 可打开的 URL 或可复核 identifier |
| `source_type` | `primary_paper`、`preprint`、`review`、`FlyBase`、`GEO`、`stock_database`、`other_database` |
| `organism` | 证据所属物种；默认候选物种为 *D. melanogaster* |
| `target_cell_scope` | `direct_target_neuron`、`nearby_clock_neuron`、`indirect_or_unverified`、`none_or_unverified` |
| `evidence_target_cells` | 直接证据实际覆盖的具体细胞亚型，以分号分隔；未知写 `unverified`，混合 LN_ITP 写 `LN_ITP_ambiguous`。|
| `assay` | 实际 assay，不能写泛化的“文献支持” |
| `readout_match` | `membrane_potential_or_current`、`expression_or_localization`、`intracellular_ion_concentration`、`behavior_only`、`none_or_unverified` |
| `evidence_label` | `direct`、`near_direct`、`indirect`、`unverified` |
| `claim_type` | `conclusion`、`inference`、`no_evidence` |
| `source_support_status` | `checked`、`not_checked`、`conflict`、`unavailable` |
| `result_summary` | 简短结果摘要，区分事实与解释 |
| `decision` | `include`、`conditional`、`exclude_from_direct_shortlist` |
| `decision_reason` | 纳入/降级/排除的可审计理由 |

`intracellular_ion_concentration` represents a measured ion-concentration readout such as s-LNv ClopHensor imaging; it is not membrane potential or channel current. `evidence_label=direct` 只有在目标细胞亚型（`evidence_target_cells`）、具名 assay 和匹配 readout 均明确时才允许；`near_direct` 只能进入 conditional pilot；`indirect`/`unverified` 保留在长名单中但不得成为 direct shortlist pass。学位论文/学位论文数据库记录不纳入，除非用户主动上传原文。

运行 `scripts/validate_evidence_search_log.py` 后，才可把记录合并进候选证据表。该脚本检查 schema 与自洽性，不替代人工阅读原文、在线核查链接或判断来源是否真正支持结论。
