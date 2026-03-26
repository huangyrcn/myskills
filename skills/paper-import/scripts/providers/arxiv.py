"""
arXiv Provider

API 文档: https://info.arxiv.org/help/api/index.html
优先级: 80 (高，CS/物理/数学)
支持全文: 是
"""

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class ArxivProvider(BaseProvider):
    """arXiv 数据源"""

    BASE_URL = "https://export.arxiv.org/api/query"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "arxiv"

    @classmethod
    def priority(cls) -> int:
        return 80

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS, SearchType.ARXIV]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _build_search_query(self, query: SearchQuery) -> str:
        """构建搜索查询字符串"""
        q = query.query

        if query.search_type == SearchType.TITLE:
            return f'ti:"{q}"'
        elif query.search_type == SearchType.AUTHOR:
            return f'au:"{q}"'
        else:
            # AUTO, KEYWORDS: 搜索所有字段
            return f'all:"{q}"'

    def _parse_entry(self, entry: ET.Element) -> Paper:
        """解析单个 entry"""
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # 标题
        title_elem = entry.find("atom:title", ns)
        title = title_elem.text.strip() if title_elem is not None and title_elem.text else None

        # 作者
        authors = []
        for author in entry.findall("atom:author", ns):
            name = author.find("atom:name", ns)
            if name is not None and name.text:
                authors.append(name.text.strip())

        # 摘要
        summary_elem = entry.find("atom:summary", ns)
        abstract = summary_elem.text.strip()[:500] if summary_elem is not None and summary_elem.text else None

        # 年份
        year = None
        pub_elem = entry.find("atom:published", ns)
        if pub_elem is not None and pub_elem.text:
            match = re.match(r"(\d{4})", pub_elem.text)
            if match:
                year = int(match.group(1))

        # arXiv ID
        arxiv_id = None
        id_elem = entry.find("atom:id", ns)
        if id_elem is not None and id_elem.text:
            match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)$", id_elem.text)
            if match:
                arxiv_id = match.group(1)

        # PDF URL
        pdf_url = None
        if arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

        return Paper(
            title=title,
            authors=authors,
            year=year,
            venue="arXiv",
            abstract=abstract,
            arxiv_id=arxiv_id,
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        # arXiv ID 直接查询 id_list
        if query.search_type == SearchType.ARXIV:
            url = f"{self.BASE_URL}?id_list={urllib.parse.quote(query.query)}&max_results=1"
        else:
            search_query = self._build_search_query(query)
            encoded = urllib.parse.quote(search_query)
            url = f"{self.BASE_URL}?search_query={encoded}&max_results={query.max_results}&sortBy=relevance"

        try:
            with urllib.request.urlopen(url, timeout=self.TIMEOUT) as resp:
                xml_text = resp.read().decode()

            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            papers = []
            for entry in root.findall("atom:entry", ns):
                papers.append(self._parse_entry(entry))

            return ProviderResult(
                papers=papers,
                source=self.name(),
                has_more=len(papers) >= query.max_results,
            )

        except Exception as e:
            return ProviderResult(
                papers=[],
                source=self.name(),
                error=str(e),
            )