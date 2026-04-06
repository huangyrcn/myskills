#!/usr/bin/env python3
"""
download_pdf.py - PDF 下载工具

用法:
    # 从 metadata.yaml 下载 (SKILL 内部调用)
    python3 download_pdf.py --metadata ~/papers/{identifier}/metadata.yaml --output ~/papers/{identifier}/paper/

    # 从 candidates.json 下载
    python3 download_pdf.py --candidates /tmp/candidates.json --output ~/papers/

    # 直接用 DOI 下载
    python3 download_pdf.py --doi "10.48550/arXiv.1706.03762" --output /tmp/papers

Fallback 顺序:
    1. 直接推断 (arXiv DOI → arxiv.org/pdf)
    2. pdf_urls (from metadata.yaml)
    3. OA Repository (OpenAIRE → CORE → EuropePMC → PMC)
    4. Unpaywall
    5. Sci-Hub (最后手段)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# 添加当前目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers import (
    SearchQuery, SearchType,
    OpenaireProvider, CoreProvider, EuropePmcProvider,
    PubmedCentralProvider, UnpaywallProvider, SciHubProvider,
)
from metadata_utils import load_metadata, title_slug


# PDF 源优先级
PDF_SOURCE_PRIORITY = [
    "arxiv", "openreview", "pmc", "pubmed_central",
    "biorxiv", "medrxiv", "ssrn", "unpaywall",
    "core", "s2", "openalex", "sci_hub",
]

# 下载配置
CONFIG = {
    "timeout": 60,
    "max_retries": 3,
    "retry_delay": 2,
    "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def download_with_curl(url: str, output_path: str) -> bool:
    """使用 curl 下载 (绕过 Cloudflare)"""
    for attempt in range(CONFIG["max_retries"]):
        try:
            result = subprocess.run([
                "curl", "-s", "-L",
                "-A", CONFIG["user_agent"],
                "-H", "Accept: application/pdf,*/*",
                "-o", output_path,
                "--connect-timeout", "30",
                "--max-time", str(CONFIG["timeout"] * 2),
                url
            ], capture_output=True, timeout=CONFIG["timeout"] * 3)

            if result.returncode != 0:
                if attempt < CONFIG["max_retries"] - 1:
                    time.sleep(CONFIG["retry_delay"])
                continue

            if not os.path.exists(output_path):
                continue

            size = os.path.getsize(output_path)
            if size < 1000:
                os.remove(output_path)
                continue

            # 验证 PDF 头
            with open(output_path, 'rb') as f:
                header = f.read(8)
            if not header.startswith(b'%PDF'):
                os.remove(output_path)
                continue

            return True

        except Exception:
            if attempt < CONFIG["max_retries"] - 1:
                time.sleep(CONFIG["retry_delay"])
            continue

    return False


def get_direct_pdf_url(doi: str) -> tuple[Optional[str], str]:
    """从 DOI 推断直接 PDF URL"""
    if not doi:
        return None, ""

    # arXiv DOI
    if "10.48550" in doi:
        arxiv_id = doi.split("/")[-1]
        if not arxiv_id.startswith("arXiv"):
            arxiv_id = f"arXiv.{arxiv_id}"
        clean_id = arxiv_id.replace("arXiv.", "")
        return f"https://arxiv.org/pdf/{clean_id}.pdf", "arxiv"

    # bioRxiv/medRxiv - 使用 Unpaywall 获取准确 URL

    return None, ""


def query_unpaywall(doi: str) -> Optional[str]:
    """Unpaywall API 获取 PDF URL"""
    if not doi:
        return None

    try:
        import urllib.request
        import urllib.parse

        email = "academic@research.org"
        url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={email}"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": CONFIG["user_agent"]}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        if data.get("best_oa_location", {}).get("url_for_pdf"):
            return data["best_oa_location"]["url_for_pdf"]

        for loc in data.get("oa_locations", []):
            if loc.get("url_for_pdf"):
                return loc["url_for_pdf"]

    except Exception:
        pass

    return None


def query_scihub(doi: str) -> Optional[str]:
    """Sci-Hub 获取 PDF URL"""
    if not doi:
        return None

    try:
        provider = SciHubProvider()
        result = provider.search(SearchQuery(query=doi, search_type=SearchType.DOI))
        if result.papers and result.papers[0].pdf_url:
            return result.papers[0].pdf_url
    except Exception:
        pass

    return None


def query_repository(doi: str, title: str) -> Optional[str]:
    """OA Repository 查询 PDF URL"""
    query = doi or title
    if not query:
        return None

    repositories = [
        ("openaire", OpenaireProvider),
        ("core", CoreProvider),
        ("europepmc", EuropePmcProvider),
        ("pmc", PubmedCentralProvider),
    ]

    for name, provider_class in repositories:
        try:
            provider = provider_class()
            result = provider.search(SearchQuery(
                query=query,
                search_type=SearchType.DOI if doi else SearchType.TITLE,
                max_results=3
            ))

            for paper in result.papers:
                if paper.pdf_url:
                    return paper.pdf_url
        except Exception:
            continue

    return None


def parse_metadata_yaml(yaml_path: str) -> dict:
    """解析 metadata.yaml"""
    metadata = load_metadata(Path(yaml_path))
    identifiers = metadata.get("identifiers", {}) or {}
    return {
        "title": metadata.get("title", ""),
        "doi": identifiers.get("doi"),
        "pdf_urls": metadata.get("pdf_urls", []) or [],
    }


def download_pdf(pdf_urls: list, doi: str, title: str, output_path: str, use_scihub: bool = True) -> bool:
    """
    执行 PDF 下载

    Args:
        pdf_urls: 已知的 PDF URL 列表
        doi: DOI
        title: 论文标题
        output_path: 输出路径
        use_scihub: 是否使用 Sci-Hub

    Returns:
        True 如果下载成功
    """
    # 1. 直接推断
    direct_url, source = get_direct_pdf_url(doi)
    if direct_url:
        print(f"  Trying {source}: {direct_url}")
        if download_with_curl(direct_url, output_path):
            print(f"✓ Downloaded from {source}")
            return True

    # 2. pdf_urls (按优先级排序)
    sorted_urls = sorted(
        pdf_urls,
        key=lambda x: PDF_SOURCE_PRIORITY.index(x.get('source', ''))
        if x.get('source') in PDF_SOURCE_PRIORITY else 999
    )

    for item in sorted_urls:
        url = item.get('url', '')
        source = item.get('source', 'unknown')
        if url:
            print(f"  Trying {source}: {url}")
            if download_with_curl(url, output_path):
                print(f"✓ Downloaded from {source}")
                return True

    # 3. OA Repository
    print("  Trying OA repositories...")
    url = query_repository(doi, title)
    if url:
        print(f"    Found: {url}")
        if download_with_curl(url, output_path):
            print("✓ Downloaded from OA repository")
            return True

    # 4. Unpaywall
    if doi:
        print(f"  Trying Unpaywall for {doi}...")
        url = query_unpaywall(doi)
        if url:
            print(f"    Found: {url}")
            if download_with_curl(url, output_path):
                print("✓ Downloaded from Unpaywall")
                return True

    # 5. Sci-Hub
    if use_scihub and doi:
        print(f"  Trying Sci-Hub for {doi}...")
        url = query_scihub(doi)
        if url:
            print(f"    Found: {url}")
            if download_with_curl(url, output_path):
                print("✓ Downloaded from Sci-Hub")
                return True

    print("❌ Failed to download PDF")
    return False


def download_from_metadata(metadata_path: str, output_dir: str, use_scihub: bool = True) -> bool:
    """从 metadata.yaml 下载"""
    metadata = parse_metadata_yaml(metadata_path)

    doi = metadata.get('doi')
    title = metadata.get('title')
    pdf_urls = metadata.get('pdf_urls', [])

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'paper.pdf')

    print(f"=== Downloading PDF ===")
    print(f"  DOI: {doi or 'N/A'}")
    print(f"  Title: {title[:50]}..." if title else "  Title: N/A")

    return download_pdf(pdf_urls, doi, title, output_path, use_scihub)


def download_from_candidates(candidates_path: str, output_dir: str, use_scihub: bool = True) -> bool:
    """从 candidates.json 下载"""
    with open(candidates_path) as f:
        data = json.load(f)

    pdf_urls = data.get("pdf_urls", [])
    best = data.get("best_match", {})
    doi = best.get("doi")
    title = best.get("title", "paper")

    # 生成目录名
    slug = title_slug(title)[:60]

    paper_dir = Path(output_dir) / slug
    paper_dir.mkdir(parents=True, exist_ok=True)
    output_path = paper_dir / "paper.pdf"

    print(f"=== Downloading to: {paper_dir} ===")

    return download_pdf(pdf_urls, doi, title, str(output_path), use_scihub)


def download_from_doi(doi: str, output_dir: str, use_scihub: bool = True) -> bool:
    """从 DOI 直接下载"""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'paper.pdf')

    print(f"=== Downloading DOI: {doi} ===")

    return download_pdf([], doi, "", output_path, use_scihub)


def main():
    parser = argparse.ArgumentParser(description="PDF 下载工具")
    parser.add_argument("--metadata", "-m", help="metadata.yaml 路径")
    parser.add_argument("--candidates", "-c", help="candidates.json 路径")
    parser.add_argument("--doi", "-d", help="直接用 DOI 下载")
    parser.add_argument("--output", "-o", required=True, help="输出目录")
    parser.add_argument("--no-scihub", action="store_true", help="禁用 Sci-Hub")

    args = parser.parse_args()

    use_scihub = not args.no_scihub

    if args.doi:
        success = download_from_doi(args.doi, args.output, use_scihub)
    elif args.metadata:
        success = download_from_metadata(args.metadata, args.output, use_scihub)
    elif args.candidates:
        success = download_from_candidates(args.candidates, args.output, use_scihub)
    else:
        parser.error("需要 --metadata, --candidates 或 --doi")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
