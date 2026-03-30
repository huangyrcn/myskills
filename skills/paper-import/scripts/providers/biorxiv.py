"""
bioRxiv Provider

API 文档: https://api.biorxiv.org
优先级: 75 (生物学预印本)
支持全文: 是

标题搜索: 通过网页爬取 /search/ 实现 (使用 curl 绕过 Cloudflare)
DOI 查询: 通过 API /details/ 实现
"""

import json
import re
import subprocess
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class BiorxivSearchParser(HTMLParser):
    """解析 bioRxiv 搜索结果页面"""

    def __init__(self):
        super().__init__()
        self.papers = []
        self.current_paper = None
        self.in_title_span = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        class_attr = attrs_dict.get("class", "")

        # 标题链接
        if tag == "a" and "highwire-cite-linked-title" in class_attr:
            self.current_paper = {
                "title": "",
                "doi": None,
                "url": attrs_dict.get("href", ""),
            }

        # 标题 span
        elif tag == "span" and self.current_paper is not None:
            if "highwire-cite-title" in class_attr:
                self.in_title_span = True
            elif "highwire-cite-metadata-doi" in class_attr:
                self.current_paper["_in_doi"] = True

    def handle_endtag(self, tag):
        if tag == "span":
            self.in_title_span = False

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return

        # 标题
        if self.in_title_span and self.current_paper is not None:
            self.current_paper["title"] = data

        # DOI
        if self.current_paper is not None and self.current_paper.get("_in_doi"):
            match = re.search(r"10\.\d+/[^\s]+", data)
            if match:
                self.current_paper["doi"] = match.group(0)
                # 移除临时标记，保存结果
                del self.current_paper["_in_doi"]
                self.papers.append(self.current_paper)
                self.current_paper = None


class BiorxivProvider(BaseProvider):
    """bioRxiv/medRxiv 预印本数据源"""

    BASE_URL = "https://api.biorxiv.org"
    SEARCH_URL = "https://www.biorxiv.org/search"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "biorxiv"

    @classmethod
    def priority(cls) -> int:
        return 75

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.DOI, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _extract_biorxiv_doi(self, doi_or_url: str) -> str:
        """从各种格式提取 bioRxiv DOI"""
        if "10.1101/" in doi_or_url or "10.64898/" in doi_or_url:
            start = doi_or_url.find("10.")
            doi_part = doi_or_url[start:]
            # 移除版本后缀
            if "v" in doi_part[10:]:
                v_pos = doi_part.find("v", 10)
                return doi_part[:v_pos]
            return doi_part
        return None

    def _parse_paper(self, item: dict) -> Paper:
        """解析 API 返回的论文数据"""
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

    def _search_by_doi(self, doi: str) -> list[Paper]:
        """通过 DOI 查询 (使用 API)"""
        biorxiv_doi = self._extract_biorxiv_doi(doi)
        if not biorxiv_doi:
            return []

        # 尝试 biorxiv 和 medrxiv
        for server in ["biorxiv", "medrxiv"]:
            try:
                url = f"{self.BASE_URL}/details/{server}/{biorxiv_doi}"
                req = urllib.request.Request(
                    url, headers={"User-Agent": "resolve-paper-metadata/5.0"}
                )
                with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                    data = json.loads(resp.read().decode())

                if data.get("collection"):
                    paper = self._parse_paper(data["collection"][0])
                    return [paper]
            except Exception:
                continue

        return []

    def _search_by_query(self, query: str, max_results: int = 10) -> list[Paper]:
        """通过标题/关键词搜索 (网页爬取)"""
        # 构建搜索 URL
        encoded_query = urllib.parse.quote(query)
        search_url = f"{self.SEARCH_URL}/{encoded_query}%20numresults%3A{max_results}%20sort%3Arelevance"

        try:
            # 使用 curl 绕过 Cloudflare
            result = subprocess.run(
                [
                    "curl", "-s", "-L",
                    "-A", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "-H", "Accept: text/html,application/xhtml+xml",
                    search_url
                ],
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )
            html = result.stdout

            if not html or "highwire-cite-linked-title" not in html:
                return []

            # 解析 HTML
            parser = BiorxivSearchParser()
            parser.feed(html)

            papers = []
            for item in parser.papers[:max_results]:
                # 提取年份 (从 DOI)
                year = None
                if item.get("doi"):
                    # DOI 格式: 10.1101/2025.06.23.661103 或 10.64898/2026.03.23.713701
                    match = re.search(r"/(\d{4})\.", item["doi"])
                    if match:
                        year = int(match.group(1))

                # PDF URL
                pdf_url = None
                if item.get("url"):
                    pdf_url = f"https://www.biorxiv.org/content{item['url']}.full.pdf"

                papers.append(Paper(
                    title=item.get("title", "").strip(),
                    authors=[],  # 网页搜索不返回作者
                    year=year,
                    venue="bioRxiv preprint",
                    doi=item.get("doi"),
                    pdf_url=pdf_url,
                    source=self.name(),
                ))

            return papers

        except Exception as e:
            return []

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        try:
            if query.search_type == SearchType.DOI:
                papers = self._search_by_doi(query.query)
            else:
                # 标题/关键词搜索
                papers = self._search_by_query(query.query, query.max_results)

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