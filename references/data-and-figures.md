# 数据分析与可复现作图

## 启动分析

1. 复制或只读检查原始数据；不要覆盖 raw files。
2. 确认文件格式、采集软件、单位、sampling rate、channel mapping、时间基准、缺失值、metadata 和实验层级。
3. 先生成 data inventory、QC 摘要和 analysis plan，再运行改变研究结论的分析。
4. 若格式或 metadata 尚未提供，明确列出所需信息并只搭建可验证的读取或 QC 骨架。

按任务选择工具：表格与统计优先考虑 Python；已有 MATLAB pipeline 或专有格式时沿用 MATLAB；图像分割、ROI 与 batch processing 可使用 Fiji macro。不要为了统一语言而破坏已有可靠流程。

## 全细胞膜片钳

至少核对：recording mode、sampling/filtering、junction potential、internal/external solution、cell capacitance、access/series resistance、bridge balance/compensation、holding potential/current、protocol timing、ZT/CT、cell identity 和每只 brain 的 cell 数。

把 cells、brains、flies、crosses 与 recording days 的嵌套关系保留在数据表中。不得把同一只 brain 的多个 cells 无条件当作独立生物学重复。

输出 QC 阈值及其依据；在看组别效应前尽量固定 exclusion rules。把 resting membrane potential、input resistance、firing rate、current density 等 readout 的计算定义写进代码和图注。

## 成像与表格

保留原始 TIFF 或 stack 和 calibration。记录 ROI 生成方式、background subtraction、bleaching correction、motion correction、z-projection 和 normalization。区分 field、brain、fly 与 batch。

对 CSV 或 Excel 先建立 data dictionary；保留原始列，派生变量使用新列并记录公式。

## 节律与统计

在选择模型前确认：采样是 longitudinal 还是不同个体的 cross-sectional time points、time basis 是 ZT 还是 CT、是否跨多个 cycles、是否有 missing phases，以及实验单位是否嵌套。

根据设计选择 harmonic/cosinor model、mixed-effects model、circular method 或 nonparametric rhythm test。报告 amplitude、phase、period（设计允许时）、effect size、confidence interval 与 model diagnostics；不要仅凭逐时间点 t-tests 宣称存在节律。

预实验以可行性、方差和效应量估计为主。正式实验在独立或 confirmatory dataset 上执行预先规定的模型。

## 可复现交付

始终提供：

- 可运行源代码或 Fiji macro
- environment、package 与 tool versions
- 参数与 random seed
- 从 raw 或 processed data 到 figures 的路径说明
- machine-readable summary table
- QC report 与 exclusion log
- figure source data

探索性分析和组会图优先清晰显示 raw points、distribution、n 与实验单位。论文图在用户提出投稿任务后再按目标期刊规范优化；保留 SVG/PDF 等矢量输出和 PNG 预览，并确保所有图可由代码重建。

## 最小可复现 SVG 作图接口

当环境没有 matplotlib 等绘图库时，可用 `scripts/plot_circadian_timeseries.py` 从规范化 CSV 生成可审计 SVG 和 JSON 报告：

```powershell
python scripts/plot_circadian_timeseries.py validation/synthetic-ephys-trace-derived.csv `
  --time-system ZT --output-svg validation/synthetic-ephys-trace-figure.svg `
  --report validation/synthetic-ephys-trace-figure.json
```

该接口要求显式声明 `--time-system ZT|CT`，默认要求 `biological_replicate_id` 存在且每行有完整分组标签，保留每行 raw point，并按生物学重复叠加各时间点均值。若确实要把行视为同一组，必须显式传 `--group-column ''`。接口会拒绝非有限数值、混合或不完整的 `metric_name`/`value_unit` 标签，报告输入与输出 SHA-256、组数和单位。输出状态为 `verified_visualization_export`，但 `scientific_status=not_a_rhythm_test`：SVG 仅用于 QC、探索和组会展示，不能替代 cosinor、混合模型或正式节律检验。

在正式分析中仍需同时交付源数据、数据字典、排除日志、模型代码和统计报告；不要把均值折线或视觉周期解释为显著节律或因果关系。
