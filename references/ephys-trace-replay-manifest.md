
# 可重放 ephys trace pipeline manifest

当需要把全细胞膜片钳或成像的 normalized trace CSV、raw-QC、派生测量和探索性分析标为 `executed` 或 `verified` 时，使用下列两个脚本：

```powershell
python scripts/validate_ephys_trace_replay_manifest.py validation/synthetic-ephys-trace-replay-manifest.json --root . --output validation/ephys-trace-manifest-validation.json
python scripts/replay_ephys_trace_manifest.py validation/synthetic-ephys-trace-replay-manifest.json --root . --timeout-seconds 120 --output validation/ephys-trace-isolated-replay.json
```

## manifest 约束

- `analysis_context` 必须声明 species、ephys assay、experimental unit、ZT/CT 和 scientific status。
- 每个 raw binary、normalized trace CSV、metadata、raw-QC、derived table 与报告都必须列出相对路径、角色与 SHA-256。
- `raw_qc` 中每个 `file_status=present` 的 `raw_file_path` 必须相对 raw-QC CSV，自身不能有盘符、绝对路径、NUL 或 `..`；解析后的 raw file 必须位于仓库内，并在 manifest 中登记相同 SHA-256。
- 每个 run 使用结构化 `command_argv`；仅允许受审阅的 metadata/QC/trace-derivation/bundle/cosinor 脚本和 `python`/ `python3` launcher。
- 需要 `--provenance-root .`，使所有报告记载仓库相对路径，因而可在隔离临时镜像中按 output hash 重放。

## 解释边界

`verified_ephys_trace_replay` 只证明已登记的合成或已附原始输入，使用当前脚本和参数时能重新得到相同的 QC、测量与分析文件。它不证明 vendor binary 已被正确解码（本 workflow 要求预先导出 normalized CSV）、cell identity、通道选择性、膜电位节律、统计充分性或因果关系。

对于真实项目，先保留原始 ABF/CED/TIFF 的只读副本及其 hash，再导出 normalized CSV；不要将 raw file、细胞、ROI 或技术重复的数量误当作 biological n。正式结论仍须通过 biological-unit-aware mixed-effects workflow、预先定义的 contrasts 与独立重复。



