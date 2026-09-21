# 候选离子通道评分器

## 用途

`score_candidates.py` 只把已有证据表转换为可复核的初始排序，不替代文献核查、表达验证、药理特异性评估或实验判断。

## 输入列

CSV 必须有 `candidate`，其余可使用以下维度（评分 0–3，缺失写 `NA`）：

`expression`, `electrophysiology`, `genetic_tools`, `class_match`, `rhythmic_evidence`, `fly_causal`, `cross_species`

运行时必须通过一个或多个 `--target-cell` 显式声明本次目标细胞；输出会独立标示细胞证据是否 exact、partial、broad-parent 或 mismatch。所有评分维度均为 `NA` 时不得生成 Top 排名；并列候选完整报告。

默认权重与 `candidate-ranking.md` 一致：4、4、3、2、2、1、0.5。`NA` 不计为 0，也不进入 raw score 的该候选分母；同时输出加权 coverage。

## 排名与 shortlist gate

同时输出：

- `score`：仅在已观察维度上计算的证据强度百分比；
- `coverage`：已观察维度的权重占全部权重比例；
- `coverage_adjusted_score = score × coverage`：默认排序键，用于防止只填写一个高分维度的候选虚高；
- `coverage_gate`：证据完整度门槛，不是生物学结论。

默认 `coverage_gate=pass` 要求 `coverage >= 0.5` 且至少观察到 3 个维度；否则标为 `needs_evidence`。该门槛用于回答“能否进入重点分析”，不能替代直接证据、stock 核验或实验 go/no-go 判断。

敏感性输出的 `rankings` 保留全部有分数的候选供长名单比较；但 `top_candidates` 只从目标细胞 gate 为 `pass` 或 `conditional_directness` 的候选中选。仅部分覆盖、细胞不匹配或没有目标特异证据时，Top 留空，并在 `top_candidate_status` 说明原因；不得把高分的无关候选命名为目标细胞 Top。

## 敏感性分析

解释敏感性时，`top_candidate_stable` 表示三个权重情景中有相同的唯一赢家；`top_candidate_set_stable` 表示三个情景中的 Top/并列集合相同。稳定的并列集合仍然没有唯一赢家。

评分器可比较默认权重、表达/电生理优先、遗传工具优先三组情景，并分别报告 raw ranking 和 gate-pass shortlist。若 Top 候选或 gate-pass 集合频繁改变，报告“排名对权重敏感”，不要把排序当成稳定事实。任何最终候选仍需给出直接来源、最强反证和可淘汰标准。
