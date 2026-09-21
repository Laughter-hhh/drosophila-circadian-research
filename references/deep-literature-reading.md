# 双语深度文献阅读

## 适用模式

当用户要求精读论文、解释每个 Figure、看不懂图注或技术方法、需要作者团队历史背景，或明确要求中英双语时，进入本模式。默认把读者当作没有生物学基础的学生：第一次出现的术语先用通俗中文解释，再给 English term、缩写和技术定义。不要因为用户是科研人员就省略基础解释。

输出采用中英双语并行结构。每个主要章节先写 **中文｜English**；表格至少提供中英文列名或在同一单元格中并列。gene symbols、genotypes、技术名称、统计符号和 Nature 风格参考文献保留英文标准写法。

## 读取与核查

1. 优先读取用户上传的全文 PDF、补充材料、高清 Figure 和原始图注；没有全文或图像不清时，明确列出不能核实的部分，不凭标题或摘要补图。
2. 联网核对文章题目、作者、期刊、年份、DOI/PMID、版本和图表编号；记录检索日期及直接链接。
3. 检索文章的参考文献链、作者实验室或机构主页、ORCID/PubMed 作者记录、同团队前后续论文和使用的关键技术。团队背景只报告有来源的事实。
4. 对“为什么做这篇文章”“为什么此时能发表”分开写：来源支持的事实标为结论，依据时间线与研究缺口提出的解释标为推断，并列出替代解释；不要猜测作者未公开的动机、审稿过程或经费细节。
5. 预印本、非果蝇物种和方法论文单独标记；学位论文只在用户主动上传时使用。沿用 `evidence-search.md` 的证据分级、检索日志和 Nature 引用规则。

**全文与图像的有限回退顺序**：先检查用户提供的全文、图像和补充材料；再查出版社的全文/图像页面及作者或机构仓储中的 accepted manuscript；再查可访问的文章 HTML、正式 figure 页面或补充文件；最后才使用可索引的图注文本。每一步记录尝试过的来源、版本、是否可访问及其提供的材料类型。索引图注或摘要只能支持 caption-/abstract-level 解读，不能当作看过原图。完成这几类来源检查后仍拿不到图像或补充材料，就停止声称视觉核验，并把相应内容标为不可核实；不要无上限地反复搜索，也不要从二手文字推造图中信息。

## 固定解读框架

### 1. Article map｜文章地图

用不超过数段先给：一句话主旨、研究对象、核心问题、核心方法、最重要发现、结论强度和仍未解决的问题。随后给一张双语导航表：

| 中文 | English |
|---|---|
| 研究对象与模型 | Organism, preparation, cell type |
| 核心问题 | Central question |
| 工作假说 | Working hypothesis |
| 关键 readouts | Primary and secondary readouts |
| 证据链 | Evidence chain across figures |
| 结论边界 | What the paper does and does not establish |

### 2. Historical and team context｜历史与团队背景

按时间线说明：

- 该问题在领域中原来知道什么、争议在哪里；
- 该团队近年的研究方向、关键模型和技术积累；
- 本文承接了团队或领域中的哪一项结果；
- 哪个技术、数据集、遗传工具或实验条件使本文问题变得可回答；
- 发表本文的合理起因和条件。

每项分开列 `source-backed fact｜有来源事实` 与 `inference｜推断`。如果没有公开证据，写 `not established｜未建立`，不要用叙事填空。

### 3. Introduction/background/research gap｜引言、背景与研究缺口

逐段压缩而不丢逻辑：

1. 已知事实及其证据。
2. 关键概念与术语表。
3. 领域未解决的问题或矛盾结果。
4. 作者提出的 research gap。
5. 假说、预测和每个预测对应的 Figure/experiment。

对每个关键术语使用三层解释：`通俗比喻 → 一句话技术定义 → 本文中的具体含义`。明确区分作者声称的背景与本文真正测量到的事实。

### 4. Results｜结果（最详细部分）

按 Figure 顺序逐一处理主文和必要的 Supplementary Figures。不得跳过任何子图（例如 a–f、A–D、左/右 panel、inset 或 representative trace）。每个 Figure 都使用以下模板：

#### Figure X｜图 X

在图题或文章摘要处醒目标明本次 Figure 覆盖状态：`image-verified｜已核查原图`、`caption-limited｜仅图注解读` 或 `source-unavailable｜来源不可访问`。每个 panel 单独记录访问状态与证据来源；一个可读图注不能使同图其他不可见 panel 自动变成已核查。

