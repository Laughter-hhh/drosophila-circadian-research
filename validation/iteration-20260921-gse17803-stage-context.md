# 2026-09-21 迭代：GSE17803 发育阶段分层

## 发现与修复

真实数据检查发现，表达提取器此前虽读入 GEO 样本特征，却没有保留 `developmental stage`，汇总只按 gene、cell type、time、background 分组。同名细胞标签下的 larval 与 adult 样本因此被合并，可能造成错误的表达背景比较。

提取器现在识别 `developmental stage`、`developmental_stage` 和 `stage` 字段，将 `developmental_stage` 写入样本级与汇总表，并纳入分组键。缺失值保持 `unknown`；不从样本标题猜填。工作流文档同时要求对 developmental stage 及其他已记录的生物学上下文分层或显式建模。

## 公开数据验证

使用 [NCBI GEO GSE17803](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE17803)（Drosophila melanogaster，GPL1322；23 个样本）。官方 NCBI FTP 端点的 series matrix 于 2026-09-21 13:16:35 UTC 重新下载；下载文件与仓库副本 SHA-256 完全一致：`1e152aa1f40ec38add896ca31a932b929d207aba84deac8a84c2f356382beeeb`。GEO 页面说明样本为手工分选的 GFP/YFP 阳性细胞，并标注 adult small-PDF 组是三重复规则的例外。

Sh 的 Elav-GAL4 样本说明了合并错误：

| 分组 | n | 平均 probe signal | SD |
|---|---:|---:|---:|
| 旧汇总（adult + larva 合并） | 6 | 6.6637 | 3.4368 |
| adult（修正后） | 3 | 9.7827 | 0.3659 |
| larva（修正后） | 3 | 3.5447 | 0.4581 |

这些是 GEO 处理后 probe signal 的描述性汇总，不是统计检验，也不能被解释为已证明的发育阶段效应。adult small-PDF 的 Sh 仅有两个样本，需谨慎看待。所有样本的 time 字段均为 unknown；该数据集是细胞类型表达谱，而非昼夜时间序列，不能用于判定转录节律，也不是离子电流或膜电位证据。

## 验证记录

- 聚焦单元测试：3/3 通过；包含合成数据回归测试与对 GSE17803 原始矩阵的整合测试。
- 全仓库测试：306/306 通过。
- GSE17803 provenance manifest：7 个文件、2 个运行步骤，`verified_public_dataset_manifest`。
- GSE17803 隔离重放：2 个运行步骤、4 个输出哈希均匹配，`verified_public_dataset_replay`。
- 因共享提取脚本更新，GSE22308 canonical 样本级/汇总表及来源清单哈希已同步更新；其清单验证通过，5 步隔离重放及 7 项输出哈希均通过。
- 此轮之外的独立盲测对 GSE22308 另用 input-only manifest 重跑，不读取旧 rhythm/inference 结果；详见本轮任务结尾总结。
