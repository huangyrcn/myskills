"""
DOAJ - 开放获取期刊目录

API: https://doaj.org/api/v2
支持: 高质量同行评审开放获取期刊
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)


class DoajProvider(BaseProvider):
    """DOAJ 开放获取期刊搜索"""

    BASE_URL = "https://doaj.org"

    @classmethod
    def name(cls) -> str:
        return "doaj"

    @classmethod
    def priority(cls) -> int:
        return 76  # 高质量开放获取

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def search(self, query: SearchQuery) -> ProviderResult:
        try:
            # DOAJ API: https://doaj.org/api/search/articles/{query}
            resp = requests.get(
                f"{self.BASE_URL}/api/search/articles/{quote(query.query)}",
                params={'pageSize': min(query.max_results, 100)},
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()

            papers = []
            results = data.get('results', [])

            for item in results[:query.max_results]:
                bibjson = item.get('bibjson', {})

                # 标题可能是列表
                title = bibjson.get('title', '')
                if isinstance(title, list):
                    title = title[0] if title else ''

                paper = Paper(
                    title=title,
                    authors=self._parse_authors(bibjson.get('author', [])),
                    year=self._parse_year(bibjson.get('year', '')),
                    venue=bibjson.get('journal', {}).get('title', '') if isinstance(bibjson.get('journal'), dict) else '',
                    abstract=bibjson.get('abstract', '')[:500] if bibjson.get('abstract') else '',
                    doi=self._get_doi(bibjson.get('identifier', [])),
                    pdf_url=self._get_pdf_url(bibjson.get('link', [])),
                    source=self.name(),
                )
                papers.append(paper)

            total = data.get('total', len(papers))
            return ProviderResult(papers=papers, source=self.name(), total=total)

        except Exception as e:
            logger.error(f"DOAJ search error: {e}")
            return ProviderResult(papers=[], source=self.name(), error=str(e))

    def _parse_authors(self, authors: list) -> list[str]:
        if not isinstance(authors, list):
            authors = [authors] if authors else []
        return [a.get('name', '') if isinstance(a, dict) else str(a) for a in authors]

    def _parse_year(self, year) -> Optional[int]:
        try:
            return int(year) if year else None
        except (ValueError, TypeError):
            return None

    def _get_doi(self, identifiers: list) -> str:
        if not isinstance(identifiers, list):
            return ''
        for idf in identifiers:
            if isinstance(idf, dict) and idf.get('type') == 'doi':
                return idf.get('id', '')
        return ''

    def _get_pdf_url(self, links: list) -> Optional[str]:
        if not isinstance(links, list):
            return None
        for link in links:
            if isinstance(link, dict):
                url = link.get('url', '')
                if url:
                    return url
        return None