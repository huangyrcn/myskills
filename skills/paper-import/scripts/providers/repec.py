"""
RePEc Provider

通过 IDEAS 前端 (ideas.repec.org) 搜索经济学论文。
RePEc (Research Papers in Economics) 是最大的开放经济学文献库。

优先级: 85 (经济学独有)
支持全文: 否 (元数据索引，PDF 在原机构)
"""

import json
import re
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


class RepecProvider(BaseProvider):
    """RePEc/IDEAS 经济学论文数据源

    覆盖范围:
    - 工作论文: NBER, IMF, World Bank, Fed, ECB
    - 期刊文章: AER, JPE, QJE, Econometrica
    - 书籍章节
    """

    SEARCH_URL = "https://ideas.repec.org/cgi-bin/htsearch2"
    TIMEOUT = 30

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    @classmethod
    def name(cls) -> str:
        return "repec"

    @classmethod
    def priority(cls) -> int:
        return 85

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        return False  # RePEc 不托管 PDF

    def _extract_year(self, text: str) -> int | None:
        """从文本中提取年份"""
        match = re.search(r'\b(19|20)\d{2}\b', text)
        if match:
            year = int(match.group())
            if 1900 <= year <= datetime.now().year:
                return year
        return None

    def _is_paper_url(self, url: str) -> bool:
        """检查是否为论文链接"""
        if not url:
            return False
        return any(f'/{t}/' in url for t in ['p', 'a', 'h', 'b']) and 'ideas.repec.org' in url

    def _extract_repec_handle(self, url: str) -> str:
        """从 URL 提取 RePEc handle"""
        match = re.search(r'ideas\.repec\.org/([pahbc])/([^/]+)/([^/]+)/([^/]+)\.html', url)
        if match:
            doc_type, publisher, series, paper_id = match.groups()
            return f"RePEc:{publisher}:{series}:{paper_id}"
        return f"repec_{hash(url)}"

    def _parse_paper(self, url: str, title: str, context: str) -> Paper:
        """解析论文数据"""
        year = self._extract_year(context) if context else None
        paper_id = self._extract_repec_handle(url)

        return Paper(
            title=title,
            authors=[],  # 搜索结果难以准确提取
            year=year,
            venue="RePEc",
            abstract=None,
            doi=None,
            pdf_url=None,  # RePEc 不直接提供 PDF
            source=self.name(),
        )

    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        if not HAS_BS4:
            return ProviderResult(
                papers=[],
                source=self.name(),
                error="beautifulsoup4 not installed. Run: pip install beautifulsoup4",
            )

        papers = []

        try:
            # 构建 POST 数据
            data = urllib.parse.urlencode({
                'q': query.query,
                'wf': '4BFF',  # Whole record
                's': 'R',       # Relevance sort
                'form': 'extended',
                'wm': 'wrd',
                'dt': 'range',
            }).encode()

            # 随机延迟避免被封
            time.sleep(random.uniform(0.5, 1.0))

            req = urllib.request.Request(
                self.SEARCH_URL,
                data=data,
                headers={
                    'User-Agent': random.choice(self.USER_AGENTS),
                    'Accept': 'text/html,application/xhtml+xml',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            )

            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                html = resp.read().decode('utf-8', errors='ignore')

            # 解析 HTML
            soup = BeautifulSoup(html, 'html.parser')

            seen_urls = set()
            for link in soup.find_all('a', href=True):
                if len(papers) >= query.max_results:
                    break

                href = link.get('href', '')
                if not href.startswith('http'):
                    href = f"https://ideas.repec.org{href}"

                if not self._is_paper_url(href):
                    continue

                if href in seen_urls:
                    continue
                seen_urls.add(href)

                title = link.get_text(strip=True)
                if not title:
                    continue

                # 获取上下文
                parent = link.find_parent()
                context = parent.get_text(separator=' ', strip=True) if parent else ""

                paper = self._parse_paper(href, title, context)
                papers.append(paper)

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