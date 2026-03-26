"""
CiteSeerX - 计算机科学数字图书馆

API: https://citeseerx.ist.psu.edu/api
支持: CS 文献、引用网络
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
import logging
import urllib3

# 禁用 SSL 警告（CiteSeerX 证书问题）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class CiteseerxProvider(BaseProvider):
    """CiteSeerX 计算机科学文献搜索"""

    BASE_URL = "https://citeseerx.ist.psu.edu"
    SEARCH_API = f"{BASE_URL}/api/search"

    @classmethod
    def name(cls) -> str:
        return "citeseerx"

    @classmethod
    def priority(cls) -> int:
        return 68  # CS 文献，但 API 不太稳定

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    def search(self, query: SearchQuery) -> ProviderResult:
        headers = {
            'User-Agent': 'paper-search-mcp/1.0',
            'Accept': 'application/json',
        }

        params = {
            'query': query.query,
            'limit': min(query.max_results, 100),
        }

        try:
            resp = requests.get(self.SEARCH_API, params=params, headers=headers, timeout=30, verify=False)

            # 检查是否重定向到 Wayback
            if 'web.archive.org' in resp.url:
                logger.warning("CiteSeerX API redirected to archive, skipping")
                return ProviderResult(papers=[], source=self.name(), error="API archived")

            resp.raise_for_status()
            data = resp.json()

            papers = []
            results = data.get('papers', []) or data.get('results', [])

            for item in results[:query.max_results]:
                paper = Paper(
                    title=item.get('title', ''),
                    authors=self._parse_authors(item.get('authors', [])),
                    year=item.get('year'),
                    abstract=item.get('abstract', '')[:500] if item.get('abstract') else '',
                    doi=item.get('doi', ''),
                    pdf_url=item.get('url', '') or item.get('pdf_url', ''),
                    source=self.name(),
                )
                paper.citeseerx_id = item.get('id', '')
                papers.append(paper)

            return ProviderResult(papers=papers, source=self.name(), total=len(papers))

        except Exception as e:
            logger.error(f"CiteSeerX search error: {e}")
            return ProviderResult(papers=[], source=self.name(), error=str(e))

    def _parse_authors(self, authors) -> list[str]:
        if isinstance(authors, str):
            return [a.strip() for a in authors.split(',') if a.strip()]
        if isinstance(authors, list):
            return [a.get('name', '') if isinstance(a, dict) else str(a) for a in authors]
        return []