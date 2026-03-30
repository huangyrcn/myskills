---
name: paper-import
description: >
  Import a paper into the local paper library from its title only.
  Use this skill whenever the user wants to download a paper, save a paper locally,
  fetch the PDF/LaTeX/Markdown package for a paper title, or find the official code
  repository for a paper title. This skill expects the paper title as input, then
  resolves metadata, downloads the PDF, downloads arXiv LaTeX when available,
  converts PDF to Markdown through the pdf-to-md API workflow, and searches multiple
  channels for the code repo before cloning a confident match.
argument-hint: "<paper_title>"
allowed-tools: Bash
---

# Paper Import

Imports a paper package into `papers/{foldername}/` using a title-driven workflow.

## Output Layout

```text
papers/{foldername}/
├── metadata.yaml
├── repo_search.json
├── paper/
│   ├── paper.pdf
│   ├── paper.md
│   ├── main.tex            # when LaTeX is available
│   ├── refs.bib            # when bibliography is available
│   └── paper_images/
└── repo/                   # only when a medium/high-confidence repo is found
```

`{foldername}` is finalized after the model confirms `venue + method_name` from the metadata.

## Core Rules

- Input must be the paper title. If the user did not provide a title, ask for it.
- Keep the LLM step for `venue` and `method_name`; do not guess this inside scripts.
- Preserve the current PDF fallback chain, including Sci-Hub as the last resort in `download_pdf.py`.
- Use the `pdf-to-md` API backend only. The high-quality VLM API path is the supported conversion path.

## Workflow

### Step 1: Resolve metadata from the paper title

```bash
python3 "${SKILL_DIR}/scripts/query_apis.py" "Paper Title Here" --output papers
```

This creates a temporary title-slug directory:

```text
papers/{title_slug}/metadata.yaml
```

`query_apis.py` now uses a three-stage resolution strategy:

- Stage 1, `title -> canonical paper`:
  `arxiv`, `s2`, `openalex`, `crossref`, `dblp`
- Stage 2, `canonical paper -> identifiers`:
  use stage-1 matches plus contextual sources such as
  `openreview`, `biorxiv`, `pubmed_central`, `europepmc`, `zenodo`, `openaire`, `doaj`, `hal`, `repec`, `core`
  to recover `arxiv_id`, DOI, venue candidates, and exact lookup entry points
- Stage 3, `identifiers -> assets`:
  downstream scripts use the recovered identifiers to fetch PDF, LaTeX, Markdown, and the code repo

`arXiv` stays in Stage 1 because it is still the highest-value source for CS/ML papers. But once an `arXiv` ID is known, the pipeline should switch to exact `id_list`-style arXiv lookups instead of relying on repeated title search.

### Step 2: Read metadata and let the model finalize the folder name

Read `metadata.yaml`, then use the paper `title`, `abstract`, and `venue_candidates` to produce:

```json
{
  "venue": "neurips",
  "method_name": "transformer",
  "foldername": "neurips2017-vaswani-transformer"
}
```

Use this prompt shape:

```markdown
You are confirming paper metadata for file naming.

Title: {title}
Venue Candidates:
{venue_candidates}
Abstract:
{abstract}

Tasks:
1. Choose the best standardized venue token.
2. Extract the method or acronym proposed by the paper.
3. Return JSON with venue, method_name, foldername.
```

Then finalize the directory:

```bash
python3 "${SKILL_DIR}/scripts/finalize_metadata.py" \
  --metadata "papers/{title_slug}/metadata.yaml" \
  --venue "{venue}" \
  --method "{method_name}"
```

The command prints the new `metadata.yaml` path inside the finalized folder.

### Step 3: Import all assets

Run the full pipeline on the finalized metadata:

```bash
python3 "${SKILL_DIR}/scripts/import_paper.py" \
  --metadata "papers/{foldername}/metadata.yaml"
```

This pipeline completes:

1. PDF download using `download_pdf.py`
2. arXiv LaTeX download when `latex_source.available=true`
3. PDF to Markdown through the `pdf-to-md` API script
4. Multi-channel repo discovery:
   - repo URLs embedded in LaTeX
   - repo URLs embedded in Markdown
   - repo URLs linked from metadata pages such as arXiv/OpenReview/DOI landing pages
   - GitHub repository search plus README validation
5. Repo clone when the selected candidate is medium/high confidence

### Step 4: Report

Report:

- the finalized folder path
- whether PDF / Markdown / LaTeX were produced
- the selected repo URL and confidence
- whether the repo was cloned or only recorded in `repo_search.json`

## Key Scripts

- `scripts/query_apis.py`
  Resolves metadata and creates the temporary title-slug directory.
- `scripts/finalize_metadata.py`
  Writes `confirmed_venue`, `method_name`, `foldername`, then renames the directory.
- `scripts/import_paper.py`
  Runs the full asset pipeline: PDF, LaTeX, Markdown, repo discovery.
- `scripts/find_repo.py`
  Scores repo candidates from local assets, metadata pages, and GitHub search.

## References

- `references/identifier-generation.md`
  Folder naming contract and the LLM extraction step.
- `references/metadata-schema.md`
  Canonical `metadata.yaml` schema.
- `references/github-api.md`
  GitHub scoring rules used for repo validation.
