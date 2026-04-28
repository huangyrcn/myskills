---
name: paper-resolve
description: >
  Resolve an ambiguous or partial paper reference into a canonical paper identity
  by first determining the canonical title through web search. Use this skill whenever
  the user gives a paper title, DOI, arXiv id, OpenReview URL, paper URL, local PDF,
  or fuzzy paper description and the system first needs to figure out exactly which
  paper it is. Prefer this skill before any paper download, raw acquisition, or note
  generation work.
---

# Paper Resolve

Resolve a user's paper reference into a canonical paper identity.

## Core Task: Determine the Canonical Title

**The first and most important step is to determine the canonical paper title.**

Use web search to find the exact, official title of the paper. This is the foundation for everything else.

## Output Contract

The goal is to determine:

- `canonical_title` — the official paper title (required, from web search)
- `folder_slug` — filesystem identifier: `{venue}{year}-{method}-{first_author}`
- `canonical_url` — primary source URL
- stable identifiers when available (DOI, arXiv, etc.)
- `resolution_confidence`

Do not require DOI or venue to succeed.

## Resolve Workflow

### Step 1: Determine Canonical Title (Three-Search Strategy)

**识别输入类型并添加关键词前缀：**

| 输入类型 | 识别特征 | 关键词前缀 |
|---------|---------|-----------|
| DOI | `10.xxx/xxx` | `doi` |
| PMID | 纯数字（上下文暗示）| `PMID` |
| arXiv ID | `YYMM.NNNNN` 格式 | `arxiv` |
| OpenReview URL | `openreview.net` | 直接用URL，无需搜索 |
| Method name | 短、大写、缩写 | 会话分析提取 |
| 模糊标题 | 其他字符串 | 会话分析提取 |

**第一次搜索：初步发现**

根据输入类型构建搜索：

```bash
# DOI
ask-search "doi {doi}" -e google -n 10

# PMID
ask-search "PMID {pmid}" -e google -n 10

# arXiv ID
ask-search "arxiv {arxiv_id}" -e google -n 10

# Method name / 模糊标题
ask-search "{用户输入}" -e google -n 10

# OpenReview URL — 直接读页面，跳过搜索
crwlr crawl -o md "{openreview_url}"
```

**第二次搜索：深度验证**

分析会话上下文，提取补充关键词：

1. 用户讨论的是什么领域？
2. 用户提到了哪些技术术语？
3. 用户是否提到了期刊/会议？
4. 用户是否提到了作者或机构？

构建搜索：

```bash
ask-search "{关键词前缀} {用户输入} {会话关键词}" -e google -n 10
```

示例：
- DOI + 会话讨论 bioinformatics → `ask-search "doi 10.xxx bioinformatics" -e google -n 10`
- arXiv ID + 会话讨论 GNN → `ask-search "arxiv 2002.05287 graph neural network" -e google -n 10`

**第三次搜索：标题复核**

```bash
ask-search "\"{候选标题关键部分}\"" -e google -n 10
```

**置信度判断**：
- 三次搜索结果一致，多个来源指向同一论文 → high confidence
- 前两次一致，第三次有偏差 → medium confidence
- 结果不一致或有多个候选 → low confidence，需要用户确认

### Step 2: Collect Identifiers (Best Effort)

使用 ask-search 直接指定学术引擎搜索。**以下全部必查**：

| 源 | 引擎名称 | 获取的信息 |
|---|---------|-----------|
| **OpenAlex** | `openalex` | DOI, OpenAlex ID, PMID, PMCID, S2 ID, is_oa, pdf_url, venue, authors, year |
| **Semantic Scholar** | `"semantic scholar"` | S2 ID, openAccessPdf, authors, venue |
| **Crossref** | `crossref` | DOI 官方元数据, publisher, type, container-title |
| **DBLP** | `dblp` | DBLP key, venue（规范）, type, authors |
| **PubMed** | `pubmed` | PMID, PMCID, DOI, authors, venue（生物医学）|
| **arXiv** | `arxiv` | arXiv ID, title, authors, categories, DOI link（预印本）|
| **Google Scholar** | `"google scholar"` | 被引用次数（不存 metadata）|
| **OpenReview** | `google` + `site:openreview.net` | OpenReview ID, reviews, decision, DOI link（会议投稿）|

**注意**：引擎名称含空格时需用引号包裹，如 `-e "semantic scholar"`。

**查询流程（每个源）**：

```bash
# 大部分源直接指定引擎
ask-search "{title}" -e {engine} -n 5

# OpenReview 无专用引擎，用 google + site:
ask-search "site:openreview.net {title}" -e google -n 5
```

**示例**：

