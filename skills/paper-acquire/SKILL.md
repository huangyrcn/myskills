---
name: paper-acquire
description: >
  Build or update the canonical raw bundle for a resolved paper under `~/papers/{title_slug}`.
  Use this skill whenever the user wants to download a paper PDF and normalize it into `paper.md`.
  For repository discovery, use `paper-repo` skill after this one.
  Prefer this skill for raw acquisition work; do not use it to write reading notes.
argument-hint: "<title_slug> | <metadata_path>"
allowed-tools: Bash, Read, Write, Edit
---

# Paper Acquire

Hydrate the canonical raw bundle for a resolved paper.

## Ownership

This skill owns:

- `~/papers/{title_slug}/metadata.yaml` (extends with assets, normalization)
- `~/papers/{title_slug}/paper/paper.pdf`
- `~/papers/{title_slug}/paper/paper.md`
- `~/papers/{title_slug}/paper/paper_images/`

This skill does **not**:
- Write the final reading note
- Discover or clone repositories (use `paper-repo`)
- Modify `identity` or `bibliography` sections in metadata.yaml

## Workflow

### 1. Start from a resolved metadata bundle

**必须先有 `metadata.yaml`**（由 `paper-resolve` 产出）。

如果用户只给了一个模糊引用，先用 `paper-resolve`。

读取 metadata.yaml，提取对 acquire 有用的信息：

```yaml
# 从 metadata.yaml 提取
identifiers:
  arxiv: "1704.01212"        # → arXiv PDF
  pmcid: "PMC11399094"       # → PMC 全文 PDF
  semantic_scholar: "..."    # → S2 openAccessPdf
  doi: "10.xxx"              # → 出版商 PDF

urls:
  pdf: "https://..."         # → 直接下载 URL
  pmc: "https://pmc..."      # → PMC 页面，提取 PDF
```

### 2. PDF Acquisition (Priority Order)

按以下优先级下载 PDF：

| 优先级 | 来源 | 条件 | URL 模式 |
|---|---|---|---|
| **1** | arXiv PDF | `identity.aliases.arxiv` 存在 | `https://arxiv.org/pdf/{arxiv_id}.pdf` |
| **2** | PMC PDF | `identity.aliases.pmcid` 存在 | 从 `urls.pmc` 页面提取 |
| **3** | Semantic Scholar | `urls.pdf` 来自 S2 | 直接用 `urls.pdf` |
| **4** | 出版商 PDF | `identity.aliases.doi` 存在 | `https://doi.org/{doi}` 重定向 |

**下载流程**：

```bash
# 优先级 1: arXiv (免费)
if identity.aliases.arxiv exists:
  wget "https://arxiv.org/pdf/${arxiv_id}.pdf" -O paper/paper.pdf

# 优先级 2: PMC (免费全文)
if identity.aliases.pmcid exists:
  # PMC 页面通常有 PDF 链接
  crwlr crawl -o md "${urls.pmc}"  # 提取 PDF URL
  wget "${pmc_pdf_url}" -O paper/paper.pdf

# 优先级 3: Semantic Scholar openAccessPdf
if urls.pdf exists and looks like S2/pdfs.semanticscholar.org:
  wget "${urls.pdf}" -O paper/paper.pdf

# 优先级 4: 出版商 PDF (可能需要认证)
if identity.aliases.doi exists and no PDF yet:
  # 尝试 wget，可能需要 cdp-download 处理认证
  wget "https://doi.org/${doi}" -O paper/paper.pdf || \
  ${SKILL_DIR}/../web-kit/scripts/cdp-download "https://doi.org/${doi}" paper/paper.pdf
```

**为什么这个优先级**：

1. **arXiv 最优先**：免费 + 无认证
2. **PMC 其次**：免费全文
3. **S2 openAccessPdf**：免费开放获取
4. **出版商最后**：可能需要订阅/认证

### 3. Normalization (PDF → Markdown)

使用 `pdf-to-md` skill 的 MinerU 进行转换：

```bash
# PDF → MinerU
python3 "${SKILL_DIR}/../pdf-to-md/scripts/mineru-api.py" paper/paper.pdf -l en
# 输出: paper/paper.md + paper/paper_images/
```

### 4. Update metadata.yaml

完成 acquisition 后，更新 metadata.yaml 的 `assets` 和 `normalization` 部分：

```yaml
assets:
  paper_pdf:
    path: "paper/paper.pdf"
    size_bytes: 2950183
    source: "arxiv"  # 或 "pmc", "semantic_scholar", "publisher"
  paper_md:
    path: "paper/paper.md"
    backend: "mineru_vlm"
    generated_at: "2026-04-13"
  paper_images:
    path: "paper/images/"
    count: 12

normalization:
  backend: "mineru_vlm"
  completed_at: "2026-04-13"
```

## Storage Rules

Read [references/raw-layout.md](references/raw-layout.md) for directory structure.

## Dependencies

- `web-kit` skill — wget, cdp-download, crwlr
- `pdf-to-md` skill — MinerU API PDF conversion

## References

| 文件 | 用途 |
|---|---|
| [raw-layout.md](references/raw-layout.md) | 目录结构规范 |