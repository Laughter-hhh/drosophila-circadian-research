# Candidate evidence live-web check — 2026-09-07

This is a targeted online verification of the highest-priority candidates and one driver stock. It supplements, but does not silently rewrite, the broader candidate evidence table.

## Source-backed observations

| Candidate or resource | Online source | Checked fact | Evidence boundary |
|---|---|---|---|
| `Shaw` | [PMID 31612994](https://pubmed.ncbi.nlm.nih.gov/31612994/) | The paper reports circadian Shaw currents in Drosophila LNvs, clock-dependent changes in excitability, and dynamic-clamp rescue of the pharmacological block. | Direct LNv physiology; this does not by itself identify the exact RNAi stock or prove every target subset. |
| `Shal` | [PMID 31612994](https://pubmed.ncbi.nlm.nih.gov/31612994/) and [PMID 30185460](https://pubmed.ncbi.nlm.nih.gov/30185460/) | The sources report circadian Shal/Kv4 current contributions in LNvs; the sleep-onset study specifically discusses l-LNv A-type currents and time-of-day effects. | Direct/near-direct LNv physiology; cell-subset and reagent details remain experiment-specific. |
| `Irk1` | [PMID 35303418](https://pubmed.ncbi.nlm.nih.gov/35303418/), [PMC8972083](https://pmc.ncbi.nlm.nih.gov/articles/PMC8972083/), [FlyBase FBgn0265042](https://flybase.org/reports/FBgn0265042) | The WNK–Fray pathway is linked to Irk1 activation and circadian-period control in sLNv pacemakers; cultured-cell patch clamp and in-vivo replacement are separate evidence tiers. FlyBase currently lists the gene as `Irk1`/`CG44159`. | Near-direct for native current mechanism; cultured-cell electrophysiology must not be relabelled as native s-LNv current. |
| `na`/`NALCN` | [PMID 26276633](https://pubmed.ncbi.nlm.nih.gov/26276633/) and [PMID 28634443](https://pubmed.ncbi.nlm.nih.gov/28634443/) | The sources connect sodium leak/NALCN-related conductance, Nlf-1, pacemaker excitability and behavior; developmental versus adult contributions are explicitly a boundary. | Direct/near-direct pacemaker evidence, but exact target-subset and adult-restricted reagent interpretation still require local validation. |
| `Pdf-GAL4` stock | [FlyBase FBst0080939](https://flybase.org/reports/FBst0080939) | FlyBase lists BDSC stock `80939`, a living stock, and the genotype `y[1] w[*]; P{w[+mC]=Pdf-GAL4.P0.5}2; P{w[+mC]=Pdf-GAL4.P0.5}3`. | Identity and listed genotype are source-backed; background purity, expression in the exact experiment, and local stock health remain unverified. |

## Not established by this check

- Current availability or exact genotype of every RNAi/replacement stock in the top-4 plan.
- Genetic background matching, insertion direction, knockdown efficiency, rescue specificity or adult-only restriction in the user’s planned crosses.
- A direct native-channel current measurement in every requested neuron class (`s-LNv`, `l-LNv`, `LNd`, `DN`).

## Use in ranking

These online checks support retaining `Shaw`, `Shal`, `Irk1` and `na` in the evidence long list, while preserving the existing conditional/formal gates. They do not authorize a formal cross or a causal claim; the stock audit and genetic-stage gate remain required.
