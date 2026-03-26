"""
IACR - 密码学预印本

网站: https://eprint.iacr.org/
支持: 密码学、信息安全
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
from bs4 import BeautifulSoup
import logging
import random

logger = logging.getLogger(__name__)


class IacrProvider(BaseProvider):
    """IACR ePrint 密码学预印本搜索"""

    SEARCH_URL = "https://eprint.iacr.org/search"
    BASE_URL = "https://eprint.iacr.org"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    ]

    @classmethod
    def name(cls) -> str:
        return "iacr"

    @classmethod
    def priority(cls) -> int:
        return 72  # 密码学专业

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return True

    def search(self, query: SearchQuery) -> ProviderResult:
        headers = {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html',
        }

        params = {
            'q': query.query,
        }

        try:
            resp = requests.get(self.SEARCH_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            papers = []

            # IACR 搜索结果结构
            results = soup.find_all('div', class_='result') or soup.find_all('div', class_='paper')

            for item in results[:query.max_results]:
                paper = self._parse_paper(item)
                if paper:
                    papers.append(paper)

            return ProviderResult(papers=papers, source=self.name(), total=len(papers))

        except Exception as e:
            logger.error(f"IACR search error: {e}")
            return ProviderResult(papers=[], source=self.name(), error=str(e))

    def _parse_paper(self, item) -> Optional[Paper]:
        """解析单个论文"""
        try:
            # 标题和链接
            title_elem = item.find('a')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            href = title_elem.get('href', '')
            paper_id = href.split('/')[-1] if href else ''

            # PDF URL
            pdf_url = f"{self.BASE_URL}/{paper_id}.pdf" if paper_id else ''

            # 作者和日期 (从文本中提取)
            text = item.get_text()

            return Paper(
                title=title,
                authors=[],  # IACR 页面结构需要更复杂的解析
                year=None,
                pdf_url=pdf_url,
                source=self.name(),
            )
        except Exception as e:
            logger.debug(f"IACR parse error: {e}")
            return None