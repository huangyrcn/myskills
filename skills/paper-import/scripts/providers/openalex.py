"""
OpenAlex Provider

API 文档: https://docs.openalex.org/
优先级: 70 (覆盖面广)
支持全文: 是 (开放获取)
"""

import json
import os
import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class OpenAlexProvider(BaseProvider):
    """OpenAlex 数据源"""

    BASE_URL = "https://api.openalex.org/works"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "openalex"

    @classmethod
    def priority(cls) -> int:
        return 70

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.DOI, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _get_headers(self) -> dict:
        return {"User-Agent": "resolve-paper-metadata/5.0 (mailto:research@example.com)"}

    def _get_params(self, query: SearchQuery) -> dict:
        """构建请求参数。"""
        q = query.query.strip()
        params = {
            "per_page": query.max_results,
            "sort": "relevance_score:desc",
        }

        api_key = os.getenv("OPENALEX_API_KEY")
        if api_key:
            params["api_key"] = api_key

        if query.search_type == SearchType.DOI:
            return params

        elif query.search_type == SearchType.TITLE:
            params["search"] = q
            return params

        elif query.search_type == SearchType.AUTHOR:
            params["filter"] = f"authorships.author.display_name.search:{q}"
            return params

        else:
            params["search"] = q
            return params

    def _extract_arxiv_id(self, data: dict) -> str | None:
        """从 OpenAlex work 中提取 arXiv ID。"""
        ids = data.get("ids") or {}
        candidates = [
            ids.get("arxiv"),
            ids.get("doi"),
            data.get("doi"),
        ]

        primary_location = data.get("primary_location") or {}
        best_oa_location = data.get("best_oa_location") or {}
        candidates.extend([
            primary_location.get("landing_page_url"),
            primary_location.get("pdf_url"),
            best_oa_location.get("landing_page_url"),
            best_oa_location.get("pdf_url"),
        ])

        for location in data.get("locations") or []:
            candidates.extend([
                location.get("landing_page_url"),
                location.get("pdf_url"),
            ])

        for value in candidates:
            if not value:
                continue
            match = re.search(
                r"(?:10\.48550/arxiv\.|arxiv\.org/(?:abs|pdf|e-print)/)"
                r"([a-z\-]+(?:\.[a-z\-]+)?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?",
                str(value),
                re.IGNORECASE,
            )
            if match:
                return match.group(1)
        return None

    def _parse_work(self, data: dict) -> Paper:
        """解析论文数据"""
        ids = data.get("ids") or {}

        # DOI: 优先使用 ids.doi，它比顶层 doi 更接近 canonical identifier
        doi = ids.get("doi") or data.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "")

        # 作者
        authors = []
        for auth in data.get("authorships", []):
            name = auth.get("author", {}).get("display_name")
            if name:
                authors.append(name)

        # 摘要 (从 inverted index 重建)
        abstract = None
        idx = data.get("abstract_inverted_index")
        if idx:
            words = {}
            for word, positions in idx.items():
                for pos in positions:
                    words[pos] = word
            abstract = " ".join(words[p] for p in sorted(words.keys()))[:500]

        # venue
        venue = None
        loc = data.get("primary_location")
        if loc and isinstance(loc, dict):
            src = loc.get("source")
            if src and isinstance(src, dict):
                venue = src.get("display_name")

        # PDF URL
        pdf_url = None
        if loc and isinstance(loc, dict):
            pdf_url = loc.get("pdf_url")
        if not pdf_url:
            best_oa = data.get("best_oa_location")
            if best_oa and isinstance(best_oa, dict):
                pdf_url = best_oa.get("pdf_url")

        # OpenAlex ID
        openalex_id = None
        if data.get("id"):
            openalex_id = data["id"].replace("https://openalex.org/", "")

        return Paper(
            title=data.get("title"),
            authors=authors,
            year=data.get("publication_year"),
            venue=venue,
            abstract=abstract,
            doi=doi,
            arxiv_id=self._extract_arxiv_id(data),
            openalex_id=openalex_id,
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        params = self._get_params(query)

        if query.search_type == SearchType.DOI:
            doi = query.query.strip()
            if not doi.startswith("http"):
                doi = f"https://doi.org/{doi}"
            path = urllib.parse.quote(doi, safe="")
            query_string = urllib.parse.urlencode({k: v for k, v in params.items() if k == "api_key"})
            url = f"{self.BASE_URL}/{path}"
            if query_string:
                url = f"{url}?{query_string}"
        else:
            url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            papers = []

            if query.search_type == SearchType.DOI:
                if data.get("id"):
                    papers.append(self._parse_work(data))
            else:
                for work in data.get("results", []):
                    papers.append(self._parse_work(work))

            return ProviderResult(
                papers=papers,
                source=self.name(),
                total=data.get("meta", {}).get("count") if isinstance(data, dict) else None,
                has_more=len(papers) >= query.max_results,
            )

        except Exception as e:
            return ProviderResult(
                papers=[],
                source=self.name(),
                error=str(e),
            )
