#!/usr/bin/env python3
"""
query_apis.py - 并行查询学术 APIs 并保存 metadata.yaml

用法:
    python3 query_apis.py "查询词" [--output /tmp/papers] [--sources s2,openalex,crossref,arxiv,openreview]

输出:
    /tmp/candidates.json - 所有候选结果
    ${OUTPUT_DIR}/{title_slug}/metadata.yaml - 最佳匹配的元数据
"""

import argparse
import asyncio
import html
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

# 添加当前目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers import (
    Paper, ProviderResult, SearchQuery, SearchType,
    SemanticScholarProvider, ArxivProvider, OpenAlexProvider,
    OpenReviewProvider, CrossrefProvider,
    BiorxivProvider, MedrxivProvider, CoreProvider, MdpiProvider,
    PubmedCentralProvider, ResearchGateProvider,
    SciHubProvider, SsrnProvider, UnpaywallProvider,
    # 新增 providers
    DblpProvider, EuropePmcProvider, ZenodoProvider,
    OpenaireProvider, DoajProvider, HalProvider,
    IacrProvider, CiteseerxProvider, BaseSearchProvider,
    GoogleScholarProvider, RepecProvider,
)
from metadata_utils import find_existing_import, title_slug, write_metadata


# === 三阶段源策略 ===

DEFAULT_TITLE_SOURCES = [
    "arxiv",
    "s2",
    "openalex",
    "crossref",
    "dblp",
]

DEFAULT_CONTEXT_SOURCES = [
    "openreview",
    "biorxiv",
    "pubmed_central",
    "europepmc",
    "zenodo",
    "openaire",
    "doaj",
    "hal",
    "repec",
    "core",
]

SOURCE_NAME_ALIASES = {
    "s2": "semantic_scholar",
}

TITLE_PROVIDER_NAMES = {
    SOURCE_NAME_ALIASES.get(source, source)
    for source in DEFAULT_TITLE_SOURCES
}

TITLE_SOURCE_PRIORITY = {
    "arxiv": 0,
    "semantic_scholar": 1,
    "openalex": 2,
    "crossref": 3,
    "dblp": 4,
}

ARXIV_ID_RE = re.compile(
    r"(?:10\.48550/arxiv\.|arxiv\.org/(?:abs|pdf|e-print)/)"
    r"(?P<id>(?:[a-z\-]+(?:\.[a-z\-]+)?/\d{7}|\d{4}\.\d{4,5}))(?:v\d+)?",
    re.IGNORECASE,
)

TRUSTED_ARXIV_SOURCES = {
    "arxiv": 6,
    "semantic_scholar": 5,
    "openalex": 5,
    "dblp": 3,
    "crossref": 2,
    "openreview": 2,
}

TRUSTED_DOI_SOURCES = {
    "openalex": 5,
    "semantic_scholar": 4,
    "crossref": 3,
    "dblp": 2,
    "openreview": 2,
    "arxiv": 1,
}


# === 输入类型自动检测 ===

def detect_query_type(query: str) -> tuple[SearchType, str]:
    """
    检测查询类型

    只接受论文标题作为输入。
    """
    query = query.strip()

    # 只支持标题搜索
    return SearchType.TITLE, query


# === 临时目录名生成 ===

def generate_temp_identifier(paper: dict) -> str:
    """
    生成临时目录名（标题 slug）

    格式: 标题 slug，如 attention_is_all_you_need
    后续由 LLM 抽取 method 后重命名为 venueyear-lastname-method
    """
    return title_slug(paper.get("title", "") or "")


# === metadata.yaml 生成 ===

