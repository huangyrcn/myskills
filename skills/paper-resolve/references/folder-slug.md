# Folder Slug Contract

`folder_slug` is the stable filesystem identifier for the canonical raw bundle.

## Principles

- derive it from **venue, year, method name, and first author** — not from the full title
- keep it short, human-readable, and stable across projects
- use it everywhere: canonical store (`~/docs/papers/`) and project directories (`./papers/`)

## Format

```
{venue}{year}-{method}-{first_author}
```

Where:
- `venue`: `bibliography.venue`, lowercase, strip whitespace (e.g., "ICLR" → `iclr`, "NeurIPS" → `neurips`)
- `year`: `bibliography.year` as-is (e.g., `2017`)
- `method`: extracted from title by the LLM — see Method Extraction below
- `first_author`: last name of `bibliography.authors[0]`, lowercase (e.g., "Thomas Kipf" → `kipf`)

All parts are lowercase, joined with `-`.

## Method Extraction

| Title pattern | Method |
|---------------|--------|
| `"Geom-GCN: ..."` | `geom-gcn` (acronym before colon) |
| `"BERT: Pre-training..."` | `bert` |
| `"Attention Is All You Need"` | `transformer` (key term from content) |
| `"Deep Residual Learning..."` | `resnet` (if mentioned in abstract) |
| `"SpaMI: Spatial Multi-omics..."` | `spami` |

No clear method → use first meaningful lowercase keyword from the title (e.g., `"deep_residual"`).

## Fallbacks

| Missing field | Fallback |
|---------------|----------|
| No venue | `preprint` |
| No year | `unknown` |
| No authors | omit the author segment |

## Collision Rule

If the slug already exists:

- reuse it if the existing bundle refers to the same paper
- otherwise add a stable suffix

Stable suffix priority:

1. arXiv id
2. DOI short hash
3. OpenReview/OpenAlex/Semantic Scholar id fragment

Examples:

```text
iclr2017-gcn-kipf_1706_03762
neurips2017-transformer-vaswani
preprint2024-spami-pei
```
