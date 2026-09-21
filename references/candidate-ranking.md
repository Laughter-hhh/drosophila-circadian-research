# 离子通道候选生成与排序

## 建立长名单

从 FlyBase、目标神经元 bulk/single-cell 数据、已有 electrophysiology、circadian screens、行为表型与跨物种研究汇总候选。保留阴性和冲突结果。

按优先级分类：

1. Leak channels 与 gated ion channels
2. 其他直接形成离子电导的 channels
3. Gap junction components
4. Pumps、transporters、exchangers
5. 调控 channel trafficking、phosphorylation 或 degradation 的蛋白

不要因为类别优先级低而删除有强直接证据的候选。

## 证据标签与 directness gate

候选表必须把下列字段与评分分开保存：

- `organism`：证据来自哪个物种；默认候选物种为 *Drosophila melanogaster*。
- `target_cell_scope`：`direct_target_neuron`、`nearby_clock_neuron`、`indirect_or_unverified` 或 `none_or_unverified`。
- `evidence_target_cells`：直接实验支持的具体细胞亚型，以分号分隔（如 `s-LNv;l-LNv`、`DN1p`）；混合群记为 `LN_ITP_ambiguous`，无可核实范围记为 `unverified`。
- `assay`：实际使用的 assay（例如 whole-cell electrophysiology、RNAi、immunostaining、single-cell RNA-seq）。
- `readout_match`：`membrane_potential_or_current`、`expression_or_localization`、`behavior_only` 或 `none_or_unverified`。
- `evidence_label`：`direct`、`near_direct`、`indirect` 或 `unverified`。

`readout_match` 还可为 `intracellular_ion_concentration`，用于如 ClopHensor 的细胞内离子浓度测量；它不得被当作膜电位或离子通道电流。`directness_gate=pass` 只允许同时满足：`evidence_label=direct`、直接目标时钟神经元范围、具名 assay，以及与本次明确选择的 readout 相符的证据。`near_direct` 只能得到 `conditional_directness`，用于信息获取或 pilot，不得伪装成直接 Top 候选。`indirect` 与 `unverified` 保留在长名单中，但必须标成需要直接证据。

真实候选排序必须把同一份经验证的 evidence-search log 与 `--readout-match` 一起传给 scorer；同时使用 `--target-cell` 明确细胞亚型。CLI 会在评分前联合验证候选表与 source log；不能只验证 log schema，也不能用候选表中的汇总字段代替 source-level 支持。缺少 log 或候选表/log 不一致时停止写出排名。scorer 仅用同一 readout 域中、经核查的 source-log rows 计算目标直接性，不再把某篇论文的培养细胞电流、目标神经元表达和行为/分子钟 readouts 汇成一个 directness claim。若某 readout 没有同亚型的直接/近直接记录，应返回 `needs_direct_evidence` 或相应的 scope gate，即使候选在其他 readout 上有强证据。

命令行不允许对带数值评分或 `membrane_potential_or_current` 声明的候选表省略 `--search-log` 和 `--readout-match`。唯一例外是所有评分维度均为 `NA` 且非 current/membrane-potential 的探索性上下文诊断（如转录组 handoff）；此类运行必须保持空排名/无 Top，不能作为候选排序。

`directness_gate` 是**readout-specific**，不能跨 readout 解释：`expression_or_localization` 下的 `direct` 仅表示目标细胞中的转录本/表达/定位被直接测量，不等于通道电流、膜电位节律或功能因果证据；`membrane_potential_or_current` 也可能是观察性 readout，若要声称候选通道导致变化，必须核实候选特异扰动、相应对照和 readout。评分输出的 `readout_domain` 与 `directness_basis` 会明确列出当前直接性覆盖的 readout 域。`shortlist_gate` 是证据分流而非功能因果证明。

必须为本次问题用 `--target-cell` 显式指定一个或多个目标亚型。`LNv` 不自动覆盖 `s-LNv`/`l-LNv`；`DN1p` 只覆盖该子集，不能代表全部 `DN`；`LN_ITP_ambiguous` 不映射到纯亚型。只有全部目标均有精确证据覆盖才通过直接匹配，子集覆盖须标记 partial/conditional。若所有评分维度均为 `NA`，应报告 `insufficient_scored_evidence`、空排名与空 Top；并列最高者完整列出，不任意指定赢家。

