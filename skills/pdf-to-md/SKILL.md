---
name: pdf-to-md
description: >
  Convert PDF to high-quality Markdown. Uses MinerU OCR on a remote GPU server.
  Produces paper.md + paper_images/ in the same directory as the input PDF.
  Use this skill whenever the user wants to convert PDF to Markdown, parse a PDF,
  OCR a paper, or extract text from a PDF document — especially academic papers.
  Also use when other skills (paper-import, research-lit) need PDF-to-Markdown conversion.
  Triggers: "PDF转markdown", "转写PDF", "parse PDF", "OCR论文", "pdf to md",
  "convert PDF to markdown", "提取PDF文本", "论文转文本", "pdf-to-md".
argument-hint: "<pdf_path> [-l lang]"
allowed-tools: Bash
---

# PDF to Markdown

Converts PDF files to Markdown via MinerU on a remote GPU server.

## Usage

```bash
# SKILL_DIR is the directory containing this SKILL.md
bash "${SKILL_DIR}/scripts/mineru-remote.sh" <pdf_path> [-l lang]
```

- `pdf_path`: absolute or relative path to the PDF file
- `-l lang`: optional language hint (`en`, `ch`, `ch_lite`, etc.). Defaults to auto-detect.

## Output

Files are written to the same directory as the input PDF:

```
<dir>/
├── paper.md          # Markdown output (named after the PDF stem)
└── paper_images/     # Extracted figures and images
```

The output filename matches the input PDF stem, e.g. `report.pdf` → `report.md` + `report_images/`.

## Workflow

### Single PDF

```bash
bash "${SKILL_DIR}/scripts/mineru-remote.sh" path/to/paper.pdf -l en
```

### Batch conversion

For multiple PDFs, run sequentially (they share the same vllm server, so no extra cold start after the first):

```bash
for pdf in papers/*/paper/paper.pdf; do
  echo "=== $(dirname "$pdf") ==="
  bash "${SKILL_DIR}/scripts/mineru-remote.sh" "$pdf" -l en
done
```

For parallel batch conversion (faster, safe to run 3-4 concurrently):

```bash
find papers/ -name "paper.pdf" | xargs -P3 -I{} bash "${SKILL_DIR}/scripts/mineru-remote.sh" {} -l en
```

## Server Lifecycle

The script manages a shared vllm server on the remote GPU automatically:

- **First call**: starts vllm server on the best available GPU (~4 min cold start)
- **Concurrent calls**: reuse the running server (no extra cold start, no extra GPU)
- **After last task**: server shuts down automatically via refcount mechanism

No manual server management is needed.

## Key Rules

- The script requires SSH access to the `l40` host — it will fail if the host is unreachable
- Output overwrites existing .md files in the same directory
- For academic papers, `-l en` (English) or `-l ch` (Chinese) usually gives the best results
