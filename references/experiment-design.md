# 假说与实验设计

## 先定义实验单位与因果边

把问题写成一条或多条可证伪关系，并分别标注当前证据状态：

- `molecular clock → channel expression/localization/function`
- `channel → membrane potential/firing/Ca2+ activity`
- `clock-neuron activity → locomotor/sleep rhythm`
- `external neural input → channel/activity rhythm`

指出目标神经元亚型、time basis（ZT/CT）、LD/DD、性别、日龄、温度、readout、干预和实验单位。缺少这些信息时不要暗中补全。

## 使用 stage gates

### Gate 0：身份与可测性

核实目标神经元表达、reagent specificity、readout dynamic range 和基础实验可行性。

### Gate 1：候选参与膜电活动

用急性 pharmacology 与全细胞膜片钳进行探索；以 vehicle、wash-in/wash-out、access resistance、series resistance、cell health 和 time-matched controls 约束解释。药物浓度和选择性必须来自当前核实资料。

### Gate 2：候选是否具有节律

区分 transcript abundance、protein abundance、membrane localization、functional current 与 downstream excitability。不要用一个层级的节律代替另一个层级。采样多个 circadian phases，并使用适当的 rhythmic model 与多重比较控制。

### Gate 3：外界输入如何调节

将 presynaptic manipulation、postsynaptic receptor/conductance 和膜电位 readout 解耦。优先使用时间受控的 optogenetic 或 thermogenetic manipulation，并设计 light/temperature、retinal、driver-only、effector-only 和 synaptic-isolation controls。

### Gate 4：行为关联与因果闭环

在 upstream links 成立后再设计 locomotor 或 sleep validation。区分 period、phase、amplitude、rhythmicity、activity level 与 sleep architecture，避免把活动量变化误判为时钟变化。

## 区分三种设计

### 信息获取实验

用于填补会改变后续设计的事实，例如表达、亚细胞定位、stock genotype、药物敏感性、信号动态范围或 recording stability。

### 探索性预实验

允许检验当前证据之外的一条因果边。使用较小但说明依据的样本、预设 QC 和明确 go/no-go；将 effect-size estimation 与可行性作为主要目的，不做 confirmatory claim。

### 正式验证实验

仅在相关 stage gate 通过后详细设计。默认包含：

- primary outcome 与关键 secondary outcomes
- 生物学重复、技术重复和独立实验单位
- effect size 或 pilot-based power justification
- randomization、blinding、allocation 与 exclusion criteria
- negative、positive、vehicle、genetic background、driver-only、effector-only controls
- sex、age、temperature、LD/DD、ZT/CT、batch 与 investigator effects
- nested/hierarchical structure，如 cells nested in brains、brains nested in crosses/days
- preregistered analysis、multiple-comparison strategy 与 data/code provenance

## 机制筛选顺序

1. 用文献和表达数据建立候选长名单。
2. 用 acute pharmacology + whole-cell current clamp 或 voltage clamp 定位 conductance class；解释 washout、state dependence 和 off-target。
3. 用 adult-restricted RNAi 做 cell-type-specific pilot，至少规划两个独立 RNAi 或一项正交验证。
4. 对阳性候选区分 expression rhythm 与 functional rhythm。
5. 再测试外界输入是否改变 channel-dependent current 或 membrane rhythm。
6. 最后连接到 locomotor 或 sleep phenotype。

## 输出每个实验模块

为每个实验给出：问题、假说、因果边、实验组、controls、时间条件、readout、QC、实验单位、分析方法、预期结果矩阵、替代解释、go/no-go、失败后的 rescue、预计耗时与依赖条件。

不得把“显著差异”作为唯一成功标准。优先定义方向、效应量、置信区间、可重复性和能区分竞争假说的结果模式。
