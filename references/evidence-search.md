# 文献检索与证据规范

## 检索顺序

1. 先把问题拆成 organism、cell type、gene/channel、phenotype/readout、circadian condition 和 intervention。
2. 为 s-LNv、l-LNv、LNd、DN 生成全称、历史名称和常见拼写变体；为 gene/channel 同时使用 current symbol、synonyms、family name 和 mammalian ortholog。
3. 不限起始年份。优先原始研究与近五年综述，但通过综述和 reference chaining 找回经典论文。
4. 先检索 PubMed 与 FlyBase，再检索 Google Scholar、bioRxiv 及可访问的 Web of Science 或 Scopus。
5. 按问题扩展到 Fly Cell Atlas、GEO/SRA、单细胞数据门户、Janelia FlyLight 和 connectome 资源。
6. 涉及 stocks 时改用 `genetics-and-stocks.md` 的来源与验证规则。

## 官方入口

- PubMed: https://pubmed.ncbi.nlm.nih.gov/
- FlyBase: https://flybase.org/
- Google Scholar: https://scholar.google.com/
- bioRxiv: https://www.biorxiv.org/
- NCBI GEO: https://www.ncbi.nlm.nih.gov/geo/
- NCBI SRA: https://www.ncbi.nlm.nih.gov/sra
- Fly Cell Atlas: https://flycellatlas.org/
- Janelia FlyLight: https://www.janelia.org/project-team/flylight

入口只是路由提示。每次使用时重新核对页面是否有效、记录检索日期，并直接链接到支持该陈述的 gene、stock、paper 或 dataset 页面。

## 查询覆盖

至少覆盖以下组合，并在结果中保存实际查询式：

- `(Drosophila OR fruit fly) AND (s-LNv OR small ventral lateral neuron ...) AND channel`
- `gene symbol/synonym AND electrophysiology/current/membrane potential/firing`
- `gene symbol/synonym AND circadian/rhythm/ZT/CT/clock/sleep/locomotor`
- `cell type AND RNA-seq/single-cell/transcriptome/proteome`
- `ortholog AND SCN/circadian neuron/electrophysiology`，仅作为跨物种间接证据

不要只依赖摘要。对决定候选排名、实验方向或药理条件的论文读取全文方法、图、补充材料和限制；无法读取全文时降低置信度。

## 证据表

每条记录至少包含：

| 字段 | 内容 |
|---|---|
| Claim | 一项可核查陈述 |
| Evidence label | 直接证据 / 间接证据 / 推断 / 未检索到 |
| Organism / cell | 物种与细胞类型 |
| Assay / condition | 方法、ZT/CT、LD/DD、性别、日龄等 |
| Result | 定性结论及必要效应量 |
| Source | DOI、PMID 或数据库直达链接 |
| Publication status | peer reviewed / preprint |
| Limitations | 不能支持什么 |
| Accessed | YYYY-MM-DD |

将“没有找到”限定为本次查询覆盖范围内的结果。记录数据库、检索式、日期、筛选数量、纳入或排除理由和全文可用性。

## 引用格式

正文使用编号引用。参考文献尽量输出 Nature 风格：

`Author, A. A. et al. Article title. Journal volume, pages (year). DOI`

联网核对作者、标题、期刊、年份、卷页、DOI 或 PMID。预印本明确标注服务器与版本或日期。不要生成未核实的 DOI、PMID 或页码。
