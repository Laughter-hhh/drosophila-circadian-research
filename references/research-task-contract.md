# 科研任务合同

## 目的

把一个自然语言科研请求转换成可执行、可审计、可复现的任务。合同是“计划”和“结果”的边界，不是把未完成的分析包装成结论。

## 最小字段

```yaml
task_id: unique-name
status: planning            # planning | executed | verified | blocked
research_question: ""
hypothesis: ""
alternative_hypotheses: []
species: Drosophila melanogaster
preparation: ""
cell_type: ""
experimental_unit: fly     # fly | brain | cell | culture | library | image
primary_readout: ""
secondary_readouts: []
time_system: "ZT/CT and LD/DD must be specified or left unknown"
input_files: []
required_metadata: []
analysis_plan: ""
decision_gate: ""
expected_outputs: []
acceptance_tests: []
```

真实项目可以增加 `genotype`、`sex`、`age_days`、`temperature_C`、`drug`、`batch`、`randomization`、`blinding`、`power_basis`、`exclusion_criteria`、`software_versions` 和 `source_log`。

## 状态规则

- `planning`：可以给出假说、方案、模拟数据和缺口，但不得使用“结果显示”。
- `executed`：必须列出实际输入文件、代码版本、命令、运行时间和输出路径。
- `verified`：至少完成一次重跑、独立计算或预先定义的 QC；说明容差和失败项。
- `blocked`：仅在缺失信息会改变实验解释或分析定义时使用；同时给出最小的信息获取实验。

## 阶段门

### Gate 0：问题可定义

研究问题、物种、样本单位、主要 readout 和时间条件可写成一句话。标签或缩写未定义时保持未知。

### Gate 1：数据可用

输入文件可读取，列名和单位明确，样本与元数据一一对应，重复层级没有混淆，缺失值和排除标准已预先写出。

### Gate 2：分析可运行

分析脚本、配置和环境版本固定；关键参数有来源或理由；能在测试数据上通过正例和负例。

### Gate 3：科学结论可解释

主要结果通过 QC，统计模型匹配实验单位，替代解释已列出，结论没有超过证据级别。

未通过某一 Gate 时，可以继续做探索性工作，但要标注为预实验或方法开发。

## 验收标准

验收应检查数值和科学不变量，而不是只检查文件存在：

- 同一配置和输入重跑时结果在预设容差内一致；
- 样本顺序、标签和单位通过自动检查；
- 正例数据产生预期方向，负对照不产生假阳性；
- 每个图表可追溯到中间表和原始输入；
- 每个关键结论都能回溯到来源、实验或分析输出。

## benchmark 与真实研究

如果请求来自 Terminal-Bench 或类似 benchmark，单独列出题目规定的格式、参数和验收规则，并标记为 `task constraint`。它们不能自动升级为真实实验的最佳实践，也不能替代生物学重复、功效分析、QC 或独立验证。
