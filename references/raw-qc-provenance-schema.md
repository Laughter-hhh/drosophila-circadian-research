# Raw electrophysiology/imaging QC and provenance

原始 trace 或 image 在进入节律、药理或膜电位效应分析前，必须能回到具体文件、metadata row 和 biological replicate。`scripts/validate_raw_qc_provenance.py` 支持 `ephys` 与 `imaging` 两种 manifest。

## Common fields

`record_id`, `raw_file_path`, `raw_file_sha256`, `metadata_row_id`, `biological_replicate_id`, `experimental_unit`, `assay`, `cell_type`, `cell_identity_method`, `qc_status`, `exclusion_reason`, `blinding_status`, `derived_output_path`。

## Ephys QC fields

`seal_MOhm`, `access_resistance_MOhm`, `holding_current_pA`, `baseline_drift_mV_per_min`, `sampling_rate_Hz`。

## Imaging QC fields

`roi_count`, `motion_qc`, `focus_qc`, `signal_to_noise`。

`raw_file_sha256` 必须是实际文件的 SHA-256；未附 raw file 时应明确标记 `file_status=not_attached` 或阻断，而不是填入猜测哈希。`qc_status=excluded`/`fail` 必须有 exclusion reason。校验通过只表示 provenance/QC 字段可审计，不表示细胞身份、通道选择性、节律或因果关系成立。
