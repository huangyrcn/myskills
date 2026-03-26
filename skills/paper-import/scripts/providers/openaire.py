"""
OpenAIRE - 欧洲开放科研基础设施

API: https://api.openaire.eu
支持: 欧洲科研项目产出
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
import logging

logger = logging.getLogger(__name__)


class OpenaireProvider(BaseProvider):
    """OpenAIRE 欧洲开放科研搜索"""

    BASE_URL = "https://api.openaire.eu/search"

    @classmethod
    def name(cls) -> str:
        return "openaire"

    @classmethod
    def priority(cls) -> int:
        return 75  # 欧洲开放科学

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS, SearchType.DOI]

    def search(self, query: SearchQuery) -> ProviderResult:
        params = {
            'keywords': query.query,
            'size': min(query.max_results, 100),
            'format': 'json',
        }

        try:
            resp = requests.get(f"{self.BASE_URL}/publications", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            papers = []
            results = data.get('response', {}).get('results', {}).get('result', [])
            if not isinstance(results, list):
                results = [results] if results else []

            for item in results[:query.max_results]:
                metadata = item.get('metadata', {}).get('oaf:entity', {}).get('oaf:result', {})
                paper = Paper(
                    title=self._get_title(metadata),
                    authors=self._parse_authors(metadata.get('creator', [])),
                    year=self._parse_year(metadata.get('dateofacceptance', {}).get('$', '')),
                    venue=self._get_venue(metadata),
                    abstract=self._get_abstract(metadata),
                    doi=self._get_doi(metadata),
                    pdf_url=self._get_pdf_url(metadata),
                    source=self.name(),
                )
                # OpenAIRE ID
                paper.openaire_id = item.get('header', {}).get('dri:objIdentifier', '')
                papers.append(paper)

            total = data.get('response', {}).get('header', {}).get('total', '$')
            return ProviderResult(papers=papers, source=self.name(), total=total if isinstance(total, int) else len(papers))

        except Exception as e:
            logger.error(f"OpenAIRE search error: {e}")
            return ProviderResult(papers=[], source=self.name(), error=str(e))

    def _get_title(self, metadata: dict) -> str:
        titles = metadata.get('title', [])
        if isinstance(titles, dict):
            return titles.get('$', '')
        if isinstance(titles, list):
            for t in titles:
                if isinstance(t, dict):
                    return t.get('$', '')
                if isinstance(t, str):
                    return t
        return ''

    def _parse_authors(self, creators: list) -> list[str]:
        if not isinstance(creators, list):
            creators = [creators] if creators else []
        return [c.get('$', '') if isinstance(c, dict) else str(c) for c in creators]

    def _parse_year(self, date_str: str) -> Optional[int]:
        try:
            return int(date_str[:4]) if date_str else None
        except (ValueError, IndexError):
            return None

    def _get_venue(self, metadata: dict) -> str:
        source = metadata.get('source', [])
        if isinstance(source, list):
            for s in source:
                if isinstance(s, dict):
                    return s.get('$', '')
        return ''

    def _get_abstract(self, metadata: dict) -> str:
        descriptions = metadata.get('description', [])
        if isinstance(descriptions, list):
            for d in descriptions:
                if isinstance(d, dict):
                    return d.get('$', '')[:500]
        return ''

    def _get_doi(self, metadata: dict) -> str:
        pids = metadata.get('pid', [])
        if isinstance(pids, list):
            for p in pids:
                if isinstance(p, dict) and p.get('classid') == 'doi':
                    return p.get('$', '')
        return ''

    def _get_pdf_url(self, metadata: dict) -> Optional[str]:
        instances = metadata.get('instance', [])
        if isinstance(instances, list):
            for inst in instances:
                if isinstance(inst, dict):
                    url = inst.get('webresource', {}).get('url', '')
                    if url:
                        return url
        return None