def save_metadata_yaml(merged: dict, output_dir: Path) -> Path:
    """
    保存 metadata.yaml

    返回: 保存路径
    """
    if not merged:
        return None

    best = merged["best_match"]
    ids = merged["ids"]
    urls = merged["urls"]
    pdf_urls = merged.get("pdf_urls", [])

    temp_identifier = generate_temp_identifier(best)
    paper_dir = output_dir / temp_identifier
    paper_dir.mkdir(parents=True, exist_ok=True)

    identifiers = {
        "doi": ids.get("doi"),
        "doi_source": "api_verified" if ids.get("doi") else None,
        "doi_reason": (
            None
            if ids.get("doi")
            else "arxiv_preprint" if ids.get("arxiv_id") else "not_found"
        ),
        "arxiv": ids.get("arxiv_id"),
        "semantic_scholar": ids.get("s2_id"),
        "openalex": ids.get("openalex_id"),
        "openreview": ids.get("openreview_id"),
        "pmc": ids.get("pmcid"),
        "core": ids.get("core_id"),
    }

    metadata = {
        "created_at": datetime.now().isoformat(),
        "title": best.get("title", ""),
        "title_slug": temp_identifier,
        "authors": best.get("authors", []),
        "year": best.get("year"),
        "venue": best.get("venue", ""),
        "confirmed_venue": None,
        "method_name": None,
        "foldername": None,
        "identifiers": {k: v for k, v in identifiers.items() if v is not None},
        "venue_candidates": merged.get("venue_candidates", []),
        "urls": urls,
        "abstract": best.get("abstract"),
        "pdf_urls": pdf_urls,
        "latex_source": (
            {
                "available": True,
                "url": f"https://arxiv.org/e-print/{ids['arxiv_id']}",
            }
            if ids.get("arxiv_id")
            else {
                "available": False,
                "note": "only_arxiv_has_latex_source",
            }
        ),
        "assets": {},
        "repo_search": {
            "selected": None,
            "candidates": [],
        },
        "resolution": merged.get("resolution", {}),
    }

    yaml_path = paper_dir / "metadata.yaml"
    write_metadata(yaml_path, metadata)
    return yaml_path


# === 工具函数 ===

