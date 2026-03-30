#!/usr/bin/env python3
"""
Discover the most likely code repository for a paper.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from metadata_utils import first_author_lastname, load_metadata, write_metadata

USER_AGENT = "paper-import/1.0 (+https://github.com/huangyrcn/myskills)"
REPO_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:github|gitlab|gitee)\.com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(?:\.git)?",
    re.IGNORECASE,
)
GITHUB_REPO_RE = re.compile(r"https?://github\.com/([^/\s]+)/([^/\s#?]+)", re.IGNORECASE)
SOURCE_WEIGHTS = {
    "latex": 8,
    "markdown": 6,
    "metadata_page": 5,
    "github_search": 2,
}


def http_get_text(url: str, *, accept: str = "text/plain,*/*", timeout: int = 30) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="ignore")


def http_get_json(url: str, *, accept: str = "application/json") -> dict:
    return json.loads(http_get_text(url, accept=accept))


def normalize_repo_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    cleaned = re.sub(r"\.git$", "", cleaned)
    parsed = urllib.parse.urlparse(cleaned)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return cleaned
    if parsed.netloc.lower().endswith("github.com"):
        parts = parts[:2]
    return f"{parsed.scheme}://{parsed.netloc}/{'/'.join(parts)}"


def extract_repo_urls(text: str) -> list[str]:
    return sorted({normalize_repo_url(match.group(0)) for match in REPO_URL_RE.finditer(text or "")})


def add_candidate(candidates: dict[str, dict], *, url: str, source: str, evidence: str) -> None:
    normalized = normalize_repo_url(url)
    current = candidates.get(normalized)
    if current is None:
        candidates[normalized] = {
            "url": normalized,
            "sources": [source],
            "evidence": [evidence[:240]],
        }
        return
    if source not in current["sources"]:
        current["sources"].append(source)
    if evidence[:240] not in current["evidence"]:
        current["evidence"].append(evidence[:240])


def scan_local_files(paper_dir: Path, candidates: dict[str, dict]) -> None:
    for pattern, source in (("*.tex", "latex"), ("*.md", "markdown")):
        for file_path in paper_dir.rglob(pattern):
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for url in extract_repo_urls(text):
                add_candidate(
                    candidates,
                    url=url,
                    source=source,
                    evidence=f"{file_path.name}: {url}",
                )


def scan_metadata_pages(metadata: dict, candidates: dict[str, dict]) -> None:
    for page_name, url in (metadata.get("urls", {}) or {}).items():
        if not url:
            continue
        try:
            body = http_get_text(url, accept="text/html,*/*")
        except Exception:
            continue
        for repo_url in extract_repo_urls(body):
            add_candidate(
                candidates,
                url=repo_url,
                source="metadata_page",
                evidence=f"{page_name}: {url}",
            )


def build_search_queries(metadata: dict) -> list[str]:
    title = (metadata.get("title") or "").strip()
    method_name = (metadata.get("method_name") or "").strip()
    lastname = first_author_lastname(metadata.get("authors", []))
    queries = [
        f"\"{title}\" official implementation",
        f"\"{title}\" code",
        f"\"{title}\" github",
    ]
    if method_name:
        queries.append(f"\"{method_name}\" \"{title}\"")
        queries.append(f"{method_name} {lastname} official implementation")
    return queries


def search_github_repositories(metadata: dict, candidates: dict[str, dict], limit: int = 5) -> None:
    for query in build_search_queries(metadata):
        encoded_query = urllib.parse.quote(query)
        url = f"https://api.github.com/search/repositories?q={encoded_query}&per_page={limit}"
        try:
            payload = http_get_json(url, accept="application/vnd.github+json")
        except Exception:
            continue
        for item in payload.get("items", []):
            repo_url = item.get("html_url")
            if not repo_url:
                continue
            add_candidate(
                candidates,
                url=repo_url,
                source="github_search",
                evidence=f"query={query}",
            )


def github_repo_name(url: str) -> Optional[str]:
    match = GITHUB_REPO_RE.match(url)
    if not match:
        return None
    owner = match.group(1)
    repo = re.sub(r"\.git$", "", match.group(2))
    return f"{owner}/{repo}"


def fetch_github_snapshot(repo_name: str) -> dict:
    repo = http_get_json(
        f"https://api.github.com/repos/{repo_name}",
        accept="application/vnd.github+json",
    )
    try:
        readme = http_get_text(
            f"https://api.github.com/repos/{repo_name}/readme",
            accept="application/vnd.github.raw+json",
        )
    except Exception:
        readme = ""
    try:
        contents = http_get_json(
            f"https://api.github.com/repos/{repo_name}/contents/",
            accept="application/vnd.github+json",
        )
    except Exception:
        contents = []
    return {
        "description": repo.get("description") or "",
        "stargazers_count": repo.get("stargazers_count", 0),
        "readme": readme,
        "root_contents": [item.get("name", "") for item in contents if isinstance(item, dict)],
    }


def score_candidate(candidate: dict, metadata: dict) -> tuple[int, list[str]]:
    title = (metadata.get("title") or "").lower()
    method_name = (metadata.get("method_name") or "").lower()
    identifiers = metadata.get("identifiers", {}) or {}
    lastname = first_author_lastname(metadata.get("authors", []))

    score = max(SOURCE_WEIGHTS.get(source, 0) for source in candidate["sources"])
    reasons = [f"found via {', '.join(candidate['sources'])}"]
    repo_name = github_repo_name(candidate["url"])

    if repo_name:
        try:
            snapshot = fetch_github_snapshot(repo_name)
        except Exception:
            snapshot = {}
        combined = " ".join(
            [
                snapshot.get("description", ""),
                snapshot.get("readme", ""),
                " ".join(snapshot.get("root_contents", [])),
                repo_name,
            ]
        ).lower()
        candidate["github"] = {
            "description": snapshot.get("description", ""),
            "stargazers_count": snapshot.get("stargazers_count", 0),
            "root_contents": snapshot.get("root_contents", []),
        }
        if title and title in combined:
            score += 3
            reasons.append("paper title appears in repo metadata")
        if method_name and method_name in combined:
            score += 2
            reasons.append("method name appears in repo metadata")
        arxiv_id = identifiers.get("arxiv")
        doi = identifiers.get("doi")
        if arxiv_id and arxiv_id.lower() in combined:
            score += 2
            reasons.append("arXiv ID appears in README")
        elif doi and doi.lower() in combined:
            score += 2
            reasons.append("DOI appears in README")
        if lastname and lastname in combined:
            score += 1
            reasons.append("author last name appears in repo metadata")
        if "official implementation" in combined or "official code" in combined:
            score += 3
            reasons.append("repo claims official implementation")
        contents = [name.lower() for name in snapshot.get("root_contents", [])]
        if any(name in contents for name in ("train.py", "main.py", "inference.py", "demo.py")):
            score += 1
            reasons.append("root contains runnable entrypoints")
        stars = snapshot.get("stargazers_count", 0)
        if stars > 0:
            score += 1
            reasons.append(f"repo has stars ({stars})")
        if stars >= 50:
            score += 1
            reasons.append("repo has non-trivial adoption")

    confidence = "high" if score >= 8 else "medium" if score >= 5 else "low"
    candidate["score"] = score
    candidate["confidence"] = confidence
    candidate["reasons"] = reasons
    return score, reasons


def clone_repo(url: str, target_dir: Path) -> None:
    if target_dir.exists():
        return
    subprocess.run(["git", "clone", url, str(target_dir)], check=True)


def find_repo(metadata_path: Path, paper_dir: Path, clone: bool) -> dict:
    metadata = load_metadata(metadata_path)
    candidates: dict[str, dict] = {}

    scan_local_files(paper_dir, candidates)
    scan_metadata_pages(metadata, candidates)
    search_github_repositories(metadata, candidates)

    ordered = list(candidates.values())
    for candidate in ordered:
        score_candidate(candidate, metadata)
    ordered.sort(key=lambda item: (-item.get("score", 0), item["url"]))

    selected = ordered[0] if ordered else None
    if selected and clone and selected.get("confidence") != "low":
        repo_dir = metadata_path.parent / "repo"
        try:
            clone_repo(selected["url"], repo_dir)
            selected["cloned_to"] = "repo/"
        except Exception as exc:
            selected["clone_error"] = str(exc)

    metadata["repo_search"] = {
        "selected": selected,
        "candidates": ordered,
    }
    assets = metadata.setdefault("assets", {})
    if selected and selected.get("cloned_to"):
        assets["repo"] = selected["cloned_to"]
    else:
        assets.pop("repo", None)
    write_metadata(metadata_path, metadata)

    report_path = metadata_path.parent / "repo_search.json"
    report_path.write_text(json.dumps(metadata["repo_search"], indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata["repo_search"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Find the most likely code repo for a paper")
    parser.add_argument("--metadata", "-m", required=True, help="Path to metadata.yaml")
    parser.add_argument("--paper-dir", help="Directory containing paper assets")
    parser.add_argument("--clone", action="store_true", help="Clone the selected repo")
    args = parser.parse_args()

    metadata_path = Path(args.metadata).resolve()
    paper_dir = Path(args.paper_dir).resolve() if args.paper_dir else metadata_path.parent / "paper"
    result = find_repo(metadata_path, paper_dir, args.clone)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
