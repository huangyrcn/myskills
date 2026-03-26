"""
Unpaywall Provider

API 文档: https://unpaywall.org/products/api
优先级: 87 (开放获取查找)
支持全文: 是
"""

import json
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class UnpaywallProvider(BaseProvider):
    """Unpaywall 开放获取数据源"""

    BASE_URL = "https://api.unpaywall.org/v2"
    TIMEOUT = 30
    EMAIL = "resolve-paper-metadata@academic-tool.org"

    @classmethod
    def name(cls) -> str:
        return "unpaywall"

    @classmethod
    def priority(cls) -> int:
        return 87

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.DOI]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _parse_response(self, data: dict) -> Paper:
        """解析响应数据"""
        # 作者
        authors = []
        for auth in data.get("z_authors", []):
            given = auth.get("given", "")
            family = auth.get("family", "")
            if given and family:
                authors.append(f"{given} {family}")
            elif given:
                authors.append(given)
            elif family:
                authors.append(family)

        # PDF URL
        pdf_url = None
        if data.get("best_oa_location"):
            pdf_url = data["best_oa_location"].get("url_for_pdf")
        if not pdf_url and data.get("oa_locations"):
            for loc in data["oa_locations"]:
                if loc.get("url_for_pdf"):
                    pdf_url = loc["url_for_pdf"]
                    break

        return Paper(
            doi=data.get("doi"),
            title=data.get("title"),
            authors=authors,
            year=data.get("year"),
            venue=data.get("journal_name"),
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索 - 仅支持 DOI"""
        if query.search_type != SearchType.DOI:
            return ProviderResult(
                papers=[],
                source=self.name(),
                has_more=False,
                error="Unpaywall only supports DOI search",
            )

        try:
            doi = query.query
            if doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")
            elif doi.startswith("http://dx.doi.org/"):
                doi = doi.replace("http://dx.doi.org/", "")

            url = f"{self.BASE_URL}/{urllib.parse.quote(doi)}?email={self.EMAIL}"

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "resolve-paper-metadata/5.0"}
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            # 只返回开放获取的论文
            if data.get("is_oa"):
                return ProviderResult(
                    papers=[self._parse_response(data)],
                    source=self.name(),
                    has_more=False,
                )

            return ProviderResult(
                papers=[],
                source=self.name(),
                has_more=False,
            )

        except Exception as e:
            return ProviderResult(
                papers=[],
                source=self.name(),
                error=str(e),
            )