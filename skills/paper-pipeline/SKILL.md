---
name: paper-pipeline
description: >
  End-to-end paper workflow: resolve a paper reference, acquire the canonical raw
  bundle, discover and clone repository. Generate reading notes if user requests
  ("笔记", "reading notes", "--with-notes").
argument-hint: "<paper_reference> [--skip-repo] [--with-notes] [--output <note_path>]"
allowed-tools: Skill, Read, Bash
---

# Paper Pipeline

End-to-end paper workflow. Calls other paper-* skills sequentially.

## Storage

**Canonical store**: `~/docs/papers/{folder_slug}/`

Example: `~/docs/papers/iclr2017-gcn-kipf/`

## Pipeline

**Default**: resolve → acquire → repo

**Notes**: Only if user requests ("笔记", "reading notes", "--with-notes")

## Execution Steps

Parse user arguments first:

| Flag | Effect |
|------|--------|
| `--skip-repo` | Skip Step 3 |
| `--with-notes` | Run Step 4 after Step 3 |
| `--output <path>` | Pass to paper-reading-notes |
| `--refresh` | Re-run completed steps |

### Step 1: paper-resolve

Call: `Skill(skill="paper-resolve", args="<paper_reference>")`

Output: `~/docs/papers/{folder_slug}/metadata.yaml`

Skip if: metadata.yaml already exists and `--refresh` not set.

### Step 2: paper-acquire

Call: `Skill(skill="paper-acquire", args="{folder_slug}")`

Output: `~/docs/papers/{folder_slug}/paper/paper.pdf`, `paper.md`

Skip if: paper.md already exists and `--refresh` not set.

### Step 3: paper-repo

Call: `Skill(skill="paper-repo", args="{folder_slug}")`

Output: `~/docs/papers/{folder_slug}/repo/` (if found)

Skip if: `--skip-repo` or repo already exists and `--refresh` not set.

### Step 4: paper-reading-notes

Call: `Skill(skill="paper-reading-notes", args="{folder_slug} --output {path}")`

Output: `reading-note.md`

Only runs if user requests notes.

## Example

User: `"SpaMI spatial multi-omics --with-notes"`

Execute:
1. `Skill(skill="paper-resolve", args="SpaMI spatial multi-omics")`
2. `Skill(skill="paper-acquire", args="preprint2024-spami-pei")`
3. `Skill(skill="paper-repo", args="preprint2024-spami-pei")`
4. `Skill(skill="paper-reading-notes", args="preprint2024-spami-pei")`
