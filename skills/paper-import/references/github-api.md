# GitHub Repo Validation

`find_repo.py` uses GitHub as one of several discovery channels. It does not trust raw search results by default; it scores them against paper metadata.

## Discovery channels

1. Explicit repo URLs in LaTeX
2. Explicit repo URLs in generated Markdown
3. Explicit repo URLs found on metadata pages such as arXiv / OpenReview / DOI landing pages
4. GitHub repository search

## GitHub API usage

Anonymous requests work with low limits.
Set `GITHUB_TOKEN` for higher limits.

### Repo metadata

```bash
curl -s -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/OWNER/REPO"
```

### Raw README

```bash
curl -s -H "Accept: application/vnd.github.raw+json" \
  "https://api.github.com/repos/OWNER/REPO/readme"
```

### Root contents

```bash
curl -s -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/OWNER/REPO/contents/"
```

## Scoring rules

- explicit discovery channel weight:
  - LaTeX: 8
  - Markdown: 6
  - Metadata page: 5
  - GitHub search: 2
- `paper title` appears in README / description: +3
- `method_name` appears in README / description / repo name: +2
- arXiv ID or DOI appears in README: +2
- first-author last name appears in repo metadata: +1
- repo claims `official implementation` or `official code`: +3
- root contains runnable entrypoints such as `train.py`, `main.py`, `demo.py`: +1
- repo has stars: +1
- repo has at least 50 stars: +1

## Confidence levels

- `high`: score >= 8
- `medium`: score >= 5
- `low`: score < 5

Only medium/high confidence repos are cloned automatically.
