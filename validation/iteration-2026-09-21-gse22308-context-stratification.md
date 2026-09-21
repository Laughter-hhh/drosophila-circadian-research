# Iteration 2026-09-21: preserve sex and developmental-stage strata

## Failure found

The GEO expression extractor already retained sex metadata, but the descriptive rhythm and exploratory cosinor analyzers grouped samples only by gene, cell type, and genetic background. Consequently, records from different sexes or developmental stages could be pooled into one analysis without warning. A focused synthetic check with 2 sexes × 2 stages × 4 Zeitgeber times (16 samples) yielded one mixed group before the fix instead of four independent context groups. A real GSE22308 join also exposed equivalent source labels written as `male and female` versus `male_and_female`.

## Change

- Both analyzers now stratify by gene, cell type, genetic background, developmental stage, and sex; missing context is kept in an explicit `unknown` stratum.
- Conflicting context labels for a repeated sample ID are rejected. In the cosinor join, case and whitespace/underscore variants are treated as equivalent for comparison only; the original source value is preserved in output.
- Regression tests cover synthetic sex × stage separation, conflicting sample metadata, metadata fill/mismatch, and GSE22308 labels. The skill and GEO/cosinor references now document these rules.

## Verification

- Full test suite: **314 tests passed**.
- Canonical GSE22308 manifest: 16 files and 8 runs verified; isolated replay verified 11 output hashes.
- Independent, versioned context-stratified forward manifest: 9 files and 4 runs verified; isolated replay verified 6 output hashes.
- Synthetic fixture: 16 samples resolve to 4 distinct sex × stage groups in both analyzers.
- Canonical candidate-expression screen: 60 context-stratified groups; 15 had enough time points for an exploratory 24-hour cosinor and 45 were reported as insufficient (two unique time points).
- Channel-regulator screen: 76 groups; 19 had enough time points and 57 were insufficient. No tested amplitude had BH-adjusted q < 0.05 (minimum q = 0.1424).
- Independent context-stratified forward analysis: 60 descriptive groups; 15 inferential cosinor groups, with no BH-adjusted q < 0.05 (minimum q = 0.0899).

## Interpretation limits

These are exploratory results from the public GSE22308 expression matrix, not evidence that a channel causes a neuronal electrical or behavioral rhythm. The dataset's sampling and lighting design do not establish an endogenous free-running rhythm; expression measurements do not establish channel protein abundance, membrane localization, or current. Groups with two unique time points are explicitly not rhythm-tested. The reports retain this limitation and separate descriptive fitting from inferential testing.

The skill-creator `quick_validate.py` check remains unavailable in this runtime because PyYAML is not installed; the existing skill frontmatter was checked manually. This does not affect the passing Python tests or dataset manifest/replay checks.
