# End-to-end pre-analysis bundle gate

在 cosinor、药理效应或膜电位分析前，把三类输入作为一个 bundle 审核：

1. experiment metadata/sample sheet；
2. raw-QC/provenance manifest；
3. derived measurement table。

`scripts/validate_preanalysis_bundle.py` 先调用 metadata/raw-QC gate，再检查 derived measurement 的 `record_id`、`metadata_row_id`、`biological_replicate_id` 是否有对应记录。每个 `qc_status=pass` raw record 至少要有一条派生测量；excluded/pending/orphan 记录不能进入分析。输出报告行守恒、孤儿记录、输入哈希和各层 gate 状态。

这只是输入完整性与 provenance gate，不代表派生量的物理单位、细胞身份、通道选择性、节律或因果结论已验证。
