# 公开果蝇行为元数据：先审计、后决定是否下载原始录像

公开行为数据经常把小型元数据表和数百 GB 的 Ethoscope 原始录像分开发布。对科研任务而言，先核对小文件的结构和来源，再决定是否承担原始录像的下载、存储和解析成本。

## 工作流

1. 从官方记录页和直接文件链接记录 accession、source URL、核查时间、观察到的物种/文件名/字段 token；不要只保存一个不可回溯的 URL。
2. 下载元数据表后运行：

   ```powershell
   python scripts/audit_public_behavior_metadata.py validation/public-data/zenodo-18214640-20lux-main-dataset.csv `
     --source-url https://zenodo.org/records/18214640 `
     --expected-sha256 1879cb556e1f84a225520b5a4d4689244b7109bfe850261d24dd3137c7fb1008 `
     --provenance-path validation/public-data/zenodo-18214640-20lux-main-dataset.csv `
     --output validation/public-data/zenodo-18214640-20lux-metadata-audit.json
   ```

3. `verified_public_behavior_metadata_audit` 只表示文件哈希、字段布局、唯一键和基础数值格式通过。它不表示有足够信息做行为节律、神经活动或因果分析。
4. 只要 genotype/strain、sex、age、temperature、LD/DD 或 ZT/CT 定义、个体 fly 标识、raw recording checksums 仍缺失，`analysis_readiness` 必须保持 `blocked_metadata_insufficient_for_behavior_analysis`。这时应优先设计信息获取实验或联系数据作者，而不是把 condition/lux/baseline_days 当成完整实验设计。
5. 将输入 CSV、审计 JSON 和运行脚本写入 public-data manifest，运行 `scripts/validate_public_dataset_manifest.py`，再运行 `scripts/replay_public_dataset_manifest.py`。只接受逐项 hash 重现的回放结果作为计算可复现证据。

## 证据层级

- **已核查（verified）**：官方记录页面可访问，局部字段和下载文件 SHA-256 可重算，审计与隔离回放可复现。
- **可推断（inference）**：行键可能对应机器/日期/ROI 记录；必须等待作者协议或 raw 文件确认其是否是独立 fly。
- **无证据（unsupported）**：从 metadata 的 condition、lux 或 baseline_days 单独推断 genotype、性别、年龄、温度、光暗周期、行为振幅/周期，或神经元/离子通道机制。

## 当前 Zenodo 示例

Zenodo 记录 `10.5281/zenodo.18214640` 的官方页面列出了 `20lux_main.dataset.csv` 和大型 Ethoscope 原始归档。skill 仅保留小型元数据文件用于审计；不要把“下载了元数据”写成“已分析行为原始数据”。当前示例的本地审计结果是 190 行、condition A/B/C 各 50 行、D 40 行；由于缺失关键研究元数据，行为分析 readiness 仍为 blocked。

