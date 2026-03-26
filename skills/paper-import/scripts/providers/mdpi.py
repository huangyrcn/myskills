"""
MDPI Provider

API 文档: https://www.mdpi.com
优先级: 75 (开放获取期刊)
支持全文: 是
"""

import json
import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class MdpiProvider(BaseProvider):
    """MDPI 开放获取期刊数据源"""

    BASE_URL = "https://www.mdpi.com"
    TIMEOUT = 30

    # 常见 MDPI 期刊映射
    JOURNAL_MAP = {
        "sensors": "Sensors",
        "materials": "Materials",
        "sustainability": "Sustainability",
        "applsci": "Applied Sciences",
        "molecules": "Molecules",
        "ijms": "International Journal of Molecular Sciences",
        "remotesensing": "Remote Sensing",
        "energies": "Energies",
        "water": "Water",
        "forests": "Forests",
        "buildings": "Buildings",
        "electronics": "Electronics",
        "polymers": "Polymers",
        "nutrients": "Nutrients",
        "jcm": "Journal of Clinical Medicine",
        "cancers": "Cancers",
    }

    @classmethod
    def name(cls) -> str:
        return "mdpi"

    @classmethod
    def priority(cls) -> int:
        return 75

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.DOI, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _extract_doi(self, text: str) -> str:
        """从文本提取 DOI"""
        match = re.search(r"10\.\d+/[^\s]+", text)
        return match.group(0) if match else None

    def _extract_journal(self, url: str) -> str:
        """从 URL 提取期刊名"""
        for key, name in self.JOURNAL_MAP.items():
            if key in url.lower():
                return name
        return "MDPI Journal"

    def _extract_year(self, date_str: str) -> int:
        """从日期字符串提取年份"""
        if not date_str:
            return None
        match = re.search(r"(\d{4})", date_str)
        return int(match.group(1)) if match else None

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索 - MDPI 使用 HTML 解析"""
        papers = []

        try:
            # MDPI 没有公开 API，需要 HTML 解析
            # 这里简化实现，主要依赖其他数据源
            search_url = f"{self.BASE_URL}/search?q={urllib.parse.quote(query.query)}&sort=relevance"

            req = urllib.request.Request(
                search_url,
                headers={"User-Agent": "resolve-paper-metadata/5.0"}
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                html = resp.read().decode()

            # 简单的 DOI 提取
            doi_pattern = r"10\.\d{4,}/[a-zA-Z0-9.]+"
            dois = list(set(re.findall(doi_pattern, html)))[:query.max_results]

            for doi in dois:
                papers.append(Paper(
                    doi=doi,
                    source=self.name(),
                ))

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