```bash
# OpenAlex — 信息最全
ask-search "Neural Message Passing for Quantum Chemistry" -e openalex -n 5

# Semantic Scholar — 有 openAccessPdf
ask-search "Neural Message Passing for Quantum Chemistry" -e "semantic scholar" -n 5

# PubMed — 生物医学论文必查
ask-search "Deciphering spatial domains from spatial multi-omics with SpatialGlue" -e pubmed -n 5

# arXiv — 预印本/ML 论文
ask-search "Neural Message Passing for Quantum Chemistry" -e arxiv -n 5

# DBLP — 计算机/ML 论文 venue 规范化
ask-search "Neural Message Passing for Quantum Chemistry" -e dblp -n 5

# Crossref — DOI 官方元数据
ask-search "Deciphering spatial domains from spatial multi-omics with SpatialGlue" -e crossref -n 5

# Google Scholar — 引用信息（不存 metadata）
ask-search "Neural Message Passing for Quantum Chemistry" -e "google scholar" -n 5

# OpenReview — 会议论文
ask-search "site:openreview.net ICLR 2020 GNN" -e google -n 5
```

**数据映射**：

Read [references/source-metadata-mapping.md](references/source-metadata-mapping.md) for the complete mapping from sources to metadata fields.

**查询顺序建议**：

1. **OpenAlex** — 信息最全，包含 S2 ID、PMID、PMCID
2. **Semantic Scholar** — openAccessPdf 重要
3. **PubMed** — 生物医学论文必查
4. **arXiv** — 预印本/ML 论文，有 LaTeX source
5. **DBLP** — CS 论文 venue 规范化
6. **Crossref** — DOI 验证
7. **OpenReview** — 会议投稿

**交叉验证**：

- 比较各源的 title 是否一致
- 比较各源的 DOI 是否一致
- 不一致时记录 evidence 并降低 resolution_confidence

**无结果处理**：

- 某些源可能没有该论文（如 Nature Methods 论文不在 arXiv/OpenReview）
- 记录为 `null`，不影响整体置信度
- 多个源一致即可确认

### Step 3: Generate folder_slug and Write metadata.yaml

From the collected identifiers (venue, year, authors) and the canonical title, generate the folder slug:

Format: `{venue}{year}-{method}-{first_author}`

- `venue`: lowercase `bibliography.venue` (e.g., "ICLR" → `iclr`); fallback `"preprint"`
- `year`: `bibliography.year`; fallback `"unknown"`
- `method`: acronym or key term from title (e.g., "Geom-GCN: ..." → `geom-gcn`, "Attention Is All You Need" → `transformer`)
- `first_author`: last name of first author, lowercase (e.g., "Thomas Kipf" → `kipf`)

If collision occurs, add suffix (arXiv id, DOI hash, etc.)

Read [references/folder-slug.md](references/folder-slug.md) for details.

Write the resolved identity to:

```text
~/docs/papers/{folder_slug}/metadata.yaml
```

Read [references/metadata-schema.md](references/metadata-schema.md) for the output format.

## Input Normalization

Understand what the user gave:

| Input type | Approach |
|------------|----------|
| Title (fuzzy) | Search → determine canonical title |
| DOI | Direct resolution → confirm title from source |
| arXiv id/URL | Direct resolution → confirm title from arXiv |
| OpenReview URL | Direct resolution → confirm title |
| Publisher URL | Read page → extract title |
| Local PDF path | Check existing ~/docs/papers first |
| Method name | Search method + context keywords → find proposing paper |

### Method Name Detection

If the input looks like a method name (short, capitalized, acronym-like, e.g., "GAT", "BERT", "MManiST"):

1. **Ask for context keywords** (optional but recommended):
   - "This looks like a method name. Any context to help narrow down?"
   - Examples: "graph neural network", "NLP", "spatial transcriptomics", "computer vision"
   - If user provides keywords, search `"{method_name} {keywords}"`

2. **Auto-infer from conversation context** (if user doesn't provide):
   - Recent topics in conversation
   - Project domain (if detectable)
   - Previous papers discussed

3. **Build search queries** (in priority order):
   - Primary: `"{method_name} {context_keywords}"`
   - Fallback: `"{method_name} method paper"`
   - Direct: `"{method_name}"`

4. **Match results**:
   - Title contains the method name
   - Paper introduces/proposes this method
   - Check abstract for "we propose/introduce/present {method_name}"

5. **Set confidence**:
   - High: exact match in title + clear proposal statement
   - Medium: method name in title, need to verify
   - Low: multiple candidates, ask user to confirm

#### Examples

| Method Name | Context | Search Query | Result |
|-------------|---------|--------------|--------|
| "GAT" | graph neural network | "GAT graph neural network" | "Graph Attention Networks" |
| "BERT" | NLP | "BERT NLP" | "Pre-training of Deep Bidirectional Transformers..." |
| "MManiST" | spatial transcriptomics | "MManiST spatial transcriptomics" | "Multi-Manifolds fusing hyperbolic graph network..." |
| "ResNet" | (none provided) | "ResNet method paper" | "Deep Residual Learning for Image Recognition" |

## OpenReview and Preprint Handling

Treat OpenReview and preprint-only papers as first-class cases:

- `venue` may be empty
- `publication_status` may be `submission`, `under_review`, `accepted`, `workshop`, `withdrawn`, or `unknown`

Do not fail resolution only because DOI or venue is missing.

## Resolution Confidence

Set `resolution_confidence` based on evidence quality:

- `high`: exact identifier match, multiple sources agree
- `medium`: title matches well, identifiers partial
- `low`: ambiguous matches, ask user to confirm
