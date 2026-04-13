# Source-to-Metadata Mapping

从各数据源收集信息，映射到 `metadata.yaml` 字段。

## 各源贡献

| 源 | 提供的数据 | metadata 字段 |
|---|---|---|
| **OpenAlex** | DOI, OpenAlex ID, PMID, PMCID, S2 ID, authors, year, venue, is_oa, pdf_url | `aliases.openalex`, `aliases.semantic_scholar`, `aliases.pmid`, `aliases.pmcid`, `bibliography.authors`, `bibliography.year`, `bibliography.venue` |
| **Semantic Scholar** | S2 ID, DOI, authors, venue, openAccessPdf | `aliases.semantic_scholar`, `urls.pdf` |
| **DBLP** | DBLP key, venue (规范化), type, authors | `aliases.dblp`, `bibliography.venue` (优先) |
| **arXiv** | arXiv ID, categories | `aliases.arxiv`, `urls.canonical`, `urls.pdf` |
| **PubMed** | PMID, PMCID, DOI | `aliases.pmid`, `aliases.pmcid` |
| **PMC** | PMCID, 全文 PDF | `urls.pmc` |
| **Crossref** | DOI, publisher, container-title | 验证 DOI，`bibliography.venue_context` |
| **OpenReview** | OpenReview ID, reviews, decision | `aliases.openreview`, `urls.openreview` |
| **Google Scholar** | 被引用数 | 不存（动态数据）|

## 字段优先级

当多个源提供同一字段时，按优先级选择：

| 字段 | 优先级 | 说明 |
|---|---|---|
| `authors` | OpenAlex > Semantic Scholar > DBLP | OpenAlex 作者列表通常最完整 |
| `venue` | DBLP > OpenAlex > Semantic Scholar | DBLP venue 规范化最好 |
| `year` | OpenAlex > Semantic Scholar > Crossref | 通常一致 |
| `doi` | Crossref > OpenAlex > Semantic Scholar | Crossref 是 DOI 官方注册 |
| `pdf_url` | arXiv > PMC > Semantic Scholar > OpenAlex | arXiv/PMC 免费，优先 |

## 交叉验证

收集到多源数据后，验证一致性：

```yaml
resolution_evidence:
  - "OpenAlex DOI 与 Crossref DOI 一致"
  - "Semantic Scholar venue 与 DBLP venue 一致"
  - "arXiv title 与 OpenAlex title 一致"
```

不一致时：
- 记录差异在 `resolution_evidence`
- 降低 `resolution_confidence` 到 `medium`
- 选择最可信源的数据（Crossref DOI > 其他）

## 无结果处理

某源无结果时：

```yaml
aliases:
  arxiv: null       # Nature Methods 论文不在 arXiv
  dblp: null        # 非计算机领域论文
  pmid: null        # 非生物医学论文
```

不影响整体置信度，多个源一致即可确认。