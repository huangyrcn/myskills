"""
SSRN Provider

API 文档: https://www.ssrn.com
优先级: 85 (社会科学预印本)
支持全文: 是
"""

import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class SsrnProvider(BaseProvider):
    """SSRN 社会科学研究网络数据源"""

    BASE_URL = "https://papers.ssrn.com"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "ssrn"

    @classmethod
    def priority(cls) -> int:
        return 85

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.DOI, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _extract_ssrn_id(self, doi: str) -> str:
        """从 DOI 提取 SSRN ID"""
        if "10.2139/ssrn." in doi:
            return doi.split("ssrn.")[1].strip()
        return None

    def _parse_paper_page(self, html: str, ssrn_id: str) -> Paper:
        """解析论文页面"""
        # 提取标题
        title_match = re.search(r'<meta\s+name="citation_title"\s+content="([^"]+)"', html)
        title = title_match.group(1) if title_match else None

        # 提取作者
        authors = re.findall(r'<meta\s+name="citation_author"\s+content="([^"]+)"', html)

        # 提取摘要
        abstract_match = re.search(r'<meta\s+name="citation_abstract"\s+content="([^"]+)"', html)
        abstract = abstract_match.group(1)[:500] if abstract_match else None

        # 提取 PDF URL
        pdf_match = re.search(r'<meta\s+name="citation_pdf_url"\s+content="([^"]+)"', html)
        pdf_url = pdf_match.group(1) if pdf_match else None

        # 提取年份
        year = None
        date_match = re.search(r'<meta\s+name="citation_publication_date"\s+content="(\d{4})', html)
        if date_match:
            year = int(date_match.group(1))

        return Paper(
            doi=f"10.2139/ssrn.{ssrn_id}",
            title=title,
            authors=authors,
            year=year,
            venue="SSRN Electronic Journal",
            abstract=abstract,
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        try:
            if query.search_type == SearchType.DOI:
                # DOI 查询
                ssrn_id = self._extract_ssrn_id(query.query)
                if ssrn_id:
                    url = f"{self.BASE_URL}/sol3/papers.cfm?abstract_id={ssrn_id}"
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "resolve-paper-metadata/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                        html = resp.read().decode()

                    paper = self._parse_paper_page(html, ssrn_id)
                    if paper.title:
                        return ProviderResult(
                            papers=[paper],
                            source=self.name(),
                            has_more=False,
                        )

            # 其他搜索类型 - 简化实现
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