"""
PubMed Central Provider

API 文档: https://www.ncbi.nlm.nih.gov/pmc/
优先级: 89 (生物医学权威)
支持全文: 是
"""

import json
import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class PubmedCentralProvider(BaseProvider):
    """PubMed Central 生物医学数据源"""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    TIMEOUT = 30

    # 常见生物医学期刊 DOI 前缀
    BIOMEDICAL_PREFIXES = [
        "10.1371",  # PLOS
        "10.1038",  # Nature
        "10.1016",  # Elsevier
        "10.1186",  # BioMed Central
        "10.3389",  # Frontiers
        "10.1172",  # JCI
        "10.1158",  # AACR
        "10.1084",  # Rockefeller
        "10.1073",  # PNAS
        "10.1056",  # NEJM
        "10.1001",  # JAMA
        "10.1126",  # Science
    ]

    @classmethod
    def name(cls) -> str:
        return "pubmed_central"

    @classmethod
    def priority(cls) -> int:
        return 89

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.DOI, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _is_biomedical_doi(self, doi: str) -> bool:
        """检查是否是生物医学 DOI"""
        return any(doi.startswith(prefix) for prefix in self.BIOMEDICAL_PREFIXES)

    def _build_query(self, query: SearchQuery) -> str:
        """构建 PMC 查询"""
        if query.search_type == SearchType.DOI:
            return f"{query.query}[doi]"
        elif query.search_type == SearchType.TITLE:
            return f"{query.query}[title]"
        elif query.search_type == SearchType.AUTHOR:
            return f"{query.query}[author]"
        else:
            return query.query

    def _parse_article(self, article: dict) -> Paper:
        """解析论文数据"""
        # 作者
        authors = []
        for auth in article.get("authors", []):
            if auth.get("name"):
                authors.append(auth["name"])

        # DOI
        doi = article.get("doi")
        if not doi:
            for aid in article.get("articleids", []):
                if aid.get("idtype") == "doi":
                    doi = aid["value"]
                    break

        # 年份
        year = None
        if article.get("pubdate"):
            match = re.search(r"(\d{4})", article["pubdate"])
            if match:
                year = int(match.group(1))

        # PDF URL
        pdf_url = None
        if article.get("pmcid"):
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{article['pmcid']}/pdf/"

        return Paper(
            title=article.get("title"),
            authors=authors,
            year=year,
            venue=article.get("fulljournalname"),
            abstract=article.get("abstract", "")[:500] if article.get("abstract") else None,
            doi=doi,
            pmcid=article.get("pmcid"),
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        try:
            # 构建搜索查询
            search_query = self._build_query(query)

            # 第一步：搜索获取 PMC ID 列表
            search_url = (
                f"{self.BASE_URL}/esearch.fcgi?"
                f"db=pmc&term={urllib.parse.quote(search_query)}&retmode=json&"
                f"retmax={query.max_results}&sort=relevance"
            )

            req = urllib.request.Request(
                search_url,
                headers={"User-Agent": "resolve-paper-metadata/5.0"}
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            id_list = data.get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return ProviderResult(
                    papers=[],
                    source=self.name(),
                    has_more=False,
                )

            # 第二步：获取论文详情
            fetch_url = (
                f"{self.BASE_URL}/esummary.fcgi?"
                f"db=pmc&id={','.join(id_list)}&retmode=json"
            )

            with urllib.request.urlopen(fetch_url, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            papers = []
            for article_id, article in data.get("result", {}).items():
                if article_id != "uids":
                    papers.append(self._parse_article(article))

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