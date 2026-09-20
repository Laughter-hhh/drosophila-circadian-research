# 果蝇遗传杂交与 stock 核查

## 来源顺序

对 gene identity、allele、construct 和 insertion 先查 FlyBase，再查 stock center 当前页面与原始论文。覆盖所有可用来源，至少检查：

- FlyBase: https://flybase.org/
- Bloomington Drosophila Stock Center: https://bdsc.indiana.edu/
- Vienna Drosophila Resource Center: https://stockcenter.vdrc.at/
- NIG-Fly: https://shigen.nig.ac.jp/fly/nigfly/
- Janelia FlyLight: https://www.janelia.org/project-team/flylight

按需要扩展 Kyoto、DGRC 或作者实验室资源。每次重新核对当前可得性、完整 genotype、插入染色体、背景、stock number、页面更新时间或访问日期和订购限制。任何不一致都保留并解释；不得拼接不同页面的信息形成未经证实的 genotype。

## 设计前核对

1. 规范 current gene symbol、synonyms、allele 或 construct ID。
2. 核对 driver、responder、repressor、reporter 和 balancer 所在染色体。
3. 核对 sex linkage、lethality/sterility、marker、recombination requirement 和 temperature sensitivity。
4. 评估 driver expression specificity、RNAi off-target、insertion/background effects 与 dosage。
5. 优先规避发育影响；按工具可得性考虑 `tub-GAL80ts`、adult-inducible systems 或时间受控 manipulation。
6. RNAi pilot 优先；规划第二条独立 RNAi、rescue、mutant 或 CRISPR 或 pharmacology 作为正交验证。

## 杂交表

输出：

| 项目 | 内容 |
|---|---|
| Purpose | 本次 cross 检验的因果边 |
| Virgin parent | 性别、完整 genotype、stock、来源、核查日期 |
| Other parent | 性别、完整 genotype、stock、来源、核查日期 |
| F1 target | 目标性别与完整 genotype |
| Selection | balancer 或 marker 与筛选逻辑 |
| Reciprocal cross | 是否需要及其目的 |
| Controls | driver-only、effector-only、background、RNAi control 等 |
| Rearing | 温度、密度、LD、转温或诱导时间 |
| Timeline | 建瓶、转瓶、羽化、aging、recording 的预计周期 |
| Risks | lethality、低产量、表达泄漏、背景与替代路线 |

显式检查目标 F1 是否同时携带所有必需元件。若需要重组或建立稳定品系，单独给出世代流程、每代筛选标记、验证方法与保种策略。

## 不确定性处理

若 stock 页面无法访问或 genotype 冲突：

- 标注“未核实”，不要给出看似精确的 stock number。
- 提供需要用户或 stock center 确认的问题。
- 可设计不依赖该 stock 的信息获取或替代实验，但不要把未核实品系写进正式方案。
