# Paper Skills Redesign

## Goal

Split the old `paper-import` monolith into a small set of reusable skills with clear ownership:

- `paper-resolve`: resolve a user's paper reference into a canonical paper identity
- `paper-acquire`: build or update the canonical raw bundle under `~/papers/{folder_slug}`
- `paper-reading-notes`: write research-style reading notes from an existing raw bundle
- `paper-pipeline`: orchestrate the end-to-end flow

Keep `paper-import` as a legacy compatibility skill instead of the default entrypoint.

## Storage Model

### Canonical raw storage

Raw assets always live under:

```text
~/papers/{folder_slug}/
```

Suggested layout:

```text
~/papers/{folder_slug}/
  metadata.yaml
  repo_search.json
  paper/
    paper.pdf
    source.md
    main.tex
    refs.bib
    paper_images/
  repo/
```

### Note output

Notes never redefine the raw root.

Output rules:

1. If the user specifies a note directory, use it.
2. If the user does not specify a note directory and the current working directory is not `~`, write notes to:

```text
./papers/{folder_slug}/reading-note.md
```

3. If the user does not specify a note directory and the current working directory is `~`, write notes to:

```text
~/tmp/paper-notes/{folder_slug}/reading-note.md
```

The note file must include:

- `Source URL`
- `Local Raw Path`

## Pipeline

### 1. Interpret Input

Accept title, DOI, arXiv id/url, OpenReview url, publisher/project url, local PDF path, or an existing raw bundle reference.

### 2. Resolve Identity

This stage is LLM-led and search-backed:

- Prefer local exact matches under `~/papers`
- Prefer exact resolution for DOI, arXiv, and OpenReview inputs
- Otherwise use an appropriate web search and page-reading tool to gather candidates
- Prefer `web-kit` when available and stable, but do not depend on it exclusively
- Ask the user to confirm only when the evidence is still ambiguous

Resolve success does **not** require DOI or venue.

Minimum success set:

- `canonical_title`
- `folder_slug`
- `canonical_url`
- one stable identifier when available
- `resolution_confidence`

### 3. Acquire Raw

Populate or update the canonical raw bundle:

- PDF
- LaTeX sources when available
- normalized source text
- repo discovery results

### 4. Normalize Source

Always produce:

```text
~/papers/{folder_slug}/paper/source.md
```

Backend policy:

- Prefer `latex -> pandoc -> source.md` when usable LaTeX is available
- Fall back to `pdf -> MinerU -> source.md`

### 5. Discover Repo

Search order:

1. links embedded in LaTeX or `source.md`
2. links embedded in metadata pages
3. repository search

Only clone medium/high confidence candidates.

### 6. Synthesize Notes

Generate the research-style note from raw assets and repo context, not from user memory.

## Skill Boundaries

### paper-resolve

- user-facing identity resolution skill
- no PDF download
- no note writing

### paper-acquire

- raw bundle hydration
- source normalization
- repo discovery
- no note writing

### paper-reading-notes

- note synthesis only
- no raw download

### paper-pipeline

- end-to-end orchestrator

## Compatibility Strategy

Keep `skills/paper-import/` as a legacy compatibility skill:

- retain the existing scripts there for now
- update `SKILL.md` so new work prefers the new skills
- let `paper-acquire` reuse the legacy implementation where practical during migration

## Validation

Validation for this redesign should include:

- YAML frontmatter sanity checks for all new skills
- JSON validity for eval files
- `paper-acquire/scripts/hydrate_raw.py --help`
- a temporary-directory dry run of `hydrate_raw.py` against an existing metadata bundle
