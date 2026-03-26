"""
CORE Provider

API 文档: https://api.core.ac.uk/docs
优先级: 86 (开放获取聚合)
支持全文: 是
"""

import json
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class CoreProvider(BaseProvider):
    """CORE 开放获取数据源"""

    BASE_URL = "https://api.core.ac.uk/v3"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "core"

    @classmethod
    def priority(cls) -> int:
        return 86

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.DOI, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _parse_work(self, data: dict) -> Paper:
        """解析论文数据"""
        # DOI
        doi = data.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "")

        # 作者
        authors = []
        for auth in data.get("authorships", []):
            name = auth.get("author", {}).get("display_name")
            if name:
                authors.append(name)

        # 摘要
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

        # CORE ID
        core_id = None
        if data.get("id"):
            core_id = data["id"].replace("https://openalex.org/", "")

        return Paper(
            title=data.get("title"),
            authors=authors,
            year=data.get("publication_year"),
            venue=venue,
            abstract=abstract,
            doi=doi,
            core_id=core_id,
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        try:
            if query.search_type == SearchType.DOI:
                # DOI 查询
                doi = query.query
                if not doi.startswith("http"):
                    doi = f"https://doi.org/{doi}"
                filter_str = f"doi:{doi}"
            elif query.search_type == SearchType.TITLE:
                filter_str = f"title.search:{query.query}"
            elif query.search_type == SearchType.AUTHOR:
                filter_str = f"authorships.author.display_name.search:{query.query}"
            else:
                filter_str = f"default.search:{query.query}"

            encoded = urllib.parse.quote(filter_str)
            url = f"{self.BASE_URL}/search/works?q={encoded}&limit={query.max_results}"

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "resolve-paper-metadata/5.0 (mailto:research@example.com)"}
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            papers = []
            for work in data.get("results", []):
                papers.append(self._parse_work(work))

            return ProviderResult(
                papers=papers,
                source=self.name(),
                total=data.get("meta", {}).get("count"),
                has_more=len(papers) >= query.max_results,
            )

        except Exception as e:
            return ProviderResult(
                papers=[],
                source=self.name(),
                error=str(e),
            )