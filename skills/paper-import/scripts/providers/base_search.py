"""
BASE - 德国学术搜索引擎

API: OAI-PMH
支持: 全球开放获取资源
注意: 需要注册 IP 或有访问限制
"""

from .base import BaseProvider, Paper, ProviderResult, SearchQuery, SearchType
from typing import Optional
import requests
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class BaseSearchProvider(BaseProvider):
    """BASE (Bielefeld Academic Search Engine) 搜索"""

    BASE_URL = "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi"

    @classmethod
    def name(cls) -> str:
        return "base"

    @classmethod
    def priority(cls) -> int:
        return 65  # 大规模但访问受限

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        return [SearchType.AUTO, SearchType.TITLE, SearchType.KEYWORDS]

    def search(self, query: SearchQuery) -> ProviderResult:
        # OAI-PMH 参数
        params = {
            'verb': 'ListRecords',
            'metadataPrefix': 'oai_dc',
            'set': f'search:"{query.query}"',
        }

        headers = {
            'User-Agent': 'paper-search-mcp/1.0',
            'Accept': 'text/xml',
        }

        try:
            resp = requests.get(self.BASE_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()

            papers = self._parse_oaipmh_response(resp.text, query.max_results)

            return ProviderResult(papers=papers, source=self.name(), total=len(papers))

        except Exception as e:
            logger.error(f"BASE search error: {e}")
            return ProviderResult(papers=[], source=self.name(), error=str(e))

    def _parse_oaipmh_response(self, xml_text: str, max_results: int) -> list[Paper]:
        """解析 OAI-PMH XML 响应"""
        papers = []

        try:
            root = ET.fromstring(xml_text)

            # OAI-PMH namespace
            ns = {
                'oai': 'http://www.openarchives.org/OAI/2.0/',
                'dc': 'http://purl.org/dc/elements/1.1/',
            }

            records = root.findall('.//oai:record', ns)

            for record in records[:max_results]:
                metadata = record.find('.//oai:metadata', ns)
                if metadata is None:
                    continue

                dc = metadata.find('.//dc:dc', ns)
                if dc is None:
                    continue

                title = self._get_dc_element(dc, 'title', ns)
                creators = self._get_dc_elements(dc, 'creator', ns)
                date = self._get_dc_element(dc, 'date', ns)
                abstract = self._get_dc_element(dc, 'description', ns)
                identifier = self._get_dc_element(dc, 'identifier', ns)

                paper = Paper(
                    title=title,
                    authors=creators,
                    year=self._parse_year(date),
                    abstract=abstract[:500] if abstract else '',
                    pdf_url=identifier if identifier and 'pdf' in identifier.lower() else None,
                    source=self.name(),
                )
                papers.append(paper)

        except ET.ParseError as e:
            logger.error(f"BASE XML parse error: {e}")

        return papers

    def _get_dc_element(self, dc, name: str, ns: dict) -> str:
        """获取单个 DC 元素"""
        elem = dc.find(f'dc:{name}', ns)
        return elem.text if elem is not None and elem.text else ''

    def _get_dc_elements(self, dc, name: str, ns: dict) -> list[str]:
        """获取多个 DC 元素"""
        return [e.text for e in dc.findall(f'dc:{name}', ns) if e.text]

    def _parse_year(self, date_str: str) -> Optional[int]:
        try:
            return int(date_str[:4]) if date_str else None
        except (ValueError, IndexError):
            return None