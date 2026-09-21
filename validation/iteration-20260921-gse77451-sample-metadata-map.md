# Iteration — validate GEO sample-to-time mapping before expression rhythms

Date: 2026-09-21
Status: verified for synthetic mapping guards, all 36 real matrix-to-GEO mappings, manifest validation and isolated replay. This is metadata alignment, not a rhythm or expression result.

## Trigger

The previous GSE77451 pass established that the processed matrices are transcript-level and contain multiple transcript rows per candidate gene/sample. It intentionally did not map matrix sample columns to GEO metadata or time. A rhythm fit must not infer ZT from adjacent labels or column order, so the next gate verifies each mapping against official NCBI family SOFT records.

## Changes

- Added `audit_geo_sample_map.py`, which verifies matrix-column coverage, unique GSM mapping, explicit alias-to-official-title matches, GEO source/type, ZT/CT, and two complete six-point four-hourly courses per matrix. It exports metadata while retaining pooled-library and missing animal/sex/age/genotype/temperature limitations.
- Added the official NCBI GSE77451 family SOFT file and a 36-row explicit map for the LNv, LNd and DN1 processed matrices.
- Added four synthetic tests for a valid mapping, swapped GSM IDs, missing columns and duplicate timepoints; routed the gate in `SKILL.md` and the GEO workflow; added it to the constrained replay allowlist.

## Current public-data execution

The script parsed 48 sample records from the family SOFT file and matched all 36 processed-matrix columns to 36 unique GSM accessions. Each LNv/LNd course maps ZT2, 6, 10, 14, 18 and 22; each DN1 course maps ZT3, 7, 11, 15, 19 and 23. The metadata output labels experimental units as pooled neuron libraries, keeps individual-fly identity unknown, and does not inspect expression values or test rhythmicity.

## Verification

- Synthetic mapping tests: 4 passed (valid map, swapped GSM/title, unmapped matrix column, duplicate timepoint).
- Public data: 48 family SOFT records parsed; 36/36 selected matrix columns map to unique GEO samples; three matrices each have two complete six-point courses.
- Manifest: verified, 7 files / 1 run / zero issues.
- Isolated replay: verified, 1 run / 2 output hashes / zero issues.
- Full unittest suite: 282 passed.
- Task contract validator: passed.

## Interpretation boundary

The timecourse IDs are curator-assigned labels derived from the publication's two independent courses and GEO sample-title blocks; they are not native GEO fields. This is a sample-metadata alignment result, not expression, channel function, or causal evidence. The downloaded files do not identify individual flies, and the pooled cell groups do not resolve the requested s-LNv/l-LNv or all DN subtypes.

## Sources

Abruzzi, K. C. et al. RNA-seq analysis of Drosophila clock and non-clock neurons reveals neuron-specific cycling and novel candidate neuropeptides. *PLoS Genet.* **13**, e1006613 (2017). https://doi.org/10.1371/journal.pgen.1006613.

NCBI GEO. GSE77451 family record and sample-level SOFT metadata: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE77451.
