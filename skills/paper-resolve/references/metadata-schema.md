# Resolve Metadata Schema

The resolve stage owns the identity and bibliographic core of `metadata.yaml`.

```yaml
title: "Geom-GCN: Geometric Graph Convolutional Networks"
title_slug: "geom_gcn_geometric_graph_convolutional_networks"

identity:
  canonical_url: "https://arxiv.org/abs/2002.05287"
  primary_id:
    type: "arxiv"
    value: "2002.05287"
  aliases:
    doi: "10.48550/arxiv.2002.05287"
    arxiv: "2002.05287"
    openreview: null
    openalex: "W2995509042"
    semantic_scholar: "04f3203f1214063436d81ce0c2ad7623204da488"
    dblp: null
    pmid: null
    pmcid: null
  resolution_confidence: "high"
  resolution_evidence:
    - "arXiv title exact match"
    - "OpenAlex and Semantic Scholar agree on the same identifiers"

bibliography:
  authors:
    - "Hongbin Pei"
    - "Bingzhe Wei"
  year: 2020
  venue: "ICLR"
  venue_context: "International Conference on Learning Representations 2020"
  publication_status: "accepted"
  abstract: "..."

urls:
  canonical: "https://arxiv.org/abs/2002.05287"
  pdf: "https://arxiv.org/pdf/2002.05287.pdf"
  doi: "https://doi.org/10.48550/arxiv.2002.05287"
  pmc: null
  openreview: null

# === For paper-acquire ===
acquisition_hints:
  pdf_sources:
    - source: "arxiv"
      url: "https://arxiv.org/pdf/2002.05287.pdf"
      priority: 1
      notes: "Free, no auth required"
    - source: "semantic_scholar"
      url: "https://..."
      priority: 2
  latex_available: true
  latex_url: "https://arxiv.org/e-print/2002.05287"
```

## Notes

- `identity` is the minimum required part for a successful resolve stage
- `bibliography` fields may be partially missing and can be enriched later
- `urls.pdf` may be empty after resolve and filled during acquisition
- `acquisition_hints` helps `paper-acquire` skip search steps

## Fields for paper-acquire

`paper-acquire` uses these fields to directly download without searching:

| 字段 | 用途 |
|---|---|
| `urls.pdf` | 直接下载 PDF |
| `urls.pmc` | PMC 全文 PDF + 可能有 LaTeX |
| `identity.aliases.arxiv` | arXiv PDF + LaTeX source |
| `identity.aliases.pmcid` | PMC 全文 |
| `identity.aliases.doi` | 出版商 PDF（可能付费）|
| `acquisition_hints.latex_available` | 是否有 LaTeX 源码 |
| `acquisition_hints.latex_url` | LaTeX 下载地址 |

## Legacy Compatibility Projection

During migration, the resolve stage also writes a flat compatibility layer so legacy scripts can operate without modification.

### Required compatibility fields

```yaml
# Flat fields derived from identity/bibliography for legacy scripts
authors:
  - "Hongbin Pei"
  - "Bingzhe Wei"
year: 2020
venue: "ICLR"
abstract: "..."

# Legacy-style identifiers map
identifiers:
  doi: "10.48550/arxiv.2002.05287"
  arxiv: "2002.05287"
  semantic_scholar: "04f3203f1214063436d81ce0c2ad7623204da488"
  openalex: "W2995509042"
  openreview: null
  dblp: null
  pmid: null

# Direct PDF URL list for legacy download_pdf.py
pdf_urls:
  - "https://arxiv.org/pdf/2002.05287.pdf"

# LaTeX source availability
latex_source:
  available: true
  url: "https://arxiv.org/e-print/2002.05287"

# Empty containers for acquisition stage to fill
assets: {}
repo_search:
  selected: null
  candidates: []
```

### Derivation rules

| New field | Compatibility field | Notes |
|-----------|--------------------|-------|
| `bibliography.authors` | `authors` | Direct copy |
| `bibliography.year` | `year` | Direct copy |
| `bibliography.venue` | `venue` | Direct copy, may be null |
| `bibliography.abstract` | `abstract` | Direct copy |
| `identity.aliases.doi` | `identifiers.doi` | May be null |
| `identity.aliases.arxiv` | `identifiers.arxiv` | Primary arXiv id |
| `identity.aliases.semantic_scholar` | `identifiers.semantic_scholar` | May be null |
| `identity.aliases.openalex` | `identifiers.openalex` | May be null |
| `identity.aliases.openreview` | `identifiers.openreview` | May be null |
| `identity.aliases.dblp` | `identifiers.dblp` | May be null |
| `identity.aliases.pmid` | `identifiers.pmid` | May be null |
| `urls.pdf` | `pdf_urls[0]` | Single-element list |
| `acquisition_hints.latex_available` | `latex_source.available` | |
| `acquisition_hints.latex_url` | `latex_source.url` | |

### Ownership

| Section | Owner | Notes |
|---|---|---|
| `identity` | **paper-resolve** | 论文身份标识 |
| `bibliography` | **paper-resolve** | 书目信息 |
| `urls` | **paper-resolve** | 初始 URL，acquire 可更新 `urls.pdf` |
| `acquisition_hints` | **paper-resolve** | 帮助 acquire 跳过搜索 |
| `assets` | **paper-acquire** | PDF、MD、LaTeX 等文件信息 |
| `normalization` | **paper-acquire** | PDF→MD 转换记录 |
| `repo_search` | **paper-repo** | 代码仓库发现结果 |

- **Resolve** owns `identity`, `bibliography`, `urls`, `acquisition_hints`, and the compatibility projection.
- **Acquire** owns `assets`, `normalization`, and may update `urls.pdf`.
- **Repo** owns `repo_search`.
- None may modify `identity` or `bibliography`.
