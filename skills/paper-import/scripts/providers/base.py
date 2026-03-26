"""
数据源提供者基类和数据类型

参考 Rust 版本的设计，为每个 provider 提供统一的接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class SearchType(Enum):
    """搜索类型"""
    AUTO = "auto"
    DOI = "doi"
    ARXIV = "arxiv"
    TITLE = "title"
    AUTHOR = "author"
    KEYWORDS = "keywords"


@dataclass
class SearchQuery:
    """搜索查询"""
    query: str
    search_type: SearchType = SearchType.AUTO
    max_results: int = 10
    offset: int = 0


@dataclass
class Paper:
    """论文元数据"""
    # 基本信息
    title: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None

    # 标识符
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    s2_id: Optional[str] = None
    openalex_id: Optional[str] = None
    openreview_id: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None  # PubMed Central ID
    core_id: Optional[str] = None  # CORE ID
    # 新增标识符
    dblp_id: Optional[str] = None
    zenodo_id: Optional[str] = None
    hal_id: Optional[str] = None
    openaire_id: Optional[str] = None
    citeseerx_id: Optional[str] = None

    # 链接
    pdf_url: Optional[str] = None

    # 来源
    source: str = "unknown"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "abstract": self.abstract,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "s2_id": self.s2_id,
            "openalex_id": self.openalex_id,
            "openreview_id": self.openreview_id,
            "pmid": self.pmid,
            "pmcid": self.pmcid,
            "core_id": self.core_id,
            "dblp_id": self.dblp_id,
            "zenodo_id": self.zenodo_id,
            "hal_id": self.hal_id,
            "openaire_id": self.openaire_id,
            "citeseerx_id": self.citeseerx_id,
            "pdf_url": self.pdf_url,
            "source": self.source,
        }


@dataclass
class ProviderResult:
    """Provider 查询结果"""
    papers: list[Paper]
    source: str
    total: Optional[int] = None
    search_time_ms: float = 0
    has_more: bool = False
    error: Optional[str] = None


class BaseProvider(ABC):
    """数据源提供者基类"""

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Provider 名称"""
        pass

    @classmethod
    def priority(cls) -> int:
        """优先级 (0-255, 越高越优先)"""
        return 50

    @classmethod
    def supported_search_types(cls) -> list[SearchType]:
        """支持的搜索类型"""
        return [SearchType.AUTO, SearchType.TITLE, SearchType.KEYWORDS]

    @classmethod
    def supports_full_text(cls) -> bool:
        """是否支持获取全文 PDF"""
        return False

    @abstractmethod
    def search(self, query: SearchQuery) -> ProviderResult:
        """执行搜索"""
        pass

    def get_by_doi(self, doi: str) -> Optional[Paper]:
        """通过 DOI 获取论文"""
        result = self.search(SearchQuery(query=doi, search_type=SearchType.DOI, max_results=1))
        return result.papers[0] if result.papers else None

    def health_check(self) -> bool:
        """健康检查"""
        try:
            result = self.search(SearchQuery(query="test", max_results=1))
            return result.error is None
        except Exception:
            return False


def measure_time(func):
    """装饰器：测量执行时间"""
    def wrapper(self, query: SearchQuery) -> ProviderResult:
        start = time.time()
        try:
            result = func(self, query)
            result.search_time_ms = (time.time() - start) * 1000
            return result
        except Exception as e:
            return ProviderResult(
                papers=[],
                source=self.name(),
                search_time_ms=(time.time() - start) * 1000,
                error=str(e),
            )
    return wrapper