如果满足 coverage 的直接 gate 候选少于用户要求的 Top 5/Top 10，必须报告“direct-gate 候选不足”，并同时给出 conditional/indirect 候选及其升级实验；不得用间接证据填满直接 Top-K。

## 默认透明评分

每项按 `0–3` 评分；缺失证据记 `NA`，不要记作 0。用以下权重生成初始排序，用户可覆盖：

| 维度 | 权重 | 3 分示例 |
|---|---:|---|
| 目标时钟神经元表达 | 4 | 多个独立数据或直接成像在目标神经元支持 |
| 已有电生理证据 | 4 | 操作该候选直接改变目标或紧邻神经元的相关电流或膜电位 |
| 遗传工具可获得性 | 3 | 当前可核实的多个独立 reagents，且可做 cell/adult specificity |
| 通道类别匹配 | 2 | leak 或与目标 readout 直接相关的 gated channel |
| 昼夜节律证据 | 2 | 多时间点、适当模型支持 expression/localization/function rhythm |
| 果蝇节律或行为因果证据 | 1 | 严格 controls 下有节律或行为效应 |
| 跨物种机制支持 | 0.5 | 同源通道在 circadian neurons 中有直接机制证据 |

计算：`score = Σ(observed rating × weight) / Σ(observed maximum × weight) × 100`。

同时报告 evidence coverage，防止只有少量维度的候选获得虚高分。排序先按 directness gate/score，再按 coverage-adjusted score；总分不能掩盖表达矛盾、药理工具非选择性、reagent 未核实、发育表型、背景效应或 readout 不匹配。

## 候选表与检索日志的联合门槛

同一篇 primary paper 若包含多个实验/readout，必须为每个 readout 拆分 source-log 记录，并各自标明 assay、target-cell scope 和 evidence label。例如 s-LNv ClopHensor、S2-R+ 异源表达 patch clamp、LNv 行为周期结果不能合并成一条 s-LNv current 证据。联合校验会要求候选摘要连接到同来源、同 readout、同 scope 的 checked 记录，且具名目标细胞由这些记录覆盖。

`scripts/validate_candidate_evidence.py` 默认做 schema 检查；真实候选进入排序前，使用：

```powershell
python scripts/validate_candidate_evidence.py candidates.csv `
  --search-log evidence-search-log.csv `
  --output candidate-evidence-validation.json
```

`--search-log` 会验证 evidence-search log，并联合验证候选表：每个候选必须出现在 log 中；候选表的 `sources` 至少与 log 的 `source_id` 或 `source_url_or_identifier` 共享一个标识；`direct`/`near_direct`/`indirect` 声明必须由同来源、同 readout、同 target scope 且具备 `checked` 状态的记录支持；具名细胞必须被这些匹配记录覆盖。`score_candidates.py` 在 CLI 内重复执行这一 gate，避免调用者跳过单独验证步骤。这个门槛证明的是可追溯性和声明的一致性，不替代在线打开原文、数据库记录或核对 reagent 当前状态。

合成夹具可以继续只做 schema 验证；若要模拟正式证据链，必须同时提供结构化 search log，并在报告中保留检索日期、查询、来源类型和纳入/降级决定。

## 输出表

完整长名单至少包含：

| Candidate | Class | Organism | Target-cell scope | Assay | Readout match | Evidence label | Target-neuron expression | Electrophysiology | Genetic tools | Rhythmic evidence | Fly phenotype | Score | Coverage | Directness gate | Confidence | Keep/drop reason | Sources | Evidence notes |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|

先按 directness、score、coverage 综合排序，再深入分析 direct-gate Top 5 或 Top 10；若数量不足，明确列出缺口，不得静默补齐。对每个 Top 候选给出：

- 最强支持与最强反证
- 关键未知项
- 最便宜或最快的信息获取步骤
- pharmacological electrophysiology pilot
- RNAi pilot 与避免发育效应的方案
- 阳性结果的正交验证
- 明确的淘汰或升级标准

对降级候选写出原因，例如“目标神经元无可核实表达”“只有非果蝇证据”“药理选择性不足”“无可用遗传工具”，而不是静默删除。
