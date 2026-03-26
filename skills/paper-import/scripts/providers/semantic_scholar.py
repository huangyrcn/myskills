"""
Semantic Scholar Provider

API 文档: https://api.semanticscholar.org/api-docs/
优先级: 88 (高)
支持全文: 是
"""

import json
import os
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class SemanticScholarProvider(BaseProvider):
    """Semantic Scholar 数据源"""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "semantic_scholar"

    @classmethod
    def priority(cls) -> int:
        return 88

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.DOI, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _get_headers(self) -> dict:
        """获取请求头"""
        headers = {"User-Agent": "resolve-paper-metadata/5.0"}
        api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        if api_key:
            headers["x-api-key"] = api_key
        return headers

    def _build_search_url(self, query: str, limit: int) -> str:
        """构建搜索 URL"""
        fields = "paperId,title,authors,year,abstract,venue,externalIds,openAccessPdf"
        encoded = urllib.parse.quote(query)
        return f"{self.BASE_URL}/paper/search?query={encoded}&fields={fields}&limit={limit}"

    def _build_doi_url(self, doi: str) -> str:
        """构建 DOI 查询 URL"""
        fields = "paperId,title,authors,year,abstract,venue,externalIds,openAccessPdf"
        encoded = urllib.parse.quote(doi)
        return f"{self.BASE_URL}/paper/DOI:{encoded}?fields={fields}"

    def _parse_paper(self, data: dict) -> Paper:
        """解析论文数据"""
        ext_ids = data.get("externalIds") or {}

        # 作者
        authors = [a.get("name", "") for a in (data.get("authors") or []) if a.get("name")]

        # PDF URL
        pdf_url = data.get("openAccessPdf", {}).get("url")

        return Paper(
            title=data.get("title"),
            authors=authors,
            year=data.get("year"),
            venue=data.get("venue"),
            abstract=(data.get("abstract") or "")[:500] if data.get("abstract") else None,
            doi=ext_ids.get("DOI"),
            arxiv_id=ext_ids.get("ArXiv"),
            s2_id=data.get("paperId"),
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        if query.search_type == SearchType.DOI:
            url = self._build_doi_url(query.query)
        else:
            url = self._build_search_url(query.query, query.max_results)

        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            papers = []

            if query.search_type == SearchType.DOI:
                # DOI 查询返回单个论文
                if "paperId" in data:
                    papers.append(self._parse_paper(data))
            else:
                # 搜索返回多个论文
                for item in data.get("data", []):
                    papers.append(self._parse_paper(item))

            return ProviderResult(
                papers=papers[:query.max_results],
                source=self.name(),
                total=data.get("total"),
                has_more=len(papers) >= query.max_results,
            )

        except Exception as e:
            return ProviderResult(
                papers=[],
                source=self.name(),
                error=str(e),
            )