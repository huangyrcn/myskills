"""数据源提供者模块"""

from .base import Paper, ProviderResult, SearchQuery, SearchType
from .semantic_scholar import SemanticScholarProvider
from .arxiv import ArxivProvider
from .openalex import OpenAlexProvider
from .openreview import OpenReviewProvider
from .crossref import CrossrefProvider
from .biorxiv import BiorxivProvider
from .medrxiv import MedrxivProvider
from .core import CoreProvider
from .mdpi import MdpiProvider
from .pubmed_central import PubmedCentralProvider
from .researchgate import ResearchGateProvider
from .sci_hub import SciHubProvider
from .ssrn import SsrnProvider
from .unpaywall import UnpaywallProvider
# 新增 provider
from .dblp import DblpProvider
from .europepmc import EuropePmcProvider
from .zenodo import ZenodoProvider
from .openaire import OpenaireProvider
from .doaj import DoajProvider
from .hal import HalProvider
from .iacr import IacrProvider
from .citeseerx import CiteseerxProvider
from .base_search import BaseSearchProvider
from .google_scholar import GoogleScholarProvider
from .repec import RepecProvider

__all__ = [
    "Paper",
    "ProviderResult",
    "SearchQuery",
    "SearchType",
    # 原有数据源
    "SemanticScholarProvider",
    "ArxivProvider",
    "OpenAlexProvider",
    "OpenReviewProvider",
    "CrossrefProvider",
    "BiorxivProvider",
    "MedrxivProvider",
    "CoreProvider",
    "MdpiProvider",
    "PubmedCentralProvider",
    "ResearchGateProvider",
    "SciHubProvider",
    "SsrnProvider",
    "UnpaywallProvider",
    # 新增数据源
    "DblpProvider",
    "EuropePmcProvider",
    "ZenodoProvider",
    "OpenaireProvider",
    "DoajProvider",
    "HalProvider",
    "IacrProvider",
    "CiteseerxProvider",
    "BaseSearchProvider",
    "GoogleScholarProvider",
    "RepecProvider",
]

# 所有可用的 providers (按优先级排序)
ALL_PROVIDERS = [
    CrossrefProvider,           # 90 - DOI 权威
    PubmedCentralProvider,      # 89 - 生物医学权威
    EuropePmcProvider,          # 88 - 生物医学，支持全文
    UnpaywallProvider,          # 87 - 开放获取
    CoreProvider,               # 86 - 开放获取聚合
    SsrnProvider,               # 85 - 社会科学预印本
    DblpProvider,               # 85 - CS 论文权威
    RepecProvider,              # 85 - 经济学独有
    SemanticScholarProvider,    # 80 - 学术搜索
    ArxivProvider,              # 80 - 预印本
    BiorxivProvider,            # 75 - 生物学预印本
    MedrxivProvider,            # 75 - 医学预印本
    MdpiProvider,               # 75 - 开放获取期刊
    OpenReviewProvider,         # 75 - ML 顶会
    ZenodoProvider,             # 78 - 通用科研仓库
    OpenaireProvider,           # 75 - 欧洲开放科学
    DoajProvider,               # 76 - 高质量开放获取
    HalProvider,                # 74 - 法国开放档案
    IacrProvider,               # 72 - 密码学预印本
    ResearchGateProvider,       # 70 - 学术社交网络
    OpenAlexProvider,           # 70 - 综合学术
    CiteseerxProvider,          # 68 - CS 文献
    BaseSearchProvider,         # 65 - 德国学术搜索
    GoogleScholarProvider,      # 50 - 谷歌学术 (反爬)
    SciHubProvider,             # 10 - 备选全文
]