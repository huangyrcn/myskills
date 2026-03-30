# Foldername Generation

Final folder format:

```text
venueyear-lastname-method
```

Examples:

```text
Attention Is All You Need
-> neurips2017-vaswani-transformer

BERT: Pre-training of Deep Bidirectional Transformers
-> naacl2019-devlin-bert
```

## Why this is a staged process

1. `query_apis.py` first resolves the title into a canonical paper and recovers trusted identifiers such as `arxiv_id` and DOI.

2. It writes a temporary folder:

```text
papers/{title_slug}/
```

3. The model then reads:

- `title`
- `abstract`
- `venue_candidates`
- `authors`
- `year`

4. The model returns:

```json
{
  "venue": "neurips",
  "method_name": "transformer",
  "foldername": "neurips2017-vaswani-transformer"
}
```

5. `finalize_metadata.py` writes these values into `metadata.yaml` and renames the directory.

## Venue rules

- Return a short standardized venue token such as `neurips`, `iclr`, `icml`, `cvpr`, `acl`, `naacl`, `emnlp`.
- If the paper has no confirmed venue, use `arxiv`.

## Method rules

- Prefer the paper's method or acronym from the abstract.
- Prefer canonical short names such as `bert`, `gpt`, `transformer`, `vit`, `resnet`.
- Keep it lowercase and filesystem-safe.
- Keep it short; `finalize_metadata.py` will sanitize and trim it to fit the folder contract.
