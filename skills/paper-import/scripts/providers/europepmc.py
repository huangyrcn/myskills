"""
Europe PMC - 欧洲生物医学文献数据库

API: https://www.ebi.ac.uk/europepmc/webservices/rest
支持: 全文下载 (OA)
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
import logging

logger = logging.getLogger(__name__)


class EuropePmcProvider(BaseProvider):
    """Europe PMC 生物医学文献搜索"""

    BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

    @classmethod
    def name(cls) -> str:
        return "europepmc"

    @classmethod
    def priority(cls) -> int:
        return 88  # 生物医学权威，支持全文

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS, SearchType.DOI]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def search(self, query: SearchQuery) -> ProviderResult:
        params = {
            'query': query.query,
            'pageSize': min(query.max_results, 100),
            'format': 'json',
            'resultType': 'core',
        }

        try:
            resp = requests.get(f"{self.BASE_URL}/search", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            papers = []
            results = data.get('resultList', {}).get('result', [])

            for item in results[:query.max_results]:
                paper = Paper(
                    title=item.get('title', ''),
                    authors=self._parse_authors(item.get('authorList', {}).get('author', [])),
                    year=self._parse_year(item.get('pubYear', '')),
                    venue=item.get('journalTitle', ''),
                    abstract=item.get('abstractText', ''),
                    doi=item.get('doi', ''),
                    pmid=item.get('pmid', ''),
                    pmcid=item.get('pmcid', ''),
                    pdf_url=self._get_pdf_url(item),
                    source=self.name(),
                )
                papers.append(paper)

            total = data.get('hitCount', len(papers))
            return ProviderResult(papers=papers, source=self.name(), total=total)

        except Exception as e:
            logger.error(f"Europe PMC search error: {e}")
            return ProviderResult(papers=[], source=self.name(), error=str(e))

    def _parse_authors(self, authors_data: list) -> list[str]:
        """解析作者列表"""
        if not isinstance(authors_data, list):
            authors_data = [authors_data] if authors_data else []
        return [a.get('fullName', '') for a in authors_data if isinstance(a, dict)]

    def _parse_year(self, year_str: str) -> Optional[int]:
        try:
            return int(year_str) if year_str else None
        except ValueError:
            return None

    def _get_pdf_url(self, item: dict) -> Optional[str]:
        """获取 PDF URL"""
        # Open access PDF
        if item.get('isOpenAccess') == 'Y':
            pmcid = item.get('pmcid', '')
            if pmcid:
                return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
        return None