def similarity(a: str, b: str) -> float:
    """计算字符串相似度"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_title(text: str | None) -> str:
    """规范化标题，用于精确比较。"""
    if not text:
        return ""
    text = html.unescape(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_author_tokens(authors: list[str] | None) -> set[str]:
    """提取作者姓氏 token，用于作者重叠判断。"""
    tokens = set()
    for author in authors or []:
        parts = re.findall(r"[a-z0-9]+", html.unescape(author).lower())
        if parts:
            tokens.add(parts[-1])
    return tokens


def author_overlap_ratio(left: list[str] | None, right: list[str] | None) -> float:
    """估算作者重叠比例。"""
    left_tokens = normalize_author_tokens(left)
    right_tokens = normalize_author_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))


def normalize_doi(doi: str) -> str:
    """规范化 DOI，用于去重"""
    if not doi:
        return None
    return doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "")


def extract_arxiv_id(text: str | None) -> str | None:
    """从 DOI / URL / 任意文本中提取 arXiv ID。"""
    if not text:
        return None
    match = ARXIV_ID_RE.search(text)
    if not match:
        return None
    return match.group("id")


def extract_arxiv_id_from_paper(paper: Paper) -> str | None:
    """从 paper 的多个字段中提取 arXiv ID。"""
    for value in [
        paper.arxiv_id,
        paper.doi,
        paper.pdf_url,
        getattr(paper, "openalex_id", None),
    ]:
        arxiv_id = extract_arxiv_id(value)
        if arxiv_id:
            return arxiv_id
    return None


def shares_identifier(left: Paper, right: Paper) -> bool:
    """判断两篇论文是否共享明确标识符。"""
    if normalize_doi(left.doi) and normalize_doi(left.doi) == normalize_doi(right.doi):
        return True
    if extract_arxiv_id_from_paper(left) and extract_arxiv_id_from_paper(left) == extract_arxiv_id_from_paper(right):
        return True

    for attr in ["s2_id", "openalex_id", "openreview_id", "pmcid", "core_id", "dblp_id"]:
        if getattr(left, attr, None) and getattr(left, attr, None) == getattr(right, attr, None):
            return True
    return False


def unique_in_order(values: list[str]) -> list[str]:
    """保持顺序去重。"""
    seen = set()
    ordered = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def deduplicate_by_doi(papers: list[Paper]) -> list[Paper]:
    """按 DOI 去重"""
    seen = set()
    unique, no_doi = [], []

    for paper in papers:
        doi = normalize_doi(paper.doi)
        if doi:
            if doi not in seen:
                seen.add(doi)
                unique.append(paper)
        else:
            no_doi.append(paper)

    return unique + no_doi


def rank_papers(papers: list[Paper], reference_title: str) -> list[Paper]:
    """按参考标题为论文打分并排序。"""
    for paper in papers:
        paper._similarity = similarity(reference_title, paper.title or "")

    current_year = datetime.now().year + 1

    def sort_key(paper: Paper):
        has_arxiv = 0 if paper.arxiv_id else 1
        sim = -paper._similarity
        source_rank = TITLE_SOURCE_PRIORITY.get(paper.source, 99)
        year_ok = 0 if paper.year and 1990 <= paper.year <= current_year else 1
        has_venue = 0 if paper.venue else 1
        has_doi = 0 if paper.doi else 1
        return (has_arxiv, sim, source_rank, year_ok, has_venue, has_doi)

    papers.sort(key=sort_key)
    return papers


def select_best_paper(papers: list[Paper], query: str) -> Paper | None:
    """从一批候选中选出 canonical paper。"""
    if not papers:
        return None
    ranked = rank_papers(list(papers), query)
    return ranked[0]


def paper_is_related_to_canonical(candidate: Paper, canonical: Paper, query: str) -> bool:
    """判断标题候选是否可以用于 identifier / venue / pdf 补全。"""
    shared_id = shares_identifier(candidate, canonical)
    if candidate is canonical or shared_id:
        return True

    title_exact = normalize_title(candidate.title) == normalize_title(canonical.title)
    title_sim = similarity(canonical.title or query, candidate.title or "")
    author_overlap = author_overlap_ratio(canonical.authors, candidate.authors)

    if canonical.authors and candidate.authors and author_overlap == 0:
        return False

    if canonical.year and candidate.year and abs(canonical.year - candidate.year) > 1 and author_overlap == 0:
        return False

    if title_exact:
        return True

    return title_sim >= 0.96 and (author_overlap > 0 or not canonical.authors or not candidate.authors)


def choose_best_arxiv_id(papers: list[Paper], canonical: Paper) -> tuple[str | None, list[dict]]:
    """从多源候选中选择最可信的 arXiv ID。"""
    scored = {}
    for paper in papers:
        arxiv_id = extract_arxiv_id_from_paper(paper)
        if not arxiv_id:
            continue

        score = TRUSTED_ARXIV_SOURCES.get(paper.source, 1)
        if normalize_title(paper.title) == normalize_title(canonical.title):
            score += 2
        if author_overlap_ratio(canonical.authors, paper.authors) > 0:
            score += 2
        if canonical.year and paper.year and abs(canonical.year - paper.year) <= 1:
            score += 1

        entry = scored.setdefault(arxiv_id, {"score": -999, "sources": set()})
        entry["score"] = max(entry["score"], score)
        entry["sources"].add(paper.source)

    if not scored:
        return None, []

    ranked = sorted(
        (
            {
                "value": arxiv_id,
                "score": data["score"],
                "sources": sorted(data["sources"]),
            }
            for arxiv_id, data in scored.items()
        ),
        key=lambda item: (-item["score"], item["value"]),
    )
    return ranked[0]["value"], ranked


def choose_best_doi(papers: list[Paper], canonical: Paper, arxiv_id: str | None) -> tuple[str | None, list[dict]]:
    """从多源候选中选择最可信的 DOI。"""
    scored = {}
    for paper in papers:
        doi = normalize_doi(paper.doi)
        if not doi:
            continue

        score = TRUSTED_DOI_SOURCES.get(paper.source, 1)
        if normalize_title(paper.title) == normalize_title(canonical.title):
            score += 2

        overlap = author_overlap_ratio(canonical.authors, paper.authors)
        if overlap > 0:
            score += 2
        elif canonical.authors and paper.authors:
            score -= 3

        if canonical.year and paper.year:
            if abs(canonical.year - paper.year) <= 1:
                score += 1
            else:
                score -= 3

        doi_arxiv_id = extract_arxiv_id(doi)
        if arxiv_id and doi_arxiv_id and doi_arxiv_id == arxiv_id:
            score += 6

        entry = scored.setdefault(doi, {"score": -999, "sources": set()})
        entry["score"] = max(entry["score"], score)
        entry["sources"].add(paper.source)

    if not scored:
        return None, []

    ranked = sorted(
        (
            {
                "value": doi,
                "score": data["score"],
                "sources": sorted(data["sources"]),
            }
            for doi, data in scored.items()
        ),
        key=lambda item: (-item["score"], item["value"]),
    )

    if ranked[0]["score"] < 5:
        return None, ranked

    return ranked[0]["value"], ranked


def exact_lookup(provider_class, query: SearchQuery) -> tuple[ProviderResult, Paper | None]:
    """执行精确回查，返回 ProviderResult 和首个 paper。"""
    result = query_provider(provider_class, query)
    return result, (result.papers[0] if result.papers else None)


def build_best_match(best: Paper, related_papers: list[Paper]) -> dict:
    """用相关候选补全 canonical paper 缺失字段。"""
    best_match = {
        "title": best.title,
        "authors": best.authors,
        "year": best.year,
        "venue": best.venue,
        "abstract": best.abstract,
    }

    for paper in related_papers:
        if not best_match["authors"] and paper.authors:
            best_match["authors"] = paper.authors
        if not best_match["year"] and paper.year:
            best_match["year"] = paper.year
        if not best_match["venue"] and paper.venue:
            best_match["venue"] = paper.venue
        if not best_match["abstract"] and paper.abstract:
            best_match["abstract"] = paper.abstract

    return best_match


def merge_papers(title_papers: list[Paper], context_papers: list[Paper], query: str) -> dict:
    """
    三阶段合并论文信息。

    1. 标题阶段决定 canonical paper
    2. identifier 阶段选择 arXiv ID / DOI 并做精确回查
    3. assets 阶段由下游 import_paper.py 消费这些 identifiers
    """
    best = select_best_paper(title_papers, query)
    if best is None:
        best = select_best_paper(context_papers, query)

    if best is None:
        return None

    canonical_title = best.title or query
    stage1_papers = title_papers + context_papers
    related_papers = [paper for paper in stage1_papers if paper_is_related_to_canonical(paper, best, query)]

    related_papers.sort(
        key=lambda paper: (
            0 if paper.source in TITLE_PROVIDER_NAMES else 1,
            -similarity(canonical_title, paper.title or ""),
            0 if paper.doi else 1,
            0 if paper.venue else 1,
        )
    )

    selected_arxiv_id, arxiv_candidates = choose_best_arxiv_id(related_papers, best)
    selected_doi, doi_candidates = choose_best_doi(related_papers, best, selected_arxiv_id)

    exact_papers = []
    exact_lookup_sources = []

    if selected_arxiv_id:
        _, arxiv_paper = exact_lookup(
            ArxivProvider,
            SearchQuery(query=selected_arxiv_id, search_type=SearchType.ARXIV, max_results=1),
        )
        if arxiv_paper:
            exact_papers.append(arxiv_paper)
            exact_lookup_sources.append("arxiv:id_list")

    if selected_doi:
        _, openalex_paper = exact_lookup(
            OpenAlexProvider,
            SearchQuery(query=selected_doi, search_type=SearchType.DOI, max_results=1),
        )
        if openalex_paper and paper_is_related_to_canonical(openalex_paper, best, query):
            exact_papers.append(openalex_paper)
            exact_lookup_sources.append("openalex:doi")

        _, crossref_paper = exact_lookup(
            CrossrefProvider,
            SearchQuery(query=selected_doi, search_type=SearchType.DOI, max_results=1),
        )
        if crossref_paper and paper_is_related_to_canonical(crossref_paper, best, query):
            exact_papers.append(crossref_paper)
            exact_lookup_sources.append("crossref:doi")

    all_related_papers = related_papers + [paper for paper in exact_papers if paper_is_related_to_canonical(paper, best, query)]
    best_match = build_best_match(best, all_related_papers)

    # 收集所有 ID
    ids = {
        "doi": selected_doi,
        "arxiv_id": selected_arxiv_id,
        "s2_id": best.s2_id,
        "openalex_id": best.openalex_id,
        "openreview_id": best.openreview_id,
        "pmcid": best.pmcid,
        "core_id": best.core_id,
    }

    # PDF URL 可靠性等级
    PDF_RELIABILITY = {
        "arxiv": "high",      # arXiv PDF 直接可用
        "openreview": "high", # OpenReview PDF 直接可用
        "pmc": "high",        # PubMed Central PDF 直接可用
        "biorxiv": "high",    # bioRxiv PDF 直接可用
        "ssrn": "medium",     # SSRN 通常可用
        "core": "medium",     # CORE 可能可用
        "s2": "low",          # Semantic Scholar 可能重定向
        "openalex": "low",    # OpenAlex 可能重定向
        "doi": "low",         # DOI 链接可能需要付费
        "unpaywall": "medium",# Unpaywall OA 版本
    }

    # 收集所有来源的 PDF URL
    pdf_urls = {}  # {source: url}
    for paper in all_related_papers:
        if paper.pdf_url and paper.source not in pdf_urls:
            pdf_urls[paper.source] = paper.pdf_url

    # 收集所有 venue 候选 (来自不同 API)
    venue_candidates = []
    seen_venues = set()
    for paper in all_related_papers:
        if paper.venue:
            v_lower = paper.venue.lower().strip()
            if v_lower not in seen_venues:
                seen_venues.add(v_lower)
                venue_candidates.append({
                    "source": paper.source,
                    "venue": paper.venue,
                })

    # 从其他匹配的论文补充缺失的 ID
    for paper in all_related_papers:
        if not ids["s2_id"] and paper.s2_id:
            ids["s2_id"] = paper.s2_id
        if not ids["openalex_id"] and paper.openalex_id:
            ids["openalex_id"] = paper.openalex_id
        if not ids["openreview_id"] and paper.openreview_id:
            ids["openreview_id"] = paper.openreview_id
        if not ids["pmcid"] and paper.pmcid:
            ids["pmcid"] = paper.pmcid
        if not ids["core_id"] and paper.core_id:
            ids["core_id"] = paper.core_id

    # 构建 URL
    urls = {}
    if ids["doi"]:
        urls["doi"] = f"https://doi.org/{ids['doi']}"
    if ids["arxiv_id"]:
        urls["arxiv_abs"] = f"https://arxiv.org/abs/{ids['arxiv_id']}"
        # arXiv PDF URL (高优先级)
        if "arxiv" not in pdf_urls:
            pdf_urls["arxiv"] = f"https://arxiv.org/pdf/{ids['arxiv_id']}"
    if ids["s2_id"]:
        urls["s2"] = f"https://semanticscholar.org/paper/{ids['s2_id']}"
    if ids["openalex_id"]:
        urls["openalex"] = f"https://openalex.org/{ids['openalex_id']}"
    if ids["openreview_id"]:
        urls["openreview"] = f"https://openreview.net/forum?id={ids['openreview_id']}"
        # OpenReview PDF URL
        if "openreview" not in pdf_urls:
            pdf_urls["openreview"] = f"https://openreview.net/pdf?id={ids['openreview_id']}"
    if ids["pmcid"]:
        urls["pmc"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{ids['pmcid']}"
        # PMC PDF URL
        if "pubmed_central" not in pdf_urls:
            pdf_urls["pubmed_central"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{ids['pmcid']}/pdf/"
    if ids["core_id"]:
        urls["core"] = f"https://api.core.ac.uk/repository/{ids['core_id']}"

    # 构建有序的 PDF URL 列表 (按可靠性排序)
    pdf_url_list = []
    for source in ["arxiv", "openreview", "pmc", "pubmed_central", "biorxiv", "ssrn", "unpaywall", "core", "s2", "openalex"]:
        if source in pdf_urls:
            pdf_url_list.append({
                "source": source,
                "url": pdf_urls[source],
                "reliability": PDF_RELIABILITY.get(source, "unknown"),
            })

    # 清理临时属性
    for paper in stage1_papers + exact_papers:
        if hasattr(paper, "_similarity"):
            delattr(paper, "_similarity")
        if hasattr(paper, "_query_similarity"):
            delattr(paper, "_query_similarity")

    return {
        "best_match": best_match,
        "ids": {k: v for k, v in ids.items() if v},
        "urls": urls,
        "pdf_urls": pdf_url_list,
        "venue_candidates": venue_candidates,
        "resolution": {
            "title_stage": {
                "canonical_source": best.source,
                "canonical_title": canonical_title,
                "matched_sources": unique_in_order([paper.source for paper in related_papers]),
            },
            "identifier_stage": {
                "arxiv_id": ids.get("arxiv_id"),
                "doi": ids.get("doi"),
                "arxiv_candidates": arxiv_candidates,
                "doi_candidates": doi_candidates,
                "exact_lookup_sources": unique_in_order(exact_lookup_sources),
            },
            "asset_stage": {
                "preferred_pdf_source": "arxiv" if ids.get("arxiv_id") else (pdf_url_list[0]["source"] if pdf_url_list else None),
                "preferred_latex_source": "arxiv" if ids.get("arxiv_id") else None,
            },
        },
        "selection": {
            "canonical_source": best.source,
            "canonical_title": canonical_title,
            "matched_sources": unique_in_order([paper.source for paper in related_papers]),
        },
    }


def split_source_layers(sources: list[str] | None, source_map: dict[str, type]) -> tuple[list[str], list[str]]:
    """将源拆成标题判定层和上下文补全层。"""
    if sources is None:
        return list(DEFAULT_TITLE_SOURCES), list(DEFAULT_CONTEXT_SOURCES)

    ordered_sources = []
    seen = set()
    for source in sources:
        if source in source_map and source not in seen:
            seen.add(source)
            ordered_sources.append(source)

    primary = [source for source in ordered_sources if source in DEFAULT_TITLE_SOURCES]
    secondary = [source for source in ordered_sources if source not in primary]

    # 如果用户显式只给了第二层源，就把它们当第一层处理。
    if not primary and secondary:
        return secondary, []

    return primary, secondary


async def query_sources(
    search_query: SearchQuery,
    sources: list[str],
    source_map: dict[str, type],
) -> dict[str, ProviderResult]:
    """并行查询一批 sources。"""
    if not sources:
        return {}

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=max(1, len(sources))) as ex:
        futures = {
            source: loop.run_in_executor(ex, query_provider, source_map[source], search_query)
            for source in sources
        }
        results = {}
        for source, future in futures.items():
            results[source] = await future
    return results


# === 主函数 ===

def query_provider(provider_class, query: SearchQuery) -> ProviderResult:
    """查询单个 provider（跳过不支持当前 search_type 的 provider）"""
    if query.search_type not in provider_class.supported_search_types():
        return ProviderResult(papers=[], source=provider_class.name())
    provider = provider_class()
    return provider.search(query)


async def query_all(query: str, limit: int = 10, sources: list = None, top_n: int = 10):
    """按三阶段策略查询标题、identifiers 和资产线索。"""
    source_map = {
        "s2": SemanticScholarProvider,
        "openalex": OpenAlexProvider,
        "arxiv": ArxivProvider,
        "openreview": OpenReviewProvider,
        "crossref": CrossrefProvider,
        "biorxiv": BiorxivProvider,
        "medrxiv": MedrxivProvider,
        "core": CoreProvider,
        "mdpi": MdpiProvider,
        "pubmed_central": PubmedCentralProvider,
        "researchgate": ResearchGateProvider,
        "sci_hub": SciHubProvider,
        "ssrn": SsrnProvider,
        "unpaywall": UnpaywallProvider,
        # 新增 sources
        "dblp": DblpProvider,
        "europepmc": EuropePmcProvider,
        "zenodo": ZenodoProvider,
        "openaire": OpenaireProvider,
        "doaj": DoajProvider,
        "hal": HalProvider,
        "iacr": IacrProvider,
        "citeseerx": CiteseerxProvider,
        "base": BaseSearchProvider,
        "google_scholar": GoogleScholarProvider,
        "repec": RepecProvider,
    }

    # 自动检测查询类型
    detected_type, normalized_query = detect_query_type(query)
    search_query = SearchQuery(
        query=normalized_query,
        search_type=detected_type,
        max_results=limit
    )

    title_sources, context_sources = split_source_layers(sources, source_map)

    title_results = await query_sources(search_query, title_sources, source_map)
    context_results = await query_sources(search_query, context_sources, source_map)

    title_papers = []
    title_source_counts = {}
    for source in title_sources:
        result = title_results.get(source)
        if result is None:
            continue
        title_source_counts[source] = len(result.papers)
        title_papers.extend(result.papers)

    context_papers = []
    context_source_counts = {}
    for source in context_sources:
        result = context_results.get(source)
        if result is None:
            continue
        context_source_counts[source] = len(result.papers)
        context_papers.extend(result.papers)

    # Stage 1: title -> canonical paper
    # Stage 2: identifiers -> exact lookups
    merged = merge_papers(
        deduplicate_by_doi(title_papers),
        deduplicate_by_doi(context_papers),
        query,
    )

    # 候选列表仍然展示标题层和上下文层，但标题层优先
    all_papers = title_papers + context_papers
    deduped = deduplicate_by_doi(all_papers)

    # 计算相似度并排序，标题判定层优先展示
    title_provider_names = {SOURCE_NAME_ALIASES.get(source, source) for source in title_sources}
    for p in deduped:
        p._similarity = similarity(query, p.title or "")

    deduped.sort(
        key=lambda paper: (
            0 if paper.source in title_provider_names else 1,
            -paper._similarity,
            0 if paper.doi else 1,
            0 if paper.venue else 1,
        )
    )

    # 取 top N
    top_papers = deduped[:top_n]

    # 清理临时属性
    for p in top_papers:
        if hasattr(p, "_similarity"):
            delattr(p, "_similarity")

    return {
        "query": query,
        "total": len(deduped),
        "returned": len(top_papers),
        "sources": {**title_source_counts, **context_source_counts},
        "source_layers": {
            "title": title_sources,
            "context": context_sources,
        },
        "merged": merged,
        "candidates": [p.to_dict() for p in top_papers],
    }


def main():
    parser = argparse.ArgumentParser(description="查询学术 APIs 并保存 metadata.yaml")
    parser.add_argument("query", help="查询词")
    parser.add_argument("--limit", "-n", type=int, default=10, help="每源最大结果数")
    parser.add_argument("--top", "-t", type=int, default=10, help="返回的候选数量")
    parser.add_argument("--sources", "-s", default="",
                       help="数据源，逗号分隔 (默认: 标题判定 arxiv,s2,openalex,crossref,dblp；上下文补全 openreview,biorxiv,pubmed_central,europepmc,zenodo,openaire,doaj,hal,repec,core)")
    parser.add_argument("--output", "-o",
                       default=str(Path.home() / "papers"),
                       help="输出目录 (默认: ~/papers/)")
    parser.add_argument("--force", "-f", action="store_true",
                       help="强制重新下载，即使已存在")

    args = parser.parse_args()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()] or None
    output_dir = Path(args.output)

    print(f"Querying: {args.query}")
    if sources:
        print(f"Sources: {sources}")
    else:
        print(f"Title sources: {', '.join(DEFAULT_TITLE_SOURCES)}")
        print(f"Context sources: {', '.join(DEFAULT_CONTEXT_SOURCES)}")
    print(f"Output: {output_dir}")

    result = asyncio.run(query_all(args.query, args.limit, sources, args.top))

    # 保存 candidates.json
    with open("/tmp/candidates.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Found {result['total']} (returning top {result['returned']})")
    for layer in ["title", "context"]:
        layer_sources = result["source_layers"][layer]
        if not layer_sources:
            continue
        print(f"  {layer}:")
        for src in layer_sources:
            print(f"    {src}: {result['sources'].get(src, 0)}")

    # 保存 metadata.yaml
    if result.get("merged"):
        m = result["merged"]
        print(f"\nBest match: {m['best_match']['title']}")
        print(f"Canonical source: {m['resolution']['title_stage']['canonical_source']}")
        if m["resolution"]["identifier_stage"]["exact_lookup_sources"]:
            print(
                "Identifier exact lookups: "
                + ", ".join(m["resolution"]["identifier_stage"]["exact_lookup_sources"])
            )

        temp_identifier = generate_temp_identifier(m["best_match"])
        print(f"Temp identifier: {temp_identifier} (symlink created by finalize_metadata.py)")

        existing_dir = find_existing_import(
            output_dir,
            title=m["best_match"].get("title", ""),
            doi=m["ids"].get("doi"),
        )

        if existing_dir and not args.force:
            metadata_path = existing_dir / "metadata.yaml"
            if metadata_path.exists():
                try:
                    from metadata_utils import load_metadata

                    metadata = load_metadata(metadata_path)
                except Exception:
                    metadata = {}
                assets = metadata.get("assets", {}) or {}
                if assets.get("pdf"):
                    print(f"\n✓ Already imported: {existing_dir}")
                    print("  Use --force to re-download")
                    return

        # 如果 force 且已存在，删除旧目录
        if args.force and existing_dir:
            import shutil
            shutil.rmtree(existing_dir)

        # 保存 metadata.yaml
        yaml_path = save_metadata_yaml(result["merged"], output_dir)
        if yaml_path:
            print(f"✓ Saved: {yaml_path}")
        else:
            print("✗ Failed to save metadata.yaml")


if __name__ == "__main__":
    main()
