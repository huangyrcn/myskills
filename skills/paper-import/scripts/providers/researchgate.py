"""
ResearchGate Provider

API 文档: https://www.researchgate.net
优先级: 70 (受限功能)
支持全文: 否 (需要认证)
"""

import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class ResearchGateProvider(BaseProvider):
    """ResearchGate 数据源 (受限功能)"""

    BASE_URL = "https://www.researchgate.net"
    TIMEOUT = 30

    @classmethod
    def name(cls) -> str:
        return "researchgate"

    @classmethod
    def priority(cls) -> int:
        return 70

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR]

    @classmethod
    def supports_full_text(cls) -> bool:
        return False

    def _is_researchgate_url(self, url: str) -> bool:
        """检查是否是 ResearchGate URL"""
        return "researchgate.net/publication/" in url or "researchgate.net/profile/" in url

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索 - 限制功能以尊重 ToS"""
        # ResearchGate 搜索受限，返回空结果
        return ProviderResult(
            papers=[],
            source=self.name(),
            has_more=False,
            error="Limited functionality to respect ToS",
        )