# Mixed-model runtime sources

These are primary runtime references for the emitted templates. They document API/formula syntax, not biological validity of any particular analysis.

- Python `statsmodels.MixedLM`: https://www.statsmodels.org/dev/generated/statsmodels.regression.mixed_linear_model.MixedLM.html
- R `lme4::lmer`: https://lme4.github.io/lme4/reference/lmer.html
- MATLAB `fitlme`: https://www.mathworks.com/help/stats/fitlme.html

The templates use a fixed-effects cosinor (`cos24`, `sin24`) plus measured covariates and an intercept grouped by `biological_replicate_id`. Runtime documentation does not replace the skill's metadata, estimand, convergence, residual-QC and causal-interpretation gates.
