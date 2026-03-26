"""
Sci-Hub Provider

优先级: 10 (最后备选)
支持全文: 是
注意: 仅作为获取全文的备选方案
"""

import re
import urllib.parse
import urllib.request

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType


class SciHubProvider(BaseProvider):
    """Sci-Hub 数据源 (仅作为备选)"""

    TIMEOUT = 30

    # Sci-Hub 镜像列表
    MIRRORS = [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru",
        "https://sci-hub.tw",
        "https://sci-hub.ren",
    ]

    # User-Agent 轮换
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    ]

    @classmethod
    def name(cls) -> str:
        return "sci_hub"

    @classmethod
    def priority(cls) -> int:
        return 10  # 最低优先级

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.DOI]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def _clean_doi(self, doi: str) -> str:
        """清理 DOI 格式"""
        return (doi.strip()
                .replace("doi:", "")
                .replace("https://doi.org/", "")
                .replace("http://dx.doi.org/", ""))

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索 - 仅支持 DOI"""
        if query.search_type != SearchType.DOI:
            return ProviderResult(
                papers=[],
                source=self.name(),
                has_more=False,
            )

        clean_doi = self._clean_doi(query.query)

        # 尝试各个镜像
        for mirror in self.MIRRORS:
            try:
                url = f"{mirror}/{urllib.parse.quote(clean_doi)}"
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": self.USER_AGENTS[0],
                        "Accept": "text/html,application/xhtml+xml",
                    }
                )
                with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                    html = resp.read().decode()

                # 检查是否有错误
                if "article not found" in html.lower() or "no fulltext" in html.lower():
                    continue

                # 提取 PDF URL
                pdf_match = re.search(r'(?:src|href)=["\']([^"\']*\.pdf[^"\']*)["\']', html)
                if pdf_match:
                    pdf_url = pdf_match.group(1)
                    if pdf_url.startswith("//"):
                        pdf_url = f"https:{pdf_url}"

                    return ProviderResult(
                        papers=[Paper(
                            doi=clean_doi,
                            pdf_url=pdf_url,
                            source=self.name(),
                        )],
                        source=self.name(),
                        has_more=False,
                    )

            except Exception:
                continue

        return ProviderResult(
            papers=[],
            source=self.name(),
            has_more=False,
        )