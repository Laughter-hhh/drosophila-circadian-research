# 公开数据 provenance manifest

真实公开数据分析除了文件 SHA-256，还应保存 accession、来源 URL、下载/整理时间、分析上下文、脚本版本、实际命令、输入和输出之间的关系。使用 `scripts/validate_public_dataset_manifest.py` 审核这些字段。

## 必需内容

manifest 以仓库根目录为路径基准，至少包含：

- `manifest_id`、`dataset_id`、`accession`、`species`、`source_url` 和带时区的 `retrieved_at_utc`；
- `source_access_status`：`content_checked`、`identifier_checked`、`not_checked` 或 `blocked`；如果是 `content_checked`，还必须记录带时区的 `source_checked_at_utc`、`source_check_method`、非空 `source_observed_tokens` 和 `source_observation_note`；
- `analysis_context`：`time_system`、`experimental_unit`、`normalization_status` 和 `biological_unit_limitations`；
- `files`：每个输入、annotation、metadata、candidate list 和 derived output 的相对路径、角色和 SHA-256；
- `runs`：每次执行的 `run_id`、脚本相对路径、脚本 SHA-256、供人阅读的完整 `command`、机器可重放的 `command_argv` 字符串数组、输入/输出路径和 `executed`/`verified` 状态。`command_argv` 的首项只能为 `python`/`python3`，第二项必须等于该 run 的脚本路径；路径必须相对且不得含 `..`、盘符或 NUL。

清单 gate 会实际重算文件和脚本哈希、阻止绝对路径和 `..` 路径、检查 `command_argv` 的安全 launcher/脚本对应关系、检查 run 的输入输出是否在 manifest 中登记，并保证输出角色与记录一致。`metadata` 可以是 parser 的合法输出，不必强行标成 `derived`。

## 运行

```powershell
python scripts/validate_public_dataset_manifest.py validation/public-data/GSE22308-provenance-manifest.json --root . --output validation/GSE22308-provenance-validation.json
```

`verified_public_dataset_manifest` 只表示本地文件完整性和 provenance linkage 通过；`content_checked` 还表示声明的在线观察凭据通过 schema，不表示网页永久不变。若 `source_access_status` 不是 `content_checked`，formal 状态仍为 `conditional_online_source_access`。该 gate 不证明 normalization、cell identity、biological representativeness、统计有效性或因果关系。





## 隔离重放（对 `executed`/`verified` 的分析）

清单结构与本地哈希通过后，任何需要标记为 `executed` 或 `verified` 的公开数据分析还应运行隔离重放：

```powershell
python scripts/replay_public_dataset_manifest.py validation/public-data/GSE22308-provenance-manifest.json --root . --timeout-seconds 120 --output validation/GSE22308-replay-validation.json
```

重放器只执行经过审阅的仓库脚本白名单，绝不解析或执行人类可读的 `command` 字符串；它在临时镜像中复制脚本和已登记的非派生产物，按 `command_argv` 逐项执行，并将每个声明 output 的 SHA-256 与清单逐项比对。只有 `verified_public_dataset_replay` 可证明**当前脚本、当前输入和声明参数**能产生同一输出哈希；任何路径、launcher、脚本白名单、退出码或哈希不符都会阻断。

该检查仍不能证明 raw-data normalization 合理、pool/cell identity 代表个体 fly、统计模型充分，或基因/离子通道存在因果作用。每次重放报告都是运行记录，不是生物学结论。



