"""
Crossref Provider

API 文档: https://api.crossref.org
优先级: 90 (DOI 权威来源)
支持全文: 否
"""

import json
import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class CrossrefProvider(BaseProvider):
    """Crossref 数据源"""

    BASE_URL = "https://api.crossref.org/works"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "crossref"

    @classmethod
    def priority(cls) -> int:
        return 90

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.DOI, SearchType.TITLE, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return False

    def _safe_get_year(self, item: dict, *keys) -> int:
        """安全提取年份"""
        for key in keys:
            val = item.get(key)
            if val is None:
                continue
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                match = re.match(r"(\d{4})", val)
                if match:
                    return int(match.group(1))
            if isinstance(val, dict):
                date_parts = val.get("date-parts")
                if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
                    first = date_parts[0]
                    if isinstance(first, list) and first and first[0]:
                        return first[0]
        return None

    def _parse_item(self, item: dict) -> Paper:
        """解析论文数据"""
        # 标题
        title = None
        titles = item.get("title", [])
        if titles:
            title = " ".join(titles)

        # 作者
        authors = []
        for a in item.get("author", []):
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if name:
                authors.append(name)

        # 年份
        year = self._safe_get_year(item, "published-print", "published-online", "created")

        # venue
        venue = None
        containers = item.get("container-title", [])
        if containers:
            venue = " ".join(containers)

        # 摘要 (可能有 JATS XML 标签)
        abstract = item.get("abstract")
        if abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract)[:500]

        return Paper(
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            abstract=abstract,
            doi=item.get("DOI"),
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        if query.search_type == SearchType.DOI:
            # DOI 直接查询
            url = f"{self.BASE_URL}/{urllib.parse.quote(query.query)}"
        else:
            # 标题搜索
            encoded = urllib.parse.quote(query.query)
            url = f"{self.BASE_URL}?query.title={encoded}&rows={query.max_results}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "resolve-paper-metadata/5.0 (mailto:research@example.com)"}
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            papers = []

            if query.search_type == SearchType.DOI:
                # DOI 查询返回单个论文
                if "message" in data:
                    papers.append(self._parse_item(data["message"]))
            else:
                # 搜索返回多个论文
                items = data.get("message", {}).get("items", [])
                for item in items:
                    papers.append(self._parse_item(item))

            return ProviderResult(
                papers=papers,
                source=self.name(),
                total=data.get("message", {}).get("total-results"),
                has_more=len(papers) >= query.max_results,
            )

        except Exception as e:
            return ProviderResult(
                papers=[],
                source=self.name(),
                error=str(e),
            )