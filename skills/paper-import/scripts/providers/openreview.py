"""
OpenReview Provider

API 文档: https://openreview.net/
优先级: 75 (ML 顶会)
支持全文: 是

覆盖会议: NeurIPS, ICLR, ICML, UAI, TMLR
"""

import json
import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class OpenReviewProvider(BaseProvider):
    """OpenReview 数据源"""

    BASE_URL = "https://api2.openreview.net"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "openreview"

    @classmethod
    def priority(cls) -> int:
        return 75

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _get_field(self, content: dict, field: str):
        """获取字段值 (处理 OpenReview 的嵌套结构)"""
        val = content.get(field)
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
        if isinstance(authors, str):
            authors = [a.strip() for a in authors.split(",")]

        # 摘要
        abstract = self._get_field(content, "abstract")
        if abstract:
            abstract = abstract[:500]

        # venue
        venue = self._get_field(content, "venue") or ""

        # 年份 (从 venue 提取)
        year = None
        if venue:
            match = re.search(r"\b(20\d{2})\b", venue)
            if match:
                year = int(match.group(1))
        if not year and note.get("pdate"):
            year = note.get("pdate") // 10000

        # PDF URL
        pdf_url = None
        pdf = self._get_field(content, "pdf")
        if pdf:
            if pdf.startswith("/"):
                pdf_url = f"https://openreview.net{pdf}"
            else:
                pdf_url = pdf

        # OpenReview ID
        openreview_id = note.get("forum") or note.get("id")

        return Paper(
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            abstract=abstract,
            openreview_id=openreview_id,
            pdf_url=pdf_url,
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        encoded = urllib.parse.quote(query.query)

        url = f"{self.BASE_URL}/notes/search?term={encoded}&limit={query.max_results}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "resolve-paper-metadata/5.0"}
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