# 在线来源可达性、人工核查与 formal gate

在报告 FlyBase、BDSC、VDRC、NIG-Fly、PubMed、PMC、GEO 或原始论文入口前，把“有 URL”与“页面内容已经核实”分开。

## 自动检查

输入 CSV 至少包含 record_id、source_url、expected_tokens。运行：

    python scripts/check_source_access.py validation/public-data/stock-source-access.csv --output validation/stock-source-access-validation.json

脚本记录最终 URL、HTTP status、Content-Type、字节数、正文 SHA-256、匹配 token 和耗时，但不保存网页正文。

## 报告 schema

在 stage gate 前验证 JSON：

    python scripts/validate_source_access_report.py validation/stock-source-access-validation.json --output validation/stock-source-access-report-validation.json

每条记录至少需要 record_id、source_url 和 access_status。自动验证的 reachable_content_verified 记录还必须有成功 HTTP status、matched_tokens 和 body_sha256。

如果网站返回 challenge/login/dynamic 页面，记录应为 reachable_content_unverified，不能进入 formal cross。

## 人工浏览器核查

当自动请求无法读取页面时，可创建同一 JSON schema 的人工记录：

- access_status=reachable_content_verified；
- verification_method=browser_manual；
- checked_at_utc 为 ISO 时间；
- observed_tokens 非空；
- observation_note 说明浏览器实际看到的 identifier 或 genotype 字段。

人工核查报告仍只证明页面级观察，不证明背景纯合度、driver expression、当前库存或生物学功能。

## 状态边界

- verified_source_access：自动或人工记录结构通过，且记录达到内容核查门槛；
- conditional_source_access：页面可达但 token 未匹配；
- blocked_source_access：HTTP 错误、网络错误或 manifest 无效；
- verified_source_access_report：JSON schema 通过，不等于所有记录都达到 verified；
- stage gate 只有在目标候选记录为 reachable_content_verified 时才允许 formal。

formal stage gate：

    python scripts/validate_genetic_stage_gate.py plan.csv --stock-audit stock-audit.csv --source-access-report source-access.json --output gate.json

integrated cross plan：

    python scripts/validate_integrated_cross_plan.py cross-plan.csv --stock-audit stock-audit.csv --source-access-report source-access.json --output integrated.json

HTTP 状态、token 匹配或人工 observation 都只支持来源追溯性；不能独立证明 genotype、库存、药理选择性、剂量或因果结论。
