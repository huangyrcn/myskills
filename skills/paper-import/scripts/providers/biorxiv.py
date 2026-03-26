"""
bioRxiv Provider

API 文档: https://api.biorxiv.org
优先级: 75 (生物学预印本)
支持全文: 是
"""

import json
import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class BiorxivProvider(BaseProvider):
    """bioRxiv/medRxiv 预印本数据源"""

    BASE_URL = "https://api.biorxiv.org"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "biorxiv"

    @classmethod
    def priority(cls) -> int:
        return 75

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.DOI, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _extract_biorxiv_doi(self, doi_or_url: str) -> str:
        """从各种格式提取 bioRxiv DOI"""
        if "10.1101/" in doi_or_url:
            start = doi_or_url.find("10.1101/")
            doi_part = doi_or_url[start:]
            # 移除版本后缀
            if "v" in doi_part[8:]:
                v_pos = doi_part.find("v", 8)
                return doi_part[:v_pos]
            return doi_part
        return None

    def _parse_paper(self, item: dict) -> Paper:
        """解析论文数据"""
        # 作者 (逗号分隔)
        authors = []
        if item.get("authors"):
            authors = [a.strip() for a in item["authors"].split(",") if a.strip()]

        # 年份
        year = None
        if item.get("date"):
            year = int(item["date"].split("-")[0])

        # PDF URL
        pdf_url = None
        if item.get("doi") and item.get("date"):
            pdf_url = (
                f"https://www.biorxiv.org/content/biorxiv/early/"
                f"{item['date'].replace('-', '/')}/{item['doi']}.full.pdf"
            )

        # venue
        venue = None
        if item.get("server"):
            venue = f"{item['server']} preprint"

        return Paper(
            title=item.get("title"),
            authors=authors,
            year=year,
            venue=venue,
            abstract=item.get("abstract", "")[:500] if item.get("abstract") else None,
            doi=item.get("doi"),
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        papers = []

        try:
            if query.search_type == SearchType.DOI:
                # DOI 查询
                biorxiv_doi = self._extract_biorxiv_doi(query.query)
                if biorxiv_doi:
                    url = f"{self.BASE_URL}/details/biorxiv/{biorxiv_doi}"
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "resolve-paper-metadata/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                        data = json.loads(resp.read().decode())

                    if data.get("collection"):
                        papers.append(self._parse_paper(data["collection"][0]))
            else:
                # bioRxiv 不支持文本搜索，返回空
                pass

            return ProviderResult(
                papers=papers,
                source=self.name(),
                has_more=False,
            )

        except Exception as e:
            return ProviderResult(
                papers=[],
                source=self.name(),
                error=str(e),
            )