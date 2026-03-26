"""
Google Scholar - 谷歌学术

注意: 有反爬机制，需要 proxy 或 SerpAPI
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
from bs4 import BeautifulSoup
import logging
import random
import os

logger = logging.getLogger(__name__)


class GoogleScholarProvider(BaseProvider):
    """Google Scholar 搜索 (需要 proxy)"""

    SCHOLAR_URL = "https://scholar.google.com/scholar"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    ]

    @classmethod
    def name(cls) -> str:
        return "google_scholar"

    @classmethod
    def priority(cls) -> int:
        return 50  # 低优先级，因为反爬严重

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.AUTHOR, SearchType.KEYWORDS]

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url or os.environ.get('GOOGLE_SCHOLAR_PROXY_URL', '')

    def search(self, query: SearchQuery) -> ProviderResult:
        headers = {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        proxies = None
        if self.proxy_url:
            proxies = {
                'http': self.proxy_url,
                'https': self.proxy_url,
            }

        params = {
            'q': query.query,
            'hl': 'en',
            'num': min(query.max_results, 20),
        }

        try:
            resp = requests.get(
                self.SCHOLAR_URL,
                params=params,
                headers=headers,
                proxies=proxies,
                timeout=30
            )
            resp.raise_for_status()

            # 检查 CAPTCHA
            if 'captcha' in resp.text.lower() or 'please show you\'re not a robot' in resp.text.lower():
                logger.warning("Google Scholar CAPTCHA detected")
                return ProviderResult(
                    papers=[],
                    source=self.name(),
                    error="CAPTCHA detected - need proxy or wait"
                )

            soup = BeautifulSoup(resp.text, 'html.parser')
            papers = self._parse_results(soup, query.max_results)

            return ProviderResult(papers=papers, source=self.name(), total=len(papers))

        except Exception as e:
            logger.error(f"Google Scholar search error: {e}")
            return ProviderResult(papers=[], source=self.name(), error=str(e))

    def _parse_results(self, soup: BeautifulSoup, max_results: int) -> list[Paper]:
        """解析搜索结果"""
        papers = []

        results = soup.find_all('div', class_='gs_ri')

        for item in results[:max_results]:
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)

        return papers

    def _parse_paper(self, item) -> Optional[Paper]:
        """解析单个论文"""
        try:
            # 标题
            title_elem = item.find('h3', class_='gs_rt')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True).replace('[PDF]', '').replace('[HTML]', '')

            # 链接
            link = title_elem.find('a', href=True)
            url = link['href'] if link else ''

            # 作者和来源
            info_elem = item.find('div', class_='gs_a')
            info_text = info_elem.get_text() if info_elem else ''

            # 解析作者 (第一个 - 之前)
            authors = []
            if info_text:
                authors = [a.strip() for a in info_text.split('-')[0].split(',') if a.strip()]

            # 年份
            year = None
            for word in info_text.split():
                if word.isdigit() and 1900 <= int(word) <= 2030:
                    year = int(word)
                    break

            # 摘要
            abstract_elem = item.find('div', class_='gs_rs')
            abstract = abstract_elem.get_text() if abstract_elem else ''

            return Paper(
                title=title,
                authors=authors,
                year=year,
                abstract=abstract[:500] if abstract else '',
                pdf_url='',  # Google Scholar 通常不直接提供 PDF URL
                source=self.name(),
            )

        except Exception as e:
            logger.debug(f"Google Scholar parse error: {e}")
            return None