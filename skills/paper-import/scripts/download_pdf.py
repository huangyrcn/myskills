#!/usr/bin/env python3
"""
download_pdf.py - OA-first Fallback 链下载 PDF

用法:
    python3 download_pdf.py --metadata res/paper/metadata.yaml --output res/paper/paper/

输出:
    paper.pdf - 下载的 PDF 文件

Fallback 顺序:
    1. 原生下载 (pdf_urls 中的链接)
    2. OA Repository fallback (OpenAIRE → CORE → EuropePMC → PMC)
    3. Unpaywall DOI 解析
    4. Sci-Hub (最后手段)
"""

import argparse
import asyncio
import json
import os
import re
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

# 添加当前目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers import (
    SearchQuery, SearchType,
    OpenaireProvider, CoreProvider, EuropePmcProvider,
    PubmedCentralProvider, UnpaywallProvider, SciHubProvider,
)


class PDFDownloader:
    """OA-first Fallback PDF 下载器"""

    def __init__(self, timeout: int = 60, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    def _download_with_curl(self, url: str, output_path: str) -> bool:
        """使用 curl 下载文件"""
        try:
            result = subprocess.run([
                "curl", "-L", "-s", "--fail",
                "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "-o", output_path,
                "--connect-timeout", str(self.timeout),
                "--max-time", str(self.timeout * 3),
                url
            ], capture_output=True, timeout=self.timeout * 4)

            if result.returncode == 0:
                # 验证是否为有效 PDF
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        header = f.read(8)
                    if header.startswith(b'%PDF'):
                        return True
                    # 删除无效文件
                    os.remove(output_path)
            return False
        except Exception:
            return False

    def download_from_url(self, url: str, output_path: str) -> bool:
        """从 URL 下载 PDF"""
        return self._download_with_curl(url, output_path)

    def repository_fallback(self, doi: str, title: str, output_path: str) -> bool:
        """OA Repository fallback

        依次查询 OpenAIRE → CORE → EuropePMC → PMC
        """
        query = doi or title
        if not query:
            return False

        # Repository 优先级顺序
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
                        if self.download_from_url(paper.pdf_url, output_path):
                            print(f"  ✓ Downloaded from {name}")
                            return True
            except Exception as e:
                print(f"  ! {name} search error: {e}")
                continue

        return False

    def unpaywall_fallback(self, doi: str, output_path: str) -> bool:
        """Unpaywall DOI 解析"""
        if not doi:
            return False

        try:
            provider = UnpaywallProvider()
            paper = provider.get_by_doi(doi)
            if paper and paper.pdf_url:
                if self.download_from_url(paper.pdf_url, output_path):
                    print("  ✓ Downloaded from Unpaywall")
                    return True
        except Exception as e:
            print(f"  ! Unpaywall error: {e}")

        return False

    def scihub_fallback(self, doi: str, title: str, output_path: str) -> bool:
        """Sci-Hub 下载 (最后手段)"""
        query = doi or title
        if not query:
            return False

        try:
            provider = SciHubProvider()
            paper = provider.get_by_doi(doi) if doi else None
            if not paper:
                result = provider.search(SearchQuery(query=query, max_results=1))
                if result.papers:
                    paper = result.papers[0]

            if paper and paper.pdf_url:
                if self.download_from_url(paper.pdf_url, output_path):
                    print("  ✓ Downloaded from Sci-Hub")
                    return True
        except Exception as e:
            print(f"  ! Sci-Hub error: {e}")

        return False


def parse_metadata_yaml(yaml_path: str) -> dict:
    """解析 metadata.yaml"""
    import re

    with open(yaml_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 简单的 YAML 解析
    data = {}

    # title
    match = re.search(r'^title:\s*"?([^"\n]+)"?', content, re.MULTILINE)
    if match:
        data['title'] = match.group(1).strip()

    # doi
    match = re.search(r'doi:\s*"?([^"\n]+)"?', content)
    if match:
        data['doi'] = match.group(1).strip()

    # pdf_urls
    pdf_urls = []
    in_pdf_urls = False
    current_url = {}

    for line in content.split('\n'):
        if 'pdf_urls:' in line:
            in_pdf_urls = True
            continue

        if in_pdf_urls:
            if line.strip().startswith('- source:'):
                if current_url:
                    pdf_urls.append(current_url)
                current_url = {'source': line.split(':', 1)[1].strip()}
            elif line.strip().startswith('url:'):
                current_url['url'] = line.split(':', 1)[1].strip().strip('"')
            elif line.strip().startswith('reliability:'):
                current_url['reliability'] = line.split(':', 1)[1].strip()
            elif line.strip() and not line.startswith(' '):
                if current_url:
                    pdf_urls.append(current_url)
                in_pdf_urls = False
                break

    if current_url:
        pdf_urls.append(current_url)

    data['pdf_urls'] = pdf_urls

    return data


def download_with_fallback(metadata_path: str, output_dir: str, use_scihub: bool = True) -> Optional[str]:
    """执行 OA-first Fallback 下载

    Returns:
        下载的 PDF 路径，或 None（失败）
    """
    metadata = parse_metadata_yaml(metadata_path)

    doi = metadata.get('doi')
    title = metadata.get('title')
    pdf_urls = metadata.get('pdf_urls', [])

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'paper.pdf')

    downloader = PDFDownloader()

    # 1. 原生下载 (pdf_urls)
    print("Step 1: Trying native download...")
    # 按可靠性排序
    reliability_order = {'high': 0, 'medium': 1, 'low': 2}
    pdf_urls_sorted = sorted(
        pdf_urls,
        key=lambda x: reliability_order.get(x.get('reliability', 'low'), 2)
    )

    for url_info in pdf_urls_sorted:
        url = url_info.get('url', '')
        source = url_info.get('source', 'unknown')
        if url:
            print(f"  Trying {source}: {url[:60]}...")
            if downloader.download_from_url(url, output_path):
                print(f"  ✓ Downloaded from {source}")
                return output_path

    # 2. OA Repository fallback
    print("\nStep 2: Trying OA repositories...")
    if downloader.repository_fallback(doi, title, output_path):
        return output_path

    # 3. Unpaywall fallback
    print("\nStep 3: Trying Unpaywall...")
    if downloader.unpaywall_fallback(doi, output_path):
        return output_path

    # 4. Sci-Hub fallback (可选)
    if use_scihub:
        print("\nStep 4: Trying Sci-Hub...")
        if downloader.scihub_fallback(doi, title, output_path):
            return output_path

    print("\n✗ All download attempts failed")
    return None


def main():
    parser = argparse.ArgumentParser(description="OA-first Fallback PDF 下载")
    parser.add_argument("--metadata", "-m", required=True, help="metadata.yaml 路径")
    parser.add_argument("--output", "-o", required=True, help="输出目录")
    parser.add_argument("--no-scihub", action="store_true", help="禁用 Sci-Hub")

    args = parser.parse_args()

    result = download_with_fallback(
        args.metadata,
        args.output,
        use_scihub=not args.no_scihub
    )

    if result:
        print(f"\n✓ Saved to: {result}")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()