"""
OpenReview Provider

API 文档: https://docs.openreview.net/reference/api-v2
优先级: 80 (ML/AI 顶会: NeurIPS, ICLR, ICML)
支持全文: 是

API V2 端点:
- 登录: POST /login
- 搜索: GET /notes/search?term=xxx
"""

import json
import os
import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class OpenReviewProvider(BaseProvider):
    """OpenReview 数据源 (API V2)"""

    BASE_URL = "https://api2.openreview.net"
    TIMEOUT = 30

    def __init__(self):
        self.token = None
        self._login()

    def _login(self):
        """登录获取 token"""
        username = os.environ.get("OPENREVIEW_USERNAME")
        password = os.environ.get("OPENREVIEW_PASSWORD")

        if not username or not password:
            return

        try:
            url = f"{self.BASE_URL}/login"
            data = json.dumps({"id": username, "password": password}).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                result = json.loads(resp.read().decode())
                self.token = result.get("token")
        except Exception:
            pass

    @classmethod
    def name(cls) -> str:
        return "openreview"

    @classmethod
    def priority(cls) -> int:
        return 80

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _get_field(self, content: dict, field: str):
        """获取字段值 (处理 OpenReview 的嵌套结构)"""
        val = content.get(field, {})
        if isinstance(val, dict):
            return val.get("value")
        return val

    def _parse_note(self, note: dict) -> Paper:
        """解析 note 数据"""
        content = note.get("content", {})

        # 标题
        title = self._get_field(content, "title")

        # 作者
        authors = self._get_field(content, "authors") or []

        # 摘要
        abstract = self._get_field(content, "abstract")
        if abstract:
            abstract = abstract[:500]

        # venue
        venue = self._get_field(content, "venue")
        if not venue:
            venueid = self._get_field(content, "venueid")
            if venueid:
                # 从 venueid 提取会议名
                match = re.search(r"([^/]+)/(\d{4})", venueid)
                if match:
                    venue = f"{match.group(1)} {match.group(2)}"

        # 年份 (从 venue 或 venueid 提取)
        year = None
        if venue:
            match = re.search(r"\b(20\d{2})\b", venue)
            if match:
                year = int(match.group(1))

        # PDF URL
        pdf_url = self._get_field(content, "pdf")
        html_url = self._get_field(content, "html")

        # DOI (从 html 或 _bibtex 提取)
        doi = None
        if html_url and "doi.org" in html_url:
            match = re.search(r"doi\.org/(.+)", html_url)
            if match:
                doi = "10." + match.group(1).split("10.")[-1] if "10." in match.group(1) else match.group(1)

        # OpenReview ID
        openreview_id = note.get("forum") or note.get("id")

        return Paper(
            title=title,
            authors=authors if isinstance(authors, list) else [authors],
            year=year,
            venue=venue,
            abstract=abstract,
            doi=doi,
            openreview_id=openreview_id,
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        if not self.token:
            return ProviderResult(
                papers=[],
                source=self.name(),
                error="OpenReview credentials not configured",
            )

        encoded = urllib.parse.quote(query.query)
        url = f"{self.BASE_URL}/notes/search?term={encoded}&limit={query.max_results}"

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "User-Agent": "resolve-paper-metadata/5.0",
                }
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            papers = []
            for note in data.get("notes", []):
                papers.append(self._parse_note(note))

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