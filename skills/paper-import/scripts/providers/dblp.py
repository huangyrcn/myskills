"""
DBLP - 计算机科学文献数据库

API: https://dblp.org/search/publ/api
返回格式: XML (默认) / JSON
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)


class DblpProvider(BaseProvider):
    """DBLP 计算机科学文献搜索"""

    # 主站和镜像列表
    BASE_URLS = [
        "https://dblp.org/search/publ/api",
        "https://dblp.uni-trier.de/search/publ/api",
        "https://dblp.dagstuhl.de/search/publ/api",
    ]
    BASE_URL = BASE_URLS[0]  # 默认主站

    @classmethod
    def name(cls) -> str:
        return "dblp"

    @classmethod
    def priority(cls) -> int:
        return 85  # CS 领域权威

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    def search(self, query: SearchQuery) -> ProviderResult:
        params = {
            'q': query.query,
            'format': 'json',
            'h': min(query.max_results, 1000)
        }

        # 尝试所有镜像
        for base_url in self.BASE_URLS:
            try:
                resp = requests.get(base_url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                papers = []
                hits = data.get('result', {}).get('hits', {}).get('hit', [])
                if not isinstance(hits, list):
                    hits = [hits] if hits else []

                for hit in hits[:query.max_results]:
                    info = hit.get('info', {})
                    paper = Paper(
                        title=info.get('title', ''),
                        authors=self._parse_authors(info.get('authors', {})),
                        year=self._parse_year(info.get('year', '')),
                        venue=info.get('venue', ''),
                        doi=info.get('doi', ''),
                        pdf_url=info.get('url', ''),
                        source=self.name(),
                    )
                    # DBLP URL
                    if info.get('url'):
                        paper.dblp_id = info['url'].split('/')[-1]
                    papers.append(paper)

                return ProviderResult(papers=papers, source=self.name(), total=len(papers))

            except Exception as e:
                logger.warning(f"DBLP {base_url} failed: {e}")
                continue

        # 所有镜像都失败
        logger.error(f"DBLP all mirrors failed")
        return ProviderResult(papers=[], source=self.name(), error="All mirrors failed")

    def _parse_authors(self, authors_data: dict) -> list[str]:
        """解析作者列表"""
        authors = authors_data.get('author', [])
        if not isinstance(authors, list):
            authors = [authors] if authors else []
        return [a.get('text', '') if isinstance(a, dict) else str(a) for a in authors]

    def _parse_year(self, year_str: str) -> Optional[int]:
        """解析年份"""
        try:
            return int(year_str) if year_str else None
        except ValueError:
            return None