---
name: paper-repo
description: >
  Discover the official or community implementation repository for a resolved paper.
  Use this skill after paper-acquire when the user wants to find code, verify repo
  authenticity, or check if an implementation exists for a paper.
argument-hint: "<title_slug> | <metadata_path>"
allowed-tools: Bash, Read, Edit, Write
---

# Paper Repo

Discover implementation repository for a paper.

## Ownership

This skill owns:

- `metadata.yaml` → `repo_search` section
- `repo/` → cloned repository (when confidence is high/medium)

This skill does **not**:
- Download PDF or normalize paper
- Generate reading notes
- Modify `identity` or `bibliography` sections

## Workflow

```
Step 1: Extract clues from paper content (scripts)
      → PDF metadata URLs
      → paper.md code links + context
      → Output: candidate URLs with evidence

Step 2: Search GitHub if needed (web-kit)
      → ask-search "{title} site:github.com" -e google -n 10
      → ask-search "{method_name} github" -e google -n 10
      → Add search results to candidates

Step 3: Verify candidates (web-kit)
      → crwlr crawl -o md "{repo_url}"
      → Judge: official vs reimplementation, author match, code-paper alignment

Step 4: Select best candidate and clone (if confidence >= medium)
      → git clone {repo_url} repo/
      → Update cloned_to in metadata.yaml

Step 5: Write repo_search to metadata.yaml
      → selected: best candidate with confidence
      → candidates: all found with sources
```

## Input

Read from:

- `~/papers/{title_slug}/metadata.yaml`
  - `bibliography.authors` — for author verification
  - `bibliography.venue` — for context
  - `identity.aliases.doi` — for citation matching
- `~/papers/{title_slug}/paper/paper.pdf`
- `~/papers/{title_slug}/paper/paper.md`

## Output

Write to `metadata.yaml`:

```yaml
repo_search:
  selected:
    url: "https://github.com/owner/repo"
    confidence: "high"  # high / medium / low / none
    source: "paper_md"  # paper_pdf / paper_md / github_search
    evidence:
      - "README cites the paper DOI: 10.xxx"
      - "Author names match: Hongbin Pei"
    type: "official"    # official / community / reimplementation
    cloned_to: "repo/"  # filled after git clone
  candidates:
    - url: "https://github.com/owner/repo"
      source: "paper_md"
      confidence: "high"
      context: "Code availability section mentions this URL"
    - url: "https://github.com/other/repo"
      source: "github_search"
      confidence: "low"
      context: "Name similarity only"
```

## Clone Policy

**Auto-clone when**:
- `confidence` is `high` or `medium`
- Repo URL is valid GitHub/GitLab URL

**Do not clone when**:
- `confidence` is `low` or `none`
- No valid repo found
- User passes `--no-clone` flag

```bash
# Clone command
cd ~/papers/{title_slug}
git clone {repo_url} repo/
```

After cloning, update `cloned_to` field in metadata.yaml.

## Scripts

### extract_urls_from_pdf.py

Extract URLs from PDF metadata and annotations.

```bash
python3 "${SKILL_DIR}/scripts/extract_urls_from_pdf.py" ~/papers/{title_slug}/paper/paper.pdf
```

Output: JSON list of URLs found in PDF with source annotation.

### extract_code_links_from_md.py

Extract code-related links from paper.md with surrounding context.

```bash
python3 "${SKILL_DIR}/scripts/extract_code_links_from_md.py" ~/papers/{title_slug}/paper/paper.md
```

Output: JSON list of code links with context lines.

## Verification Criteria

| Criterion | How to check |
|-----------|--------------|
| **DOI citation** | README or repo description contains paper DOI |
| **Author match** | GitHub owner name matches one of `bibliography.authors` |
| **Method name** | Repo name contains the method name from title |
| **Paper link** | README links to arXiv/publisher URL from `urls.canonical` |
| **Code alignment** | Repo implements the core algorithm described in paper |

## Confidence Levels

| Level | Criteria |
|-------|----------|
| `high` | DOI citation + author match + official implementation stated |
| `medium` | Repo matches method name + README mentions paper, but no author match |
| `low` | Only name similarity, no explicit paper connection |
| `none` | No candidate found or clearly unrelated |

## Search Strategy

### From paper content (Step 1)

Priority order:

1. `paper.md` → Code availability section, footnote links
2. `paper.pdf` → PDF metadata URLs, annotation links

Paper often explicitly states: "Code is available at https://github.com/..."

### From web search (Step 2)

When paper content has no explicit link:

```bash
# Search by paper title + github
ask-search "{paper_title} github" -e google -n 10

# Search by method name (if identifiable)
ask-search "{method_name} github" -e google -n 10

# Direct GitHub search via site:
ask-search "site:github.com {method_name}" -e google -n 10
```

### Verify candidates (Step 3)

For each candidate URL:

```bash
${SKILL_DIR}/../web-kit/scripts/crwlr crawl -o md "{repo_url}"
```

Look for:
- README content citing the paper
- Author profiles matching paper authors
- Code structure matching paper methodology

## Integration

This skill runs after `paper-acquire`.

Use `paper-pipeline` for end-to-end workflow including repo discovery.

## References

| File | When to read |
|------|--------------|
| `references/repo-verification.md` | Need detailed verification criteria |