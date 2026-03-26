---
name: paper-import
description: >
  Import a paper into the local literature library: metadata, PDF, LaTeX source, Markdown, and code repo.
  Use this skill whenever the user wants to get, download, fetch, find, import, or save a paper —
  even if they only mention the title, arXiv ID, or DOI.
  Also use when the user wants to find or clone the code/implementation for a paper.
  Triggers: "下载论文", "获取论文", "找这篇论文", "下载这篇", "导入论文", "import paper",
  "get paper", "fetch paper", "download paper", "找代码", "下载代码", "find the code",
  "get the implementation", "clone the repo", "有没有开源代码",
  or any mention of acquiring a paper or its code.
  Can be called silently by other skills (lit-review, idea-discovery) with an arXiv ID or DOI.
  Output: literature/{identifier}/ with metadata.yaml, paper/, and optional repo/.
---

# Paper Import

Downloads a complete paper package into a standardized local directory.

## Output Structure

```
literature/{identifier}/          e.g.  papers/vaswani2017attention/
├── metadata.yaml            paper metadata + asset paths
├── paper/
│   ├── paper.pdf            PDF full text
│   ├── paper.md             Markdown version (via /pdf-to-md)
│   ├── main.tex             LaTeX source (arXiv only, flattened)
│   └── refs.bib             bibliography (if present)
└── repo/                    code repository
```

`{identifier}` = `{author}{year}{keyword}`, e.g. `vaswani2017attention`.
See `references/identifier-generation.md` for rules.
See `references/metadata-schema.md` for the full metadata.yaml field reference.

---

## Step 0: Check Existing (增量检查)

**Before starting, check if paper already exists:**

```bash
IDENTIFIER_DIR="literature/{identifier}"

if [ -f "${IDENTIFIER_DIR}/metadata.yaml" ]; then
  # 检查 assets 是否已完整
  if grep -q "assets:" "${IDENTIFIER_DIR}/metadata.yaml"; then
    echo "✓ Already imported: ${IDENTIFIER_DIR}"
    echo "  Use --force to re-download"
    exit 0
  fi
fi
```

If `--force` flag is provided, delete existing directory and re-download.

---

## Step 1: Resolve Metadata

**只接受论文标题作为输入。**

```bash
# SKILL_DIR is the directory containing this SKILL.md
python3 "${SKILL_DIR}/scripts/query_apis.py" "Paper Title Here" --output literature
```

脚本会用标题去 arXiv、S2、OpenAlex、Crossref 等数据源搜索匹配，去重后写入 `literature/{identifier}/metadata.yaml`。

---

## Step 2: Download (PDF + LaTeX + Code) — 并行执行

**使用后台 Agent 并行下载，不阻塞主流程：**

```bash
PAPER_DIR="literature/{identifier}/paper"
mkdir -p "${PAPER_DIR}"
```

### 2a: PDF + LaTeX (主流程)

**Download PDF:**

```bash
python3 "${SKILL_DIR}/scripts/download_pdf.py" \
    --metadata "literature/{identifier}/metadata.yaml" \
    --output "${PAPER_DIR}"
```

**Download LaTeX (arXiv papers only, 与 PDF 并行):**

```bash
# 检查是否有 LaTeX 源码
if grep -q "latex_source:" "${IDENTIFIER_DIR}/metadata.yaml"; then
  LATEX_URL=$(grep -A1 "latex_source:" "${IDENTIFIER_DIR}/metadata.yaml" | grep "url:" | head -1 | sed 's/.*url: *"\([^"]*\)".*/\1/')

  if [ -n "$LATEX_URL" ]; then
    curl -L -A "Mozilla/5.0" -o /tmp/latex_src.tar.gz "$LATEX_URL" 2>/dev/null

    if file /tmp/latex_src.tar.gz | grep -qE "gzip|tar"; then
      tar -xzf /tmp/latex_src.tar.gz -C "${PAPER_DIR}/" 2>/dev/null || \
      tar -xf /tmp/latex_src.tar.gz -C "${PAPER_DIR}/"

      # Flatten: move .tex and .bib to paper/ root
      find "${PAPER_DIR}" -mindepth 2 \( -name "*.tex" -o -name "*.bib" \) \
          -exec mv {} "${PAPER_DIR}/" \; 2>/dev/null
      find "${PAPER_DIR}" -mindepth 1 -type d -empty -delete 2>/dev/null
      echo "✓ LaTeX downloaded"
    fi
  fi
fi
```

**Convert PDF → Markdown:**

```
/pdf-to-md "${PAPER_DIR}/paper.pdf"
```

### 2b: Find Code (与 2a 并行)

**在后台 Agent 中执行代码搜索，与 PDF 下载并行：**

```
Agent(run_in_background=true):
  1. Search LaTeX source for repo URLs
  2. Search paper.md for repo URLs
  3. Web search if needed
  4. Clone repo to literature/{identifier}/repo/
```

**代码搜索优先级：**

1. **LaTeX 源码** (最可靠 — 作者嵌入):
   ```bash
   grep -rhoE 'https?://(github|gitlab|gitee)\.com/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+' \
       "${PAPER_DIR}"/*.tex 2>/dev/null | sort -u
   ```

2. **Markdown** (语义判断):
   ```bash
   grep -oE 'https?://(github|gitlab|gitee)\.com/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+' \
       "${PAPER_DIR}/paper.md" | sort -u
   ```

3. **网页搜索** (最后手段):
   ```
   "{paper title}" github implementation
   ```

**Clone repo:**

```bash
REPO_DIR="literature/{identifier}/repo"
git clone "{repo_url}" "${REPO_DIR}"
```

---

## Step 3: Update metadata.yaml

```bash
cat >> "literature/{identifier}/metadata.yaml" << 'YAML'

# local assets
assets:
  pdf: paper/paper.pdf
  markdown: paper/paper.md
YAML

# LaTeX (if exists)
[ -f "literature/{identifier}/paper/main.tex" ] && \
    echo "  latex_dir: paper/" >> "literature/{identifier}/metadata.yaml"

# Repo (if cloned)
[ -d "literature/{identifier}/repo/.git" ] && \
    echo "  repo: repo/" >> "literature/{identifier}/metadata.yaml"
```

---

## Step 4: Report

```
✓ literature/sun2019videobert/

  paper/paper.pdf     6.0 MB  [arxiv]
  paper/paper.md      48 KB   [/pdf-to-md]
  paper/main.tex              [LaTeX, 2 .tex files]
  repo/               173 MB  [github.com/xxx/VideoBERT ⭐124]
```

---

## Quick Reference

```bash
# Check what was fetched
ls literature/{identifier}/
cat literature/{identifier}/metadata.yaml

# Read the paper
cat literature/{identifier}/paper/paper.md

# Explore code
ls literature/{identifier}/repo/
```