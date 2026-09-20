# 元数据与数据字典

## 使用原则

元数据是结果解释的一部分。缺失 `sex`、`age`、`temperature`、`LD/DD`、`ZT/CT`、`genotype` 或 biological replicate 时，不要默默填入默认值；先标记未知，必要时设计信息获取实验。

## 果蝇昼夜节律最小字段

| 字段 | 例子 | 影响 |
|---|---|---|
| species/strain | `Drosophila melanogaster`, `w1118` | 物种和遗传背景 |
| genotype | 完整 genotype | driver、RNAi、阳性/阴性对照 |
| sex | female/male/unknown | 性别差异 |
| age_days | 5 | 发育和生理状态 |
| temperature_C | 25 | 通道动力学和发育 |
| lighting | LD 12:12 或 DD | 光输入和相位定义 |
| ZT_or_CT | `ZT2`, `CT14` | 时间匹配 |
| dissection_time | 日期和 ZT/CT | 取材偏差 |
| preparation | whole brain、ex vivo 等 | readout 的生物学边界 |
| experimental_unit | fly/brain/cell | 独立性和统计模型 |
| biological_replicate_id | fly 或 brain ID | 避免伪重复 |
| technical_replicate_id | trace/image/library | 技术重复层级 |
| batch_id | recording/imaging/library batch | 批次效应 |
| treatment | 药物、RNAi、光遗传等 | 干预定义 |
| concentration_and_vehicle | 数值、单位、vehicle | 剂量和对照 |

## 数据字典检查

对每个输入表记录：

1. 文件路径、哈希或版本；
2. 行代表什么，列代表什么；
3. 单位、量纲和转换；
4. 缺失值编码；
5. 重复层级和嵌套关系；
6. 排除标准是否在分析前定义；
7. 哪些列来自原始测量，哪些列是派生变量。

## 统计单位提醒

- 多个细胞来自同一只 fly 时，不能把细胞直接当作独立动物；考虑以 fly 为单位汇总或使用嵌套/混合模型。
- 多个 ROI 来自同一细胞时，先定义 ROI 层级，不能把 ROI 数量当生物学 n。
- 多个 library 来自同一动物时，library 是技术重复，动物仍是生物学单位。
- 多个 cage 的行为数据应记录 cage 作为可能的随机或批次因素。

## 缺失字段的处理

低影响字段可以暂时写 `unknown` 并继续探索性分析；会改变解释的字段应阻止正式方案。每个 unknown 都要给出最小获取方式，例如查原始实验记录、重新核对时间戳或做小规模校准实验。