1. **Figure question｜本图问题**：这张图想区分什么假说或获得什么信息。
2. **Caption walkthrough｜图注逐项解读**：逐句解释图注中实验对象、干预、时间条件、颜色或线型、统计、误差线、n、比例尺和 panel 关系。用自己的话翻译和解释，不大段逐字复制受版权保护的图注。
3. **Panel inventory｜子图清单**：主文及所需补充图的每个 panel、inset 和 representative trace 各占一行，记录 `panel_id`、caption/image 状态、所依据的版本/页面/直接链接、可见或可从图注核实的轴与单位/组别/符号、无法检查的视觉项目。可用 `unknown｜未知` 或 `unavailable｜不可访问`；不得用同图其他 panel 的信息填补。轴、颜色、线型、比例尺、代表性 trace 或图中文字若只能从图像判断，只有实际查看原图后才能描述。
4. **Abbreviation and symbol glossary｜缩写与符号表**：

   | Abbreviation/symbol | Full English | 中文 | In this panel |
   |---|---|---|---|

   覆盖所有图注中出现且影响理解的字母、单词、缩写、基因名、细胞类型、ZT/CT、n、p、星号、error bars、scale bar、颜色和线型；不要假设读者知道常见符号。图像不可访问、因此无法辨认的 artwork-only 标签须逐 panel 标为未知，不能依靠记忆补全。

5. **Principle｜实验原理**：用零基础语言解释为什么该 assay 能测量目标变量、信号来自哪里、关键对照排除什么；再给一段技术层面的原理或必要公式与定义。
6. **Example｜具体示例**：挑一个点、trace、细胞或组别，演示如何从图上读出方向、大小、时间或空间关系；必要时用日常比喻，但明确比喻不是数据。
7. **What the data show｜数据实际显示什么**：只描述可直接从图或统计结果支持的观察，区分代表性图像与群体定量。
8. **Conclusion｜本图结论**：说明该结果支持、削弱或不能区分哪些假说，并标注 `direct evidence｜直接证据`、`indirect evidence｜间接证据`、`inference｜推断` 或 `not established｜未建立`。紧邻结论给出 panel-level source/provenance；文末总参考文献不能替代某项图示结论的直接来源。
9. **Caveats｜限制与替代解释**：指出选择性、相关不等于因果、时间采样、样本量、批次、细胞或动物嵌套、统计模型和未测量变量的影响。
10. **Figure-to-figure link｜图间逻辑**：说明本图如何承接前一图、为后一图提供什么前提，以及证据链在哪一处仍断裂。

遇到电生理、钙成像、免疫染色、RNA-seq 或 single-cell 图时，额外解释 signal、normalization、ROI、current/voltage、spike、cluster、marker、differential expression、rhythmic model 等术语，并核对方法部分的定义。不要把“有显著差异”自动翻译成“机制已证明”。

对 `n`、`N`、trials、recordings 等字段，只有原文明确时才说明其代表 fly、brain、cell、culture、animal、独立样本还是技术重复。图注仅列出数字而 methods 不可访问时，写明数字及其单位/experimental unit 为 `unknown｜未知`，并说明需要查看哪一段 Methods 或补充材料才能确认；绝不把细胞数、记录次数或 trials 默认等同于独立动物数。

### 5. Conclusion/discussion｜结论与讨论

分层总结：

- `what is directly shown｜直接显示了什么`；
- `what is a reasonable inference｜合理推断是什么`；
- `what remains unsupported｜仍无证据的部分`；
- `alternative explanations｜竞争解释`；
- `next decisive experiment｜最能区分解释的下一实验`。

把作者的结论与独立评估分成两列，避免复述作者语言造成过度确信。对果蝇结果与跨物种结果分开讨论。

## 记忆友好输出

每个 Figure 最后给一张双语五格卡片：

`Question → Method → Observation → Meaning → Limitation`

中文对应：`问什么 → 怎么测 → 看到什么 → 说明什么 → 还缺什么`。

整篇文章最后提供：

1. 一句话主旨｜one-sentence take-home message；
2. 三句话证据链｜three-sentence evidence chain；
3. 术语和缩写总表｜master glossary；
4. Figure 之间的因果或证据流程图｜figure evidence map；
5. 五个自测题及答案｜five recall questions with answers。

## 交付前检查

- 是否中英双语覆盖所有主要分析，而不是只有标题双语？
- 是否解释每个 Figure 的每一个子图、inset、符号和图注要素？
- 是否说明实验原理、对照、统计、样本量和结果意义？
- 是否区分观察、结论、推断、无证据和替代解释？
- 是否核查作者团队背景与文章历史，而没有臆测作者动机？
- 是否给出全文、图像或补充材料不可得时的明确限制？
- 是否对每个 panel 标注图像/图注访问状态与逐项来源；若仅有图注，标题或摘要是否醒目标为 caption-limited，而非视觉核验？
- 是否把 `n`、trial、recording 和独立 experimental unit 区分；方法未说明时是否保留 `unknown`？
- 是否给出直接链接、Nature 风格参考文献和检索日期？
