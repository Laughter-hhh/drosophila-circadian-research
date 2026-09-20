#!/usr/bin/env Rscript
args <- commandArgs(trailingOnly = TRUE)
table_path <- if (length(args) >= 1) args[[1]] else "nested_aggregated.csv"
manifest_path <- if (length(args) >= 2) args[[2]] else "nested_manifest.json"
if (!requireNamespace("jsonlite", quietly=TRUE) || !requireNamespace("lme4", quietly=TRUE)) stop("BLOCKED: require jsonlite and lme4")
manifest <- jsonlite::fromJSON(manifest_path)
if (!identical(manifest$status, "ready_for_mixed_model")) stop("BLOCKED: mixed-model manifest is not ready")
dat <- read.csv(table_path, check.names = FALSE)
dat$cos24 <- cos(2*pi*dat$time_hours/24)
dat$sin24 <- sin(2*pi*dat$time_hours/24)
fit <- lme4::lmer(value ~ cos24 + sin24 + factor(batch_id) + factor(sex) + age_days + factor(genotype) + temperature_C + factor(lighting) + (1|biological_replicate_id), data=dat, REML=TRUE)
print(summary(fit))
print(lme4::isSingular(fit, tol=1e-4))
