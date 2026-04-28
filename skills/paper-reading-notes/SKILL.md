---
name: paper-reading-notes
description: >
  Generate research-style reading notes from an existing canonical raw bundle.
  Use this skill whenever the user wants to read a paper deeply, produce reusable
  research notes, compare paper claims with evidence, map the paper to code, or
  turn an already-downloaded paper into structured notes. Use this after resolve,
  acquire, and repo stages, not instead of them.
argument-hint: "<folder_slug> | <metadata_path> [--output <path>]"
allowed-tools: Bash, Read, Write, Edit
---

# Paper Reading Notes

Generate research-style reading notes from an existing raw bundle.

## Ownership

This skill owns:

- `./papers/{folder_slug}/reading-note.md` (when cwd is not `~`)
- `~/tmp/paper-notes/{folder_slug}/reading-note.md` (when cwd is `~`)
- User-specified output path

This skill does **not**:
- Resolve paper identity
- Download PDF or normalize to paper.md
- Discover repositories
- Modify `metadata.yaml`

## Inputs

Read from the canonical raw bundle:

| Source | Fields used |
|--------|-------------|
| `metadata.yaml` | `title`, `bibliography.authors`, `bibliography.venue`, `urls.canonical`, `repo_search.selected` |
| `paper/paper.md` | Full text for analysis |
| `paper/paper.pdf` | Fallback when paper.md incomplete |
| `paper/latex/main.tex` | Supplementary detail when needed |
| `repo/` | Code alignment when `repo_search.selected.confidence` is high |

## Output Path

Choose destination in this order:

1. User-specified `--output` path
2. `./papers/{folder_slug}/reading-note.md` when cwd is not `~`
3. `~/tmp/paper-notes/{folder_slug}/reading-note.md` when cwd is `~`

## Note Contract

The note is **not a summary**. It is a reusable research note that reconstructs:

1. **Problem Context** — Why this paper exists, what prior work it responds to
2. **Core Idea** — The key insight or mechanism that distinguishes this work
3. **Mechanism** — How the method works, step by step
4. **Evidence** — What experiments/results support the claims
5. **Limits** — What the method cannot do, failure cases, assumptions
6. **Code Alignment** — How paper concepts map to implementation (when repo exists)
7. **Reading Guide** — How to efficiently read this paper in the future

Read [references/note-ontology.md](references/note-ontology.md) for section structure.

## Script

```bash
python3 "${SKILL_DIR}/scripts/generate_note.py" "{folder_slug}"
python3 "${SKILL_DIR}/scripts/generate_note.py" "{folder_slug}" --output ./notes/reading-note.md
python3 "${SKILL_DIR}/scripts/generate_note.py" "/path/to/paper/bundle"
```

The script:
- Locates raw bundle from folder_slug or path
- Reads `metadata.yaml`, `paper.md`, `repo_search`
- Determines output path based on cwd
- Prints assembled context for note generation

## Repo Confidence Guardrail

**Critical**: Check `repo_search.selected.confidence` before writing Code Alignment section.

| Confidence | Action |
|------------|--------|
| `high` | Full code alignment: map paper concepts to repo modules/functions |
| `medium` | Partial alignment: note uncertainty, map only obvious parts |
| `low` | State "repo found but confidence low, alignment unreliable" |
| `none` / `null` | Skip Code Alignment section, state "no official repo found" |

**Never** pretend a repo is official when confidence is uncertain.

Example guardrail text:

```markdown
## Code Alignment

> ⚠️ Repo confidence: low. Alignment may be unreliable.

Repository: https://github.com/xxx/yyy

Based on repo README, the following modules appear to correspond to paper concepts:
- `model.py` — likely implements the core architecture (unverified)
```

## Note Header

Every note must begin with:

```markdown
# {Paper Title}

**Source**: {urls.canonical}
**Authors**: {bibliography.authors}
**Venue**: {bibliography.venue} ({bibliography.year})
**Local Path**: ~/docs/papers/{folder_slug}

> Generated: {date}
```

## Integration

This skill runs after:
- `paper-resolve` (identity established)
- `paper-acquire` (raw bundle complete)
- `paper-repo` (repo discovered or confirmed none)

Use `paper-pipeline` for end-to-end workflow.

## References

| File | When to read |
|------|--------------|
| `references/note-ontology.md` | Before writing note structure |
| `references/repo-alignment.md` | When writing Code Alignment section |