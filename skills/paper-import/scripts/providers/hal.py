"""
HAL - 法国开放档案

API: https://api.archives-ouvertes.fr/docs/search
支持: 法国学术界所有学科
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
import logging

logger = logging.getLogger(__name__)


class HalProvider(BaseProvider):
    """HAL 法国开放档案搜索"""

    BASE_URL = "https://api.archives-ouvertes.fr/search"

    @classmethod
    def name(cls) -> str:
        return "hal"

    @classmethod
    def priority(cls) -> int:
        return 74  # 法国开放档案

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def search(self, query: SearchQuery) -> ProviderResult:
        fields = "halId_s,title_s,authFullName_s,abstract_s,doiId_s,publicationDateY_i,fileMain_s,uri_s,docType_s"

        params = {
            'q': query.query,
            'rows': min(query.max_results, 10000),
            'fl': fields,
            'wt': 'json',
        }

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            papers = []
            docs = data.get('response', {}).get('docs', [])

            for doc in docs[:query.max_results]:
                # title_s 可能是列表
                title = doc.get('title_s', '')
                if isinstance(title, list):
                    title = title[0] if title else ''

                # authors
                authors = doc.get('authFullName_s', [])
                if isinstance(authors, str):
                    authors = [authors]

                paper = Paper(
                    title=title,
                    authors=authors,
                    year=doc.get('publicationDateY_i'),
                    abstract=self._get_abstract(doc.get('abstract_s', '')),
                    doi=doc.get('doiId_s', ''),
                    pdf_url=doc.get('fileMain_s', ''),
                    source=self.name(),
                )
                paper.hal_id = doc.get('halId_s', '')
                paper.doc_type = doc.get('docType_s', '')
                papers.append(paper)

            total = data.get('response', {}).get('numFound', len(papers))
            return ProviderResult(papers=papers, source=self.name(), total=total)

        except Exception as e:
            logger.error(f"HAL search error: {e}")
            return ProviderResult(papers=[], source=self.name(), error=str(e))

    def _get_abstract(self, abstract) -> str:
        """摘要可能是列表"""
        if isinstance(abstract, list):
            return abstract[0][:500] if abstract else ''
        return str(abstract)[:500] if abstract else ''