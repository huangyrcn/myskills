# metadata.yaml Schema

`metadata.yaml` is the single source of truth for `paper-import`.

Location:

```text
~/papers/{title_slug}/metadata.yaml
```

The actual storage directory stays as `{title_slug}` under `~/papers/`.
A symlink `{venue}-{method}-{author}` is created in the current working directory pointing to the real directory.

## Schema

```yaml
created_at: "2026-03-29T12:34:56.000000"

title: "Attention Is All You Need"
title_slug: "attention_is_all_you_need"
authors:
  - "Ashish Vaswani"
  - "Noam Shazeer"
year: 2017
venue: "NeurIPS"

confirmed_venue: "neurips"     # filled by finalize_metadata.py
author: "vaswani"              # filled by finalize_metadata.py
method_name: "transformer"     # filled by finalize_metadata.py
foldername: "neurips2017-transformer-vaswani"  # computed by finalize_metadata.py
symlink_path: "/path/to/cwd/neurips2017-transformer-vaswani"  # symlink path if cwd != ~

identifiers:
  doi: "10.5555/3295222.3295349"
  doi_source: "api_verified"
  arxiv: "1706.03762"
  semantic_scholar: "..."
  openalex: "..."
  openreview: "..."
  pmc: "..."
  core: "..."

venue_candidates:
  - source: semantic_scholar
    venue: "Advances in Neural Information Processing Systems"
  - source: openalex
    venue: "NeurIPS"

urls:
  doi: "https://doi.org/10.5555/3295222.3295349"
  arxiv_abs: "https://arxiv.org/abs/1706.03762"
  openreview: "https://openreview.net/forum?id=..."

abstract: "We propose a new simple network architecture..."

pdf_urls:
  - source: arxiv
    url: "https://arxiv.org/pdf/1706.03762"
    reliability: high
  - source: openreview
    url: "https://openreview.net/pdf?id=..."
    reliability: high

latex_source:
  available: true
  url: "https://arxiv.org/e-print/1706.03762"

assets:
  pdf: "paper/paper.pdf"
  markdown: "paper/paper.md"
  latex_dir: "paper/"
  latex_files:
    - "main.tex"
    - "refs.bib"
  repo: "repo/"

repo_search:
  selected:
    url: "https://github.com/example/transformer"
    score: 10
    confidence: high
    cloned_to: "repo/"
  candidates:
    - url: "https://github.com/example/transformer"
      sources: ["latex", "github_search"]
      score: 10
      confidence: high

resolution:
  title_stage:
    canonical_source: "semantic_scholar"
    canonical_title: "Attention Is All You Need"
    matched_sources: ["semantic_scholar", "openalex", "arxiv"]
  identifier_stage:
    arxiv_id: "1706.03762"
    doi: "10.48550/arXiv.1706.03762"
    exact_lookup_sources:
      - "arxiv:id_list"
      - "openalex:doi"
  asset_stage:
    preferred_pdf_source: "arxiv"
    preferred_latex_source: "arxiv"
```

## Notes

- `venue` is the best raw venue from APIs; `confirmed_venue` is the model-confirmed token used for naming.
- `author` is the first author's last name, confirmed during the LLM step.
- `foldername` is empty until `finalize_metadata.py` computes it as `{venue}-{method}-{author}`.
- `symlink_path` is the full path to the cwd symlink; `null` if cwd is the home directory (symlink was skipped).
- `assets.repo` is written only when a medium/high-confidence repo is cloned.
- `repo_search.candidates` is still useful even when no repo is cloned.
- `resolution` records how the title stage selected the paper, which identifiers were trusted, and which asset source should be preferred downstream.
