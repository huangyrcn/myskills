# Foldername Generation

Final symlink format:

```text
venue-method-author
```

Examples:

```text
Attention Is All You Need
-> neurips2017-transformer-vaswani

BERT: Pre-training of Deep Bidirectional Transformers
-> naacl2019-bert-devlin
```

## Why this is a staged process

1. `query_apis.py` first resolves the title into a canonical paper and recovers trusted identifiers such as `arxiv_id` and DOI.

2. It writes a temporary folder:

```text
~/papers/{title_slug}/
```

This is the actual storage location — it is NOT renamed during finalization.

3. The model then reads:

- `title`
- `abstract`
- `venue_candidates`
- `authors`
- `year`

4. The model returns:

```json
{
  "venue": "neurips2017",
  "author": "vaswani",
  "method_name": "transformer"
}
```

5. `finalize_metadata.py` writes these values into `metadata.yaml` and creates a symlink in the current working directory: `{venue}-{method}-{author}/ -> ~/papers/{title_slug}/`.
   If cwd is the home directory, the symlink is skipped.

## Venue rules

- Return a short standardized venue token such as `neurips2017`, `iclr2019`, `icml2023`, `cvpr2024`, `acl`, `naacl2019`, `emnlp2024`.
- Include the year in the venue token (e.g., `neurips2017`, not `neurips`).
- If the paper has no confirmed venue, use `arxiv`.

## Method rules

- Prefer the paper's method or acronym from the abstract.
- Prefer canonical short names such as `bert`, `gpt`, `transformer`, `vit`, `resnet`.
- Keep it lowercase and filesystem-safe.
- Keep it short; `finalize_metadata.py` will sanitize and trim it to 15 characters.

## Author rules

- Use the first author's last name.
- `finalize_metadata.py` will slugify it (max 40 chars, ASCII-safe).
