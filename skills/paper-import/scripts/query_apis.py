#!/usr/bin/env python3
"""
query_apis.py - 并行查询学术 APIs 并保存 metadata.yaml

用法:
    python3 query_apis.py "查询词" [--output /tmp/papers] [--sources s2,openalex,crossref,arxiv,openreview]

输出:
    /tmp/candidates.json - 所有候选结果
    ${OUTPUT_DIR}/${citation_key}/metadata.yaml - 最佳匹配的元数据
"""

import argparse
import asyncio
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


# === 输入类型自动检测 ===

def detect_query_type(query: str) -> tuple[SearchType, str]:
    """
    检测查询类型

    只接受论文标题作为输入。
    """
    query = query.strip()

    # 只支持标题搜索
    return SearchType.TITLE, query


# === Citation Key 生成 ===

def generate_citation_key(paper: dict) -> str:
    """
    生成 citation key (BibTeX 风格)

    格式: 第一作者姓 + 年份 + 标题首词
    例如: du2023protodiff
    """
    # 提取第一作者姓
    authors = paper.get("authors", [])
    if authors:
        first_author = authors[0]
        # 取最后一个词作为姓 (如 "Yingjun Du" -> "du")
        last_name = first_author.split()[-1].lower()
        # 移除非字母字符
        last_name = re.sub(r"[^a-z]", "", last_name)
    else:
        last_name = "unknown"

    # 年份
    year = paper.get("year", "")
    year_str = str(year) if year else "nodate"

    # 标题首词 (跳过冠词等)
    title = paper.get("title", "") or ""
    skip_words = {"a", "an", "the", "on", "in", "for", "of", "and", "to", "with"}
    title_words = re.findall(r"[a-zA-Z]+", title)
    first_word = ""
    for word in title_words:
        if word.lower() not in skip_words:
            first_word = word.lower()
            break
    if not first_word and title_words:
        first_word = title_words[0].lower()

    # 组合
    key = f"{last_name}{year_str}"
    if first_word:
        key += first_word

    # 清理并限制长度
    key = re.sub(r"[^a-z0-9]", "", key)
    return key[:50] if len(key) > 50 else key


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

    # 生成 citation key
    citation_key = generate_citation_key(best)

    # 创建目录
    paper_dir = output_dir / citation_key
    paper_dir.mkdir(parents=True, exist_ok=True)

    # 构建 YAML 内容
    yaml_lines = [
        "# 论文元数据",
        f"# 生成时间: {datetime.now().isoformat()}",
        "",
        "# 基本信息",
        f'title: "{best.get("title", "")}"',
        "authors:",
    ]
    for author in best.get("authors", []):
        yaml_lines.append(f'  - "{author}"')

    yaml_lines.extend([
        f'year: {best.get("year", "")}',
        f'venue: "{best.get("venue", "")}"',
        "",
        "# 标识符",
        "identifiers:",
    ])

    id_names = {
        "doi": "doi",
        "arxiv_id": "arxiv",
        "s2_id": "semantic_scholar",
        "openalex_id": "openalex",
        "openreview_id": "openreview",
        "pmcid": "pmc",
        "core_id": "core",
    }
    for key, display_name in id_names.items():
        if ids.get(key):
            yaml_lines.append(f'  {display_name}: "{ids[key]}"')

    yaml_lines.extend([
        "",
        "# 链接",
        "urls:",
    ])
    for name, url in urls.items():
        yaml_lines.append(f'  {name}: "{url}"')

    # 摘要 (多行)
    if best.get("abstract"):
        yaml_lines.extend([
            "",
            "# 摘要",
            "abstract: |",
        ])
        for line in best["abstract"].split(". "):
            line = line.strip()
            if line:
                yaml_lines.append(f'  {line}.')

    # PDF 下载链接 (按可靠性排序)
    if pdf_urls:
        yaml_lines.extend([
            "",
            "# PDF 下载链接 (按可靠性排序)",
            "# reliability: high=直接可用, medium=可能可用, low=可能需要付费/重定向",
            "pdf_urls:",
        ])
        for item in pdf_urls:
            yaml_lines.append(f'  - source: {item["source"]}')
            yaml_lines.append(f'    url: "{item["url"]}"')
            yaml_lines.append(f'    reliability: {item["reliability"]}')

    # LaTeX 源码信息 (仅 arXiv)
    if ids.get("arxiv_id"):
        yaml_lines.extend([
            "",
            "# LaTeX 源码",
            "latex_source:",
            f'  available: true',
            f'  url: "https://arxiv.org/e-print/{ids["arxiv_id"]}"',
        ])
    else:
        yaml_lines.extend([
            "",
            "# LaTeX 源码",
            "latex_source:",
            f'  available: false',
            f'  note: "仅 arXiv 论文有 LaTeX 源码"',
        ])

    # 写入文件
    yaml_path = paper_dir / "metadata.yaml"
    yaml_content = "\n".join(yaml_lines)
    yaml_path.write_text(yaml_content, encoding="utf-8")

    return yaml_path


