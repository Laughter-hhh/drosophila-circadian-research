# 成像与转录组 QC

## 钙成像

预先定义 frame rate、曝光、指标表达、刺激时间、baseline、ΔF/F 计算、motion correction、bleaching correction、ROI 和 neuropil subtraction。保存原始 movie、校正 movie、ROI mask、每 ROI 时间序列和排除原因。

需要检查 motion、饱和、漂白、焦平面漂移、光毒性、响应延迟和不同批次的 indicator 表达差异。多个 ROI 来自同一细胞时，明确是先按细胞汇总还是使用层级模型。

## 免疫染色

记录抗体、批号、稀释、固定、透化、成像参数、曝光、背景扣除、盲法和 scale bar。定量时预先定义 segmentation、阈值、细胞计数单位和每只 fly 的抽样规则。representative image 不得替代群体定量。

## Bulk RNA-seq

记录 sample sheet、RNA 质量、library batch、测序批次、read depth、参考基因组/注释版本、比对或定量工具版本、过滤规则和多重检验方法。差异分析要明确 biological replicate，不能把技术重复当作独立样本。

## Single-cell RNA-seq

至少记录 cell barcode/UMI 过滤、doublet、线粒体比例、批次整合、cluster marker、细胞类型判定和 pseudobulk 单位。整合后的 cluster 可用于探索，但不能把每个 cell 当作独立生物学重复来证明动物层面的差异。

## 结果边界

表达变化、蛋白信号或 calcium event 与膜电位机制之间通常是不同层级的 readout。除非有干预、时间顺序和正交测量，不要把相关性写成因果链。
