# 全细胞膜片钳与膜电位实验 QC

## 记录前

明确 cell identity、driver/split-GAL4、遗传背景、sex、age、temperature、LD/DD、ZT/CT、培养时长、内外液组成、pH/osmolality、药物和 vehicle。记录 acquisition software、sampling rate、filter、series compensation 和 liquid-junction-potential 处理。

## 每个细胞或 trace 的最小 QC

| 类别 | 必须保存 | 失败时的处理 |
|---|---|---|
| seal | seal resistance、形成时间 | 未达到预设阈值则排除并记录原因 |
| access | access resistance、稳定性 | 漂移超阈值时停止或标记 trace |
| membrane | capacitance、input resistance、resting potential | 与预注册范围比较，不用事后挑选 |
| current | holding current、leak、series error | 保存原始 trace 和修正方法 |
| stimulation | voltage/current step、间隔、持续时间 | 记录是否触发 adaptation 或 rundown |
| drug | compound、浓度、溶剂、灌流、起效、洗脱 | 不能把未洗脱的状态当作可逆阻断 |
| timing | 记录开始和结束的 ZT/CT | 只在预设时间窗内合并 |
| health | membrane rupture、blebbing、movement、baseline drift | 用预设排除标准处理 |

## 离子通道阻断的解释边界

急性药理阻断可以探索 `channel activity → membrane potential/current`，但药物特异性、浓度依赖、off-target、补偿性变化和细胞状态必须单独列出。单一药物产生的差异不能直接证明某个基因是唯一分子来源。

阳性结果优先用独立药物、RNAi/knockdown、rescue 或电流动力学特征进行正交复核；RNAi 结果要关注发育影响和 knockdown 效率。

## 昼夜实验设计

预先定义 ZT/CT 采样点、每个时间点的 fly 数、每只 fly 的细胞数上限、记录顺序、实验日和批次平衡。不能把不同温度、不同光照历史或不同记录日的样本仅按 clock time 合并。

## 推荐输出

至少保存原始 trace、去标识化元数据、每细胞 QC 表、派生电流/电压表、排除列表、药物时间线、统计脚本和代表性图。群体统计同时报告每只 fly 的分布，避免只展示代表性细胞。
