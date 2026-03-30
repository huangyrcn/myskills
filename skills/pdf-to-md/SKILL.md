---
name: pdf-to-md
description: >
  Convert a PDF into high-quality Markdown through the MinerU API VLM pipeline.
  Use this skill whenever the user wants PDF-to-Markdown conversion, OCR-like extraction,
  paper text extraction, or Markdown plus extracted images from a PDF. This skill supports
  the API backend only and always uses the high-quality VLM model configuration.
argument-hint: "<pdf_path> [-l lang]"
allowed-tools: Bash
---

# PDF to Markdown

Converts a PDF to:

```text
<pdf_stem>.md
<pdf_stem>_images/
```

## Prerequisite

Set the MinerU API token:

```bash
export MINERU_API_TOKEN="your_token_here"
```

## Usage

```bash
python3 "${SKILL_DIR}/scripts/mineru-api.py" <pdf_path> [-l lang]
```

- `pdf_path`: local PDF path
- `-l lang`: language hint, `en` or `ch`

## Backend contract

- Supported backend: MinerU API only
- Model: VLM
- Goal: highest available parsing quality for formulas, tables, and mixed-layout academic PDFs

## Output behavior

- Output files are written next to the PDF
- Existing Markdown and image directories for the same stem may be overwritten
- Example: `paper.pdf` -> `paper.md` and `paper_images/`
