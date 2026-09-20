% Fit the pre-specified random-intercept cosinor with MATLAB Statistics Toolbox.
% Usage: fit_mixed_model('nested_aggregated.csv','nested_manifest.json')
function fit = fit_mixed_model(table_path, manifest_path)
if nargin < 1, table_path = 'nested_aggregated.csv'; end
if nargin < 2, manifest_path = 'nested_manifest.json'; end
manifest = jsondecode(fileread(manifest_path));
if ~strcmp(manifest.status,'ready_for_mixed_model')
    error('BLOCKED: mixed-model manifest is not ready');
end
if exist('fitlme','file') ~= 2
    error('BLOCKED: MATLAB Statistics and Machine Learning Toolbox fitlme is unavailable');
end
dat = readtable(table_path);
dat.cos24 = cos(2*pi*dat.time_hours/24);
dat.sin24 = sin(2*pi*dat.time_hours/24);
dat.batch_id = categorical(dat.batch_id);
dat.sex = categorical(dat.sex);
dat.genotype = categorical(dat.genotype);
dat.lighting = categorical(dat.lighting);
formula = 'value ~ 1 + cos24 + sin24 + batch_id + sex + age_days + genotype + temperature_C + lighting + (1|biological_replicate_id)';
fit = fitlme(dat, formula, 'FitMethod', 'REML');
disp(fit);
end
