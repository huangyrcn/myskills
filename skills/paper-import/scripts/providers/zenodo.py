"""
Zenodo - CERN 开放科研仓库

API: https://developers.zenodo.org/
支持: 所有学科，免费 API
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
import logging

logger = logging.getLogger(__name__)


class ZenodoProvider(BaseProvider):
    """Zenodo 开放科研仓库搜索"""

    BASE_URL = "https://zenodo.org/api"

    @classmethod
    def name(cls) -> str:
        return "zenodo"

    @classmethod
    def priority(cls) -> int:
        return 78  # 通用科研仓库

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def search(self, query: SearchQuery) -> ProviderResult:
        params = {
            'q': query.query,
            'size': min(query.max_results, 200),
            'sort': 'mostrecent',
        }

        try:
            resp = requests.get(f"{self.BASE_URL}/records", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            papers = []
            hits = data.get('hits', {}).get('hits', [])

            for item in hits[:query.max_results]:
                metadata = item.get('metadata', {})
                paper = Paper(
                    title=metadata.get('title', ''),
                    authors=self._parse_authors(metadata.get('creators', [])),
                    year=self._parse_year(metadata.get('publication_date', '')),
                    venue=metadata.get('journal', {}).get('title', '') if metadata.get('journal') else '',
                    abstract=metadata.get('description', ''),
                    doi=metadata.get('doi', ''),
                    pdf_url=self._get_pdf_url(item),
                    source=self.name(),
                )
                # Zenodo record ID
                paper.zenodo_id = str(item.get('id', ''))
                papers.append(paper)

            total = data.get('hits', {}).get('total', len(papers))
            return ProviderResult(papers=papers, source=self.name(), total=total)

        except Exception as e:
            logger.error(f"Zenodo search error: {e}")
            return ProviderResult(papers=[], source=self.name(), error=str(e))

    def _parse_authors(self, creators: list) -> list[str]:
        """解析作者列表"""
        return [c.get('name', '') for c in creators if isinstance(c, dict)]

    def _parse_year(self, date_str: str) -> Optional[int]:
        """解析年份 (格式: YYYY-MM-DD)"""
        try:
            return int(date_str[:4]) if date_str else None
        except (ValueError, IndexError):
            return None

    def _get_pdf_url(self, item: dict) -> Optional[str]:
        """获取 PDF URL"""
        files = item.get('files', [])
        for f in files:
            if f.get('type') == 'pdf' or (f.get('key', '').endswith('.pdf')):
                return f.get('links', {}).get('self', '')
        return None