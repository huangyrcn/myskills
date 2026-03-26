# GitHub API for Repo Validation

## Auth

```bash
AUTH_ARGS=()
[ -n "$GITHUB_TOKEN" ] && AUTH_ARGS=(-H "Authorization: token $GITHUB_TOKEN")
```

Limits: 60 req/hr (anon), 5000 req/hr (with token).

## Get README

```bash
OWNER_REPO="owner/repo"
curl -s "${AUTH_ARGS[@]}" -H "Accept: application/vnd.github.v3.raw" \
  "https://api.github.com/repos/${OWNER_REPO}/readme"
```

Truncate to 5000 chars for validation. Fallback: fetch JSON + base64-decode.

## Get Root Contents

```bash
curl -s "${AUTH_ARGS[@]}" "https://api.github.com/repos/${OWNER_REPO}/contents/" | \
  python3 -c "import sys,json; [print(f['name']) for f in json.load(sys.stdin)]"
```

## Get Repo Metadata

```bash
curl -s "${AUTH_ARGS[@]}" "https://api.github.com/repos/${OWNER_REPO}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Stars: {d.get('stargazers_count',0)}\nDesc: {d.get('description','')}\nLang: {d.get('language','')}\")"
```

## Scoring

README title match (3pts), "official implementation" (3pts), arXiv/DOI in README (2pts), author (2pts), env file (1pt), train/main script (1pt), stars>0 (1pt). Score ≥5=high, 2-4=medium, <2=low.

Errors: 404=invalid, 403=rate limit (suggest adding `$GITHUB_TOKEN`), 301=follow redirect.
