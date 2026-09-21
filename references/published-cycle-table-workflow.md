# 已发表时钟神经元转录节律表的候选核对

## 范围

`GSE77451` 的 processed expression matrix 与 Abruzzi et al. (2017) 的 S3 supplement 是两种不同分析入口：前者需要先确认样本列、时间和重复结构，再决定是否重做统计；S3 核对只判断作者是否把某个精确基因符号列入已发表 cycler 表，不重算节律。

主来源：Abruzzi, K. C. et al. RNA-seq analysis of Drosophila clock and non-clock neurons reveals neuron-specific cycling and novel candidate neuropeptides. *PLoS Genet.* **13**, e1006613 (2017). https://doi.org/10.1371/journal.pgen.1006613. Supplementary S3: https://doi.org/10.1371/journal.pgen.1006613.s003.

## 表格与分析边界

- S3 工作表列出 LNv、LNd、DN1 与 TH 组的作者 cycler calls；只把前三个 clock-neuron sheet 映射到本任务候选。TH 是 non-clock outgroup，不作时钟神经元候选证据。
- 作者报告在 LD 下采集两组独立六时点 time course、每四小时一次；LNv/LNd 为 ZT2–22，DN1 为 ZT3–23。作者将同时通过 JTK_cycle 和 F24 的 transcript 定义为 high-confidence (HC)，只通过其中一个的定义为 low-confidence (LC)。文章所述 cutoffs 包括 JTK p<0.05、F24 score>0.5、振幅>2-fold、平均 reads>5。审计保留 S3 已发布统计量，不从这些字段重新筛选或拟合。
- 候选键是候选表的 `candidate` 与 supplement 的 `symbol`。仅做大小写敏感的完整符号匹配；不自动展开别名、不做模糊匹配、不把 `Sh` 变成 `Shal` 或 `Shaw`。如需别名，应先创建带 FlyBase FBgn/FBtr、来源和审阅状态的显式映射表。
- 每个 worksheet 独立按表头解析 F24/JTK flag，因为不同 sheet 的两列顺序不同。重复 symbol 行逐行保留，并输出源行号；不得悄悄合并 transcript/feature 记录。
- 未在目标 cycler sheet 中找到精确 symbol 时标为 `not_listed_in_published_cycler_supplement`。这不等于未表达、无节律或没有离子通道作用。

## 细胞群覆盖范围

- 论文的 LNv RNA-seq library 同时包含 PDF-positive s-LNv 与 l-LNv，不能用于区分这两个亚群。
- 论文的 LNd 组包含第五个 PDF-negative s-LNv，因此它不是 LNd-only 的证据。
- DN1 是论文采集的一个 subset，不代表全部 dorsal neurons 或 DN1a/b/c 的逐类结果。
- 样品为分离神经元的 pooled library（论文报告每个样品约 50–100 个细胞）。本 S3 核对不还原个体 fly 身份，也不提供 cell-level 或 fly-level replication。
- transcript cycling 不等价于 channel protein abundance、膜电流、膜电位或行为因果证据。候选排序必须继续保留这些 readout 的区别。

## 必须报告的源内核查

将解析所得 HC 数量与论文正文报告的数量并列；同时检查 sheet header、HC/LC 标注、F24/JTK 标记、重复 symbol 和时间点组。若正文与 supplement 不一致，保留两个值并标记未解决，不要静默选择其中一个。

在 2026-09-21 的当前核对中，S3 LNv sheet 有 252 个 unique HC symbols，而论文正文报告 249；LNd 为 303 对 303，DN1 为 185 对 185。当前三个 sheet 的 F24/JTK flags 与 HC/LC 标签一致；LNd 的 `CG40498` 与 DN1 的 `Nopp140` 有重复行，但这些重复均为 LC。LNv 的 3-symbol 差异未能由重复 symbol 或表内 flag 冲突解释，需保留为 source discrepancy。

## 可复现命令

```powershell
python scripts/audit_published_cycle_candidates.py `
  --workbook validation/public-data/Abruzzi2017_S3_cycle-transcripts.xlsx `
  --candidates validation/public-data/candidate-evidence-real.csv `
  --output-csv validation/public-data/Abruzzi2017_channel-candidate-cycle-evidence.csv `
  --output-report validation/public-data/Abruzzi2017_channel-candidate-cycle-audit.json

python scripts/validate_public_dataset_manifest.py validation/public-data/Abruzzi2017-candidate-cycle-manifest.json --root . --output validation/public-data/Abruzzi2017-candidate-cycle-manifest-validation.json

python scripts/replay_public_dataset_manifest.py validation/public-data/Abruzzi2017-candidate-cycle-manifest.json --root . --timeout-seconds 120 --output validation/public-data/Abruzzi2017-candidate-cycle-replay.json
```

Manifest/replay `verified` 只表示源文件、代码、参数和输出哈希可追溯并可确定性重放，不会消除上面的 LNv source discrepancy，也不证明转录节律具有因果作用。