# === 工具函数 ===

def similarity(a: str, b: str) -> float:
    """计算字符串相似度"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_doi(doi: str) -> str:
    """规范化 DOI，用于去重"""
    if not doi:
        return None
    return doi.lower().replace("https://doi.org/", "").replace("http://doi.org/", "")


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


def merge_papers(papers: list[Paper], query: str) -> dict:
    """
    合并多个来源的论文信息

    找出所有标题匹配的论文（相似度 > 0.9），合并它们的 ID 和 PDF URL。
    """
    if not papers:
        return None

    # 计算相似度
    for p in papers:
        p._similarity = similarity(query, p.title or "")

    # 排序：相似度 > 有 DOI > 有 venue
    papers.sort(key=lambda p: (-p._similarity, 0 if p.doi else 1, 0 if p.venue else 1))

    # 取第一个作为基准
    best = papers[0]

    # 收集所有 ID
    ids = {
        "doi": best.doi,
        "arxiv_id": best.arxiv_id,
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
    for p in papers:
        if p._similarity >= 0.9 and p.pdf_url and p.source not in pdf_urls:
            pdf_urls[p.source] = p.pdf_url

    # 从其他匹配的论文补充缺失的 ID
    for p in papers[1:]:
        if p._similarity >= 0.9:
            if not ids["doi"] and p.doi:
                ids["doi"] = p.doi
            if not ids["arxiv_id"] and p.arxiv_id:
                ids["arxiv_id"] = p.arxiv_id
            if not ids["s2_id"] and p.s2_id:
                ids["s2_id"] = p.s2_id
            if not ids["openalex_id"] and p.openalex_id:
                ids["openalex_id"] = p.openalex_id
            if not ids["openreview_id"] and p.openreview_id:
                ids["openreview_id"] = p.openreview_id
            if not ids["pmcid"] and p.pmcid:
                ids["pmcid"] = p.pmcid
            if not ids["core_id"] and p.core_id:
                ids["core_id"] = p.core_id

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
    for p in papers:
        if hasattr(p, "_similarity"):
            delattr(p, "_similarity")

    return {
        "best_match": {
            "title": best.title,
            "authors": best.authors,
            "year": best.year,
            "venue": best.venue,
            "abstract": best.abstract,
        },
        "ids": {k: v for k, v in ids.items() if v},
        "urls": urls,
        "pdf_urls": pdf_url_list,
    }


# === 主函数 ===

def query_provider(provider_class, query: SearchQuery) -> ProviderResult:
    """查询单个 provider（跳过不支持当前 search_type 的 provider）"""
    if query.search_type not in provider_class.supported_search_types():
        return ProviderResult(papers=[], source=provider_class.name())
    provider = provider_class()
    return provider.search(query)


async def query_all(query: str, limit: int = 10, sources: list = None, top_n: int = 10):
    """并行查询所有指定源"""
    if sources is None:
        sources = ["s2", "openalex", "crossref", "arxiv", "openreview",
                   "biorxiv", "medrxiv", "core", "mdpi", "pubmed_central", "ssrn", "unpaywall",
                   "dblp", "europepmc", "zenodo", "openaire", "doaj", "hal", "repec"]

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

    search_query = SearchQuery(query=query, max_results=limit)

    # 自动检测查询类型
    detected_type, normalized_query = detect_query_type(query)
    search_query = SearchQuery(
        query=normalized_query,
        search_type=detected_type,
        max_results=limit
    )

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=len(sources)) as ex:
        futures = {
            src: loop.run_in_executor(ex, query_provider, cls, search_query)
            for src, cls in source_map.items()
            if src in sources
        }
        results = {}
        for src, fut in futures.items():
            results[src] = await fut

    # 合并所有论文
    all_papers = []
    source_counts = {}
    for src, result in results.items():
        source_counts[src] = len(result.papers)
        all_papers.extend(result.papers)

    # 去重
    deduped = deduplicate_by_doi(all_papers)

    # 计算相似度并排序
    query_lower = query.lower()
    for p in deduped:
        p._similarity = similarity(query_lower, (p.title or "").lower())

    deduped.sort(key=lambda p: (-p._similarity, 0 if p.doi else 1, 0 if p.venue else 1))

    # 取 top N
    top_papers = deduped[:top_n]

    # 清理临时属性
    for p in top_papers:
        if hasattr(p, "_similarity"):
            delattr(p, "_similarity")

    # 合并匹配论文的信息
    merged = merge_papers(top_papers, query) if top_papers else None

    return {
        "query": query,
        "total": len(deduped),
        "returned": len(top_papers),
        "sources": source_counts,
        "merged": merged,
        "candidates": [p.to_dict() for p in top_papers],
    }


def main():
    parser = argparse.ArgumentParser(description="查询学术 APIs 并保存 metadata.yaml")
    parser.add_argument("query", help="查询词")
    parser.add_argument("--limit", "-n", type=int, default=10, help="每源最大结果数")
    parser.add_argument("--top", "-t", type=int, default=10, help="返回的候选数量")
    parser.add_argument("--sources", "-s", default="",
                       help="数据源，逗号分隔 (默认使用全部源: s2,openalex,crossref,arxiv,openreview,biorxiv,core,mdpi,pubmed_central,ssrn,unpaywall)")
    parser.add_argument("--output", "-o", default="literature",
                       help="输出目录 (默认: literature/ 在当前项目目录下)")
    parser.add_argument("--force", "-f", action="store_true",
                       help="强制重新下载，即使已存在")

    args = parser.parse_args()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()] or None
    output_dir = Path(args.output)

    print(f"Querying: {args.query}")
    print(f"Sources: {sources if sources else 'all'}")
    print(f"Output: {output_dir}")

    result = asyncio.run(query_all(args.query, args.limit, sources, args.top))

    # 保存 candidates.json
    with open("/tmp/candidates.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Found {result['total']} (returning top {result['returned']})")
    for src, count in result["sources"].items():
        print(f"  {src}: {count}")

    # 保存 metadata.yaml
    if result.get("merged"):
        m = result["merged"]
        print(f"\nBest match: {m['best_match']['title']}")

        # 生成 citation key
        citation_key = generate_citation_key(m["best_match"])
        print(f"Citation key: {citation_key}")

        # 检查是否已存在
        paper_dir = output_dir / citation_key
        metadata_path = paper_dir / "metadata.yaml"

        if metadata_path.exists() and not args.force:
            # 检查 assets 是否完整
            content = metadata_path.read_text()
            if "assets:" in content:
                print(f"\n✓ Already imported: {paper_dir}")
                print("  Use --force to re-download")
                return

        # 如果 force 且已存在，删除旧目录
        if args.force and paper_dir.exists():
            import shutil
            shutil.rmtree(paper_dir)

        # 保存 metadata.yaml
        yaml_path = save_metadata_yaml(result["merged"], output_dir)
        if yaml_path:
            print(f"✓ Saved: {yaml_path}")
        else:
            print("✗ Failed to save metadata.yaml")


if __name__ == "__main__":